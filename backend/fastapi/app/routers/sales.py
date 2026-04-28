from __future__ import annotations

import tempfile
import random
import re
import math
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import cast as type_cast
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import Integer, case, cast, false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_aqc_role_key, get_current_user, require_permissions, scoped_sales_conditions, to_iso, to_local_iso, user_shop_ids
from ..importers.sales_template_import import import_sales_template, inspect_sales_template_import
from ..inventory import apply_inventory_delta, inventory_actor_name, normalize_shop_name, recalculate_goods_stock, simplify_shop_name
from ..models import AqcGoodsItem, AqcSaleRecord, AqcShop, AqcUser
from ..schemas import (
    AccountPerformanceRankItemOut,
    AccountPerformanceResponse,
    MessageResponse,
    SalesCalendarResponse,
    SalesCalendarBreakdownOut,
    SalesCalendarDrilldownItemOut,
    SalesCalendarPersonEntryOut,
    SaleRecordCreateRequest,
    SaleRecordListResponse,
    SaleRecordMetaResponse,
    SaleRecordOut,
    SalesFilterOptionOut,
    SalesIndexOptionOut,
    SalesRecommendedPeriodOptionOut,
    SalesMetricOut,
    SalesPointOut,
    SalesSummaryResponse,
    SalesTemplateImportResponse,
)


router = APIRouter(prefix="/sales", tags=["sales"])
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
ORDER_NOTE_PATTERN = re.compile(r"单号:([^;\s]+)")
GUIDE_NOTE_PATTERN = re.compile(r"导购:([^;]+)")
DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SALE_SORT_FIELD_MAP = {
    "sold_at": AqcSaleRecord.sold_at,
    "goods_series": AqcSaleRecord.goods_series,
    "goods_model": AqcSaleRecord.goods_model,
    "goods_brand": AqcSaleRecord.goods_brand,
    "unit_price": AqcSaleRecord.unit_price,
    "quantity": AqcSaleRecord.quantity,
    "receivable_amount": AqcSaleRecord.receivable_amount,
    "discount_rate": AqcSaleRecord.discount_rate,
    "coupon_amount": AqcSaleRecord.coupon_amount,
    "received_amount": AqcSaleRecord.amount,
    "shop_name": AqcSaleRecord.shop_name,
    "ship_shop_name": AqcSaleRecord.ship_shop_name,
    "salesperson": AqcSaleRecord.salesperson,
    "order_num": AqcSaleRecord.order_num,
}


PERIOD_META = {
    "day": {"label": "本日", "title": "今日累计销售额", "bucket": "hour"},
    "week": {"label": "本周", "title": "近7日累计销售额", "bucket": "day"},
    "month": {"label": "本月", "title": "近30日累计销售额", "bucket": "day"},
    "ytd": {"label": "年累计", "title": "年累计销售额", "bucket": "month"},
}
ACCOUNT_PERIOD_LABELS = {
    "today": "今日",
    "yesterday": "昨日",
    "this_week": "本周",
    "last_week": "上周",
    "this_month": "本月",
    "last_month": "上月",
    "this_year": "本年",
    "last_year": "去年",
    "range": "时间范围",
}
SALES_RECOMMENDED_PERIOD_KEYS = (
    "today",
    "yesterday",
    "this_week",
    "last_week",
    "this_month",
    "last_month",
    "this_year",
    "last_year",
)
SALES_RECOMMENDED_PERIOD_LABELS = {
    "today": "本日",
    "yesterday": "昨日",
    "this_week": "本周",
    "last_week": "上周",
    "this_month": "本月",
    "last_month": "上月",
    "this_year": "本年",
    "last_year": "去年",
}
YEAR_MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")
SALE_STATUS_LABELS = {
    "normal": "正常",
    "returned": "已退货",
    "return_entry": "退货冲销",
}
SALE_KIND_GOODS = "goods"
SALE_KIND_REPAIR = "repair"
SALE_KIND_LABELS = {
    SALE_KIND_GOODS: "普通销售",
    SALE_KIND_REPAIR: "维修销售",
}


def _parse_sold_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
    clean = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(clean)
        if parsed.tzinfo is not None:
            return parsed.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
        return parsed
    except Exception:
        return datetime.now(SHANGHAI_TZ).replace(tzinfo=None)


def _clean_text(value: str | None, max_length: int) -> str:
    return (value or "").strip()[:max_length]


def _normalize_sale_kind(value: str | None) -> str:
    return SALE_KIND_REPAIR if str(value or "").strip().lower() == SALE_KIND_REPAIR else SALE_KIND_GOODS


def _to_amount(value: float | int | str | Decimal | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _extract_order_num(note: str | None) -> str:
    text = str(note or "").strip()
    match = ORDER_NOTE_PATTERN.search(text)
    return match.group(1).strip()[:32] if match else ""


def _extract_salesperson(note: str | None) -> str:
    text = str(note or "").strip()
    match = GUIDE_NOTE_PATTERN.search(text)
    return match.group(1).strip()[:80] if match else ""


def _normalize_sale_index_key(series: str | None, brand: str | None, model: str | None) -> str:
    seed = f"{series or ''} {brand or ''} {model or ''}".strip()
    if not seed:
        return "#"
    for ch in seed:
        if ch.isascii() and ch.isalpha():
            return ch.upper()
        if ch.isdigit():
            return ch
    return "#"


def _format_discount_display(rate: float, receivable_amount: float, received_amount: float) -> str:
    if receivable_amount <= 0:
        return "/"
    if abs(receivable_amount - received_amount) < 0.005 and rate >= 9.995:
        return "/"
    return f"{rate:.2f}"


def _resolve_order_num(item: AqcSaleRecord) -> str:
    stored = _clean_text(item.order_num, 32)
    if stored:
        return stored
    extracted = _extract_order_num(item.note)
    if extracted:
        return extracted
    if item.sold_at and item.id:
        return f"Clo{item.sold_at.strftime('%Y%m%d')}{int(item.id):09d}"[:32]
    return ""


def _resolve_shop_name(item: AqcSaleRecord) -> str:
    _, stored = normalize_shop_name(_clean_text(item.shop_name, 255))
    if stored:
        return stored
    if (item.customer_name or "").strip():
        return _clean_text(item.customer_name, 255)
    if " / " in (item.channel or ""):
        return _clean_text((item.channel or "").split(" / ", 1)[1], 255)
    return ""


def _resolve_ship_shop_name(item: AqcSaleRecord) -> str:
    _, stored = normalize_shop_name(_clean_text(item.ship_shop_name, 255))
    if stored:
        return stored
    return _resolve_shop_name(item)


def _resolve_salesperson(item: AqcSaleRecord) -> str:
    stored = _clean_text(item.salesperson, 80)
    creator_display_name = _clean_text(item.creator.display_name if item.creator else "", 80)
    creator_username = _clean_text(item.creator.username if item.creator else "", 80)
    creator_phone = _clean_text(item.creator.phone if item.creator else "", 80)
    if stored:
        if creator_display_name and stored in {creator_username, creator_phone}:
            return creator_display_name
        return stored
    if creator_display_name:
        return creator_display_name
    return _extract_salesperson(item.note)


def _find_salesperson_user(db: Session, raw_value: str | None, *, active_only: bool = True) -> AqcUser | None:
    matched_users = _find_salesperson_users(db, raw_value, active_only=active_only)
    return matched_users[0] if matched_users else None


def _find_salesperson_users(db: Session, raw_value: str | None, *, active_only: bool = True) -> list[AqcUser]:
    clean_value = _clean_text(raw_value, 80)
    if not clean_value:
        return []
    conditions = [
        or_(
            AqcUser.username == clean_value,
            AqcUser.display_name == clean_value,
            AqcUser.phone == clean_value,
        ),
    ]
    if active_only:
        conditions.insert(0, AqcUser.is_active.is_(True))
    return list(
        db.execute(select(AqcUser).where(*conditions).limit(20))
        .scalars()
        .all()
    )


def _dedupe_clean_texts(*values: str | None, max_length: int = 80) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean_value = _clean_text(value, max_length)
        if not clean_value or clean_value in seen:
            continue
        seen.add(clean_value)
        deduped.append(clean_value)
    return deduped


def _salesperson_identity_candidates(raw_value: str | None, matched_users: list[AqcUser] | None = None) -> list[str]:
    values: list[str | None] = [raw_value]
    for user in matched_users or []:
        values.extend([user.display_name, user.username, user.phone])
    return _dedupe_clean_texts(*values, max_length=80)


def _salesperson_match_conditions(raw_value: str | None, matched_users: list[AqcUser] | None = None) -> list:
    conditions: list = []
    salesperson_candidates = _salesperson_identity_candidates(raw_value, matched_users)
    if salesperson_candidates:
        conditions.append(AqcSaleRecord.salesperson.in_(salesperson_candidates))
    matched_user_ids = sorted({int(user.id) for user in (matched_users or []) if user.id is not None})
    if matched_user_ids:
        conditions.append(AqcSaleRecord.created_by.in_(matched_user_ids))
    return conditions


def _latest_salesperson_sale_row(db: Session, *, scoped_conditions: list, salesperson: str | None) -> AqcSaleRecord | None:
    matched_users = _find_salesperson_users(db, salesperson, active_only=False)
    candidate_conditions = _salesperson_match_conditions(salesperson, matched_users)
    if not candidate_conditions:
        return None
    row_conditions = list(scoped_conditions)
    row_conditions.append(or_(*candidate_conditions))
    return (
        db.execute(
            select(AqcSaleRecord)
            .where(*row_conditions)
            .order_by(AqcSaleRecord.sold_at.desc(), AqcSaleRecord.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def _resolve_salesperson_name(db: Session, raw_value: str | None, current_user: AqcUser) -> str:
    matched_user = _find_salesperson_user(db, raw_value)
    if matched_user is not None:
        return _clean_text(matched_user.display_name or matched_user.username, 80)

    current_name = _clean_text(current_user.display_name or current_user.username, 80)
    clean_value = _clean_text(raw_value, 80)
    if clean_value in {
        _clean_text(current_user.username, 80),
        _clean_text(current_user.phone, 80),
    }:
        return current_name
    return clean_value or current_name


def _sales_template_import_message(stats: dict, *, dry_run: bool) -> str:
    total_rows = int(stats.get("totalRows") or 0)
    rows_ready = int(stats.get("rowsReady") or 0)
    duplicates = int(stats.get("duplicates") or 0)
    imported = int(stats.get("imported") or 0)
    unmatched_goods = int(len(stats.get("unmatchedGoods") or []))
    unmatched_shops = int(len(stats.get("unmatchedShops") or []))
    out_of_scope = int(len(stats.get("outOfScopeShops") or []))

    if dry_run:
        if unmatched_goods or unmatched_shops or out_of_scope:
            return "校验未通过，请先处理未匹配商品、门店或越权门店"
        return f"校验通过，共 {total_rows} 行，可导入 {rows_ready} 行，识别重复 {duplicates} 条"

    if imported > 0 and duplicates > 0:
        return f"成功导入 {imported} 条销售记录，跳过 {duplicates} 条重复记录"
    if imported > 0:
        return f"成功导入 {imported} 条销售记录"
    if duplicates > 0:
        return f"未导入新记录，{duplicates} 条均为重复记录"
    return f"未导入新记录，共处理 {total_rows} 行"


def _parse_sale_bound(raw: str | None, *, end_of_day: bool = False) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if DATE_ONLY_PATTERN.match(text):
            parsed = datetime.fromisoformat(text)
            if end_of_day:
                return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            return parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _build_sale_conditions(
    db: Session,
    *,
    sale_kind: str | None = SALE_KIND_GOODS,
    record_id: int | None = None,
    keyword: str = "",
    order_num: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    shop_id: int | None = None,
    shop_name: str | None = None,
    salesperson: str | None = None,
    sale_status: str | None = None,
    index_key: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list:
    conditions: list = []
    normalized_sale_kind = _normalize_sale_kind(sale_kind)
    conditions.append(AqcSaleRecord.sale_kind == normalized_sale_kind)

    if record_id is not None:
        conditions.append(AqcSaleRecord.id == int(record_id))

    clean_keyword = keyword.strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        conditions.append(
            or_(
                AqcSaleRecord.order_num.like(like),
                AqcSaleRecord.channel.like(like),
                AqcSaleRecord.shop_name.like(like),
                AqcSaleRecord.salesperson.like(like),
                AqcSaleRecord.customer_name.like(like),
                AqcSaleRecord.note.like(like),
                AqcSaleRecord.goods_code.like(like),
                AqcSaleRecord.goods_brand.like(like),
                AqcSaleRecord.goods_series.like(like),
                AqcSaleRecord.goods_model.like(like),
                AqcSaleRecord.goods_barcode.like(like),
            )
        )

    if order_num:
        conditions.append(AqcSaleRecord.order_num.like(f"%{order_num.strip()}%"))
    if brand:
        conditions.append(AqcSaleRecord.goods_brand == brand.strip())
    if series:
        conditions.append(AqcSaleRecord.goods_series == series.strip())
    if model:
        conditions.append(AqcSaleRecord.goods_model.like(f"%{model.strip()}%"))
    normalized_shop_name = ""
    if shop_name:
        _, normalized_shop_name = normalize_shop_name(shop_name.strip())
    elif shop_id is not None:
        matched_shop = db.execute(select(AqcShop.name).where(AqcShop.id == int(shop_id)).limit(1)).scalar()
        if matched_shop:
            _, normalized_shop_name = normalize_shop_name(str(matched_shop).strip())
    if shop_id is not None and normalized_shop_name:
        conditions.append(or_(AqcSaleRecord.shop_id == shop_id, AqcSaleRecord.shop_name == normalized_shop_name))
    elif shop_id is not None:
        conditions.append(AqcSaleRecord.shop_id == shop_id)
    elif normalized_shop_name:
        conditions.append(AqcSaleRecord.shop_name == normalized_shop_name)
    if salesperson:
        clean_salesperson = salesperson.strip()
        matched_users = _find_salesperson_users(db, clean_salesperson, active_only=False)
        salesperson_conditions = _salesperson_match_conditions(clean_salesperson, matched_users)
        conditions.append(or_(*salesperson_conditions))
    if sale_status:
        conditions.append(AqcSaleRecord.sale_status == _clean_text(sale_status, 20))
    if index_key:
        conditions.append(AqcSaleRecord.index_key == index_key.strip().upper()[:8])

    start = _parse_sale_bound(date_from)
    end = _parse_sale_bound(date_to, end_of_day=True)
    if start is not None:
        conditions.append(AqcSaleRecord.sold_at >= start)
    if end is not None:
        conditions.append(AqcSaleRecord.sold_at <= end)

    return conditions


def _normalize_sort_field(sort_field: str | None) -> str:
    field = str(sort_field or "sold_at").strip().lower()
    return field if field in SALE_SORT_FIELD_MAP else "sold_at"


def _normalize_sort_order(sort_order: str | None) -> str:
    return "asc" if str(sort_order or "").strip().lower() == "asc" else "desc"


def _generate_sale_order_num(db: Session, sold_at: datetime) -> str:
    prefix = f"Clo{sold_at.strftime('%Y%m%d')}"
    randomizer = random.SystemRandom()
    for _ in range(24):
        suffix = f"{randomizer.randrange(0, 1_000_000_000):09d}"
        candidate = f"{prefix}{suffix}"
        exists = db.execute(select(AqcSaleRecord.id).where(AqcSaleRecord.order_num == candidate).limit(1)).scalar()
        if exists is None:
            return candidate
    fallback_seed = int(datetime.now(SHANGHAI_TZ).timestamp() * 1000000) % 1_000_000_000
    return f"{prefix}{fallback_seed:09d}"


def _goods_display_name(*parts: str) -> str:
    name = " ".join(part.strip() for part in parts if (part or "").strip()).strip()
    return name or "-"


def _resolve_calendar_person_entry_label(row: AqcSaleRecord) -> str:
    sale_kind = _normalize_sale_kind(row.sale_kind)
    if sale_kind == SALE_KIND_REPAIR:
        return _clean_text(row.note, 255) or _resolve_order_num(row) or "维修项目"
    model_name = _clean_text(row.goods_model, 191)
    if model_name:
        return model_name
    display_name = _goods_display_name(row.goods_brand or "", row.goods_series or "", row.goods_model or "")
    return display_name if display_name != "-" else (_resolve_order_num(row) or "未命名商品")


def _build_calendar_person_entries_from_map(entries_map: dict[str, dict[str, object]], *, sale_kind: str) -> list[SalesCalendarPersonEntryOut]:
    label_prefix = "单数" if sale_kind == SALE_KIND_REPAIR else "销量"
    return [
        SalesCalendarPersonEntryOut(
            label=label,
            amount=round(float(stats.get("amount") or 0), 2),
            meta=f"{label_prefix} {int(stats.get('quantity') or 0)} · 订单 {len(type_cast(set, stats.get('orderNums') or set()))}",
        )
        for label, stats in sorted(
            entries_map.items(),
            key=lambda item: (-float(item[1].get("amount") or 0), item[0]),
        )
    ]


def _normalized_sale_status(status: str | None) -> str:
    return _clean_text(status, 20) or "normal"


def _normalize_sale_metric_value(value: float | int | Decimal | None, status: str | None) -> float:
    amount = float(value or 0)
    normalized_status = _normalized_sale_status(status)
    if normalized_status == "returned":
        return abs(amount)
    if normalized_status == "return_entry":
        return -abs(amount)
    return amount


def _normalize_sale_metric_quantity(value: int | float | Decimal | None, status: str | None) -> int:
    quantity = int(value or 0)
    normalized_status = _normalized_sale_status(status)
    if normalized_status == "returned":
        return abs(quantity)
    if normalized_status == "return_entry":
        return -abs(quantity)
    return quantity


def _sale_metric_snapshot(item: AqcSaleRecord) -> tuple[float, float, float, int, str]:
    sale_status = _normalized_sale_status(item.sale_status)
    receivable_amount = _normalize_sale_metric_value(
        item.receivable_amount if item.receivable_amount is not None else item.amount,
        sale_status,
    )
    received_amount = _normalize_sale_metric_value(item.amount, sale_status)
    coupon_amount = _normalize_sale_metric_value(item.coupon_amount, sale_status)
    quantity = _normalize_sale_metric_quantity(item.quantity, sale_status)
    return receivable_amount, received_amount, coupon_amount, quantity, sale_status


def _status_normalized_metric_expr(column, *, integer: bool = False):
    base_expr = func.coalesce(column, 0)
    abs_expr = cast(func.abs(base_expr), Integer) if integer else func.abs(base_expr)
    status_expr = func.coalesce(AqcSaleRecord.sale_status, "normal")
    return case(
        (status_expr == "returned", abs_expr),
        (status_expr == "return_entry", -abs_expr),
        else_=base_expr,
    )


def _to_sale_out(item: AqcSaleRecord) -> SaleRecordOut:
    sale_kind = _normalize_sale_kind(item.sale_kind)
    order_num = _resolve_order_num(item)
    shop_name = _resolve_shop_name(item)
    ship_shop_name = _resolve_ship_shop_name(item)
    salesperson = _resolve_salesperson(item)
    receivable_amount, received_amount, coupon_amount, quantity, sale_status = _sale_metric_snapshot(item)
    discount_rate = float(item.discount_rate or 0)
    return SaleRecordOut(
        id=item.id,
        soldAt=to_local_iso(item.sold_at) or "",
        saleKind=sale_kind,
        saleKindLabel=SALE_KIND_LABELS.get(sale_kind, SALE_KIND_LABELS[SALE_KIND_GOODS]),
        orderNum=order_num,
        goodsId=item.goods_id,
        goodsCode=item.goods_code or "",
        goodsBrand=item.goods_brand or "",
        goodsSeries=item.goods_series or "",
        goodsModel=item.goods_model or "",
        goodsBarcode=item.goods_barcode or "",
        indexKey=item.index_key or _normalize_sale_index_key(item.goods_series, item.goods_brand, item.goods_model),
        goodsDisplayName=_goods_display_name(item.goods_brand or "", item.goods_series or "", item.goods_model or ""),
        unitPrice=float(item.unit_price or 0),
        receivableAmount=receivable_amount,
        receivedAmount=received_amount,
        couponAmount=coupon_amount,
        discountRate=discount_rate,
        discountDisplay=_format_discount_display(discount_rate, receivable_amount, received_amount),
        amount=received_amount,
        quantity=quantity,
        channel=item.channel or "",
        saleStatus=sale_status,
        saleStatusLabel=SALE_STATUS_LABELS.get(sale_status, "正常"),
        sourceSaleRecordId=int(item.source_sale_record_id) if item.source_sale_record_id is not None else None,
        relatedWorkOrderId=int(item.related_work_order_id) if item.related_work_order_id is not None else None,
        shopId=item.shop_id,
        shopName=shop_name,
        shipShopId=item.ship_shop_id,
        shipShopName=ship_shop_name,
        salesperson=salesperson,
        customerName=item.customer_name or "",
        note=item.note or "",
        createdBy=item.created_by,
        createdByName=item.creator.display_name if item.creator else None,
        createdAt=to_iso(item.created_at) or "",
        updatedAt=to_iso(item.updated_at) or "",
    )


def _normalize_period(period: str | None) -> str:
    value = str(period or "day").lower()
    if value not in PERIOD_META:
        return "day"
    return value


def _resolve_summary_custom_range(date_from: str | None, date_to: str | None) -> tuple[datetime, datetime] | None:
    start = _parse_sale_bound(date_from)
    end = _parse_sale_bound(date_to, end_of_day=True)
    if start is None or end is None or start > end:
        return None
    return start, end


def _current_user_salesperson_candidates(user: AqcUser) -> list[str]:
    return _dedupe_clean_texts(user.display_name, user.username, user.phone, max_length=80)


def _resolve_account_custom_range(date_from: str | None, date_to: str | None) -> tuple[datetime, datetime] | None:
    start = _parse_sale_bound(date_from)
    end = _parse_sale_bound(date_to, end_of_day=True)
    if start is None or end is None or start > end:
        return None
    return start, end


def _resolve_account_period_window(
    period: str | None,
    date_from: str | None,
    date_to: str | None,
    now: datetime,
) -> tuple[str, datetime, datetime, str]:
    normalized = str(period or "this_month").strip().lower()
    custom_range = _resolve_account_custom_range(date_from, date_to)
    if custom_range is not None:
        start, end = custom_range
        return "range", start, end, _format_summary_range_label(start, end)

    today_start = datetime(now.year, now.month, now.day)
    if normalized == "today":
        return "today", today_start, now, ACCOUNT_PERIOD_LABELS["today"]
    if normalized == "yesterday":
        start = today_start - timedelta(days=1)
        end = today_start - timedelta(microseconds=1)
        return "yesterday", start, end, ACCOUNT_PERIOD_LABELS["yesterday"]
    if normalized == "this_week":
        start = today_start - timedelta(days=today_start.weekday())
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
        return "this_week", start, end, ACCOUNT_PERIOD_LABELS["this_week"]
    if normalized == "last_week":
        end = today_start - timedelta(days=today_start.weekday(), microseconds=1)
        start = datetime(end.year, end.month, end.day) - timedelta(days=6)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return "last_week", start, end, ACCOUNT_PERIOD_LABELS["last_week"]
    if normalized == "last_month":
        current_month_start = datetime(now.year, now.month, 1)
        end = current_month_start - timedelta(microseconds=1)
        start = datetime(end.year, end.month, 1)
        return "last_month", start, end, ACCOUNT_PERIOD_LABELS["last_month"]
    if normalized == "this_year":
        start = datetime(now.year, 1, 1)
        end = datetime(now.year + 1, 1, 1) - timedelta(microseconds=1)
        return "this_year", start, end, ACCOUNT_PERIOD_LABELS["this_year"]
    if normalized == "last_year":
        start = datetime(now.year - 1, 1, 1)
        end = datetime(now.year, 1, 1) - timedelta(microseconds=1)
        return "last_year", start, end, ACCOUNT_PERIOD_LABELS["last_year"]

    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1) - timedelta(microseconds=1)
    else:
        end = datetime(now.year, now.month + 1, 1) - timedelta(microseconds=1)
    return "this_month", start, end, ACCOUNT_PERIOD_LABELS["this_month"]


def _resolve_account_rank_shop_context(db: Session, user: AqcUser, scoped_conditions: list) -> tuple[int | None, str]:
    primary_shop_ids = user_shop_ids(user)
    if primary_shop_ids:
        primary_shop_id = int(primary_shop_ids[0])
        return primary_shop_id, _shop_name_by_id(db, primary_shop_id)
    if user.shop_id is not None:
        return int(user.shop_id), _shop_name_by_id(db, int(user.shop_id))
    return _resolve_summary_shop_context(
        db,
        scoped_conditions=scoped_conditions,
        salesperson=_clean_text(user.display_name or user.username, 80),
    )


def _aggregate_salesperson_rankings(
    rows: list[AqcSaleRecord],
    *,
    excluded_names: set[str] | None = None,
) -> list[AccountPerformanceRankItemOut]:
    excluded = {item for item in (excluded_names or set()) if item}
    buckets: dict[str, dict[str, float | int | list[str]]] = {}
    for row in rows:
        name = _clean_text(_resolve_salesperson(row), 80)
        if not name or name in excluded:
            continue
        bucket = buckets.setdefault(name, {"amount": 0.0, "quantity": 0, "shops": []})
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        bucket["amount"] = round(float(bucket["amount"] or 0) + received_amount, 2)
        bucket["quantity"] = int(bucket["quantity"] or 0) + quantity
        shop_name = _clean_text(row.shop_name, 255)
        if shop_name:
            current_shops = type_cast(list[str], bucket["shops"])
            if shop_name not in current_shops:
                current_shops.append(shop_name)

    ordered = sorted(
        buckets.items(),
        key=lambda item: (-float(item[1]["amount"] or 0), -int(item[1]["quantity"] or 0), item[0]),
    )
    return [
        AccountPerformanceRankItemOut(
            rank=index + 1,
            name=name,
            shopName="、".join(type_cast(list[str], stats["shops"] or [])),
            amount=round(float(stats["amount"] or 0), 2),
            quantity=int(stats["quantity"] or 0),
        )
        for index, (name, stats) in enumerate(ordered)
    ]


def _compute_joined_days(employment_date: str | None, now: datetime) -> int | None:
    text = str(employment_date or "").strip()
    if not text:
        return None
    try:
        start_date = datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    delta_days = (now.date() - start_date).days
    if delta_days < 0:
        return 0
    return delta_days + 1


def _resolve_range_bucket(start: datetime, end: datetime) -> str:
    span = end - start
    if span <= timedelta(days=1):
        return "hour"
    if span <= timedelta(days=93):
        return "day"
    return "month"


def _format_summary_range_label(start: datetime, end: datetime) -> str:
    if start.date() == end.date():
        return start.strftime("%Y-%m-%d")
    return f"{start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}"


def _format_commission_rate_label(rate: float) -> str:
    percent = round(max(0.0, min(float(rate or 0.0), 1.0)) * 100, 2)
    if float(percent).is_integer():
        return f"{int(percent)}%"
    if float(percent * 10).is_integer():
        return f"{percent:.1f}%"
    return f"{percent:.2f}%"


def _previous_custom_range_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    span = end - start
    previous_end = start - timedelta(microseconds=1)
    previous_start = previous_end - span
    return previous_start, previous_end


def _period_window(period: str, now: datetime) -> tuple[datetime, datetime]:
    day_start = datetime(now.year, now.month, now.day)
    if period == "day":
        return day_start, now
    if period == "week":
        week_start = day_start - timedelta(days=day_start.weekday())
        return week_start, now
    if period == "month":
        return datetime(now.year, now.month, 1), now
    return datetime(now.year, 1, 1), now


def _previous_period_window(period: str, now: datetime) -> tuple[datetime, datetime]:
    current_start, _current_end = _period_window(period, now)
    if period == "day":
        return current_start - timedelta(days=1), current_start - timedelta(microseconds=1)
    if period == "week":
        return current_start - timedelta(days=7), current_start - timedelta(microseconds=1)
    if period == "month":
        previous_month = current_start.month - 1 or 12
        previous_year = current_start.year - 1 if current_start.month == 1 else current_start.year
        previous_start = datetime(previous_year, previous_month, 1)
        return previous_start, current_start - timedelta(microseconds=1)
    previous_start = datetime(now.year - 1, 1, 1)
    return previous_start, datetime(now.year, 1, 1) - timedelta(microseconds=1)


def _bucket_key(dt: datetime, bucket: str) -> str:
    if bucket == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    if bucket == "month":
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


def _build_bucket_axis(start: datetime, end: datetime, bucket: str) -> list[str]:
    axis: list[str] = []
    cursor = start

    if bucket == "hour":
        cursor = cursor.replace(minute=0, second=0, microsecond=0)
        while cursor <= end:
            axis.append(_bucket_key(cursor, bucket))
            cursor += timedelta(hours=1)
        return axis

    if bucket == "month":
        cursor = datetime(cursor.year, cursor.month, 1)
        while cursor <= end:
            axis.append(_bucket_key(cursor, bucket))
            next_month = cursor.month + 1
            next_year = cursor.year
            if next_month == 13:
                next_month = 1
                next_year += 1
            cursor = datetime(next_year, next_month, 1)
        return axis

    cursor = datetime(cursor.year, cursor.month, cursor.day)
    while cursor <= end:
        axis.append(_bucket_key(cursor, bucket))
        cursor += timedelta(days=1)
    return axis


def _parse_calendar_month(raw: str | None) -> datetime:
    now = datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
    if raw and YEAR_MONTH_PATTERN.match(raw.strip()):
        year, month = raw.strip().split("-", 1)
        try:
            return datetime(int(year), int(month), 1)
        except ValueError:
            pass
    return datetime(now.year, now.month, 1)


def _shift_month(month_start: datetime, month_delta: int) -> datetime:
    month_index = (month_start.year * 12 + (month_start.month - 1)) + month_delta
    year = month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1)


def _calendar_grid_bounds(month_start: datetime) -> tuple[datetime, datetime, datetime]:
    next_month_start = _shift_month(month_start, 1)
    month_end = next_month_start - timedelta(days=1)

    leading_days = (month_start.weekday() + 1) % 7
    trailing_days = 6 - ((month_end.weekday() + 1) % 7)
    grid_start = month_start - timedelta(days=leading_days)
    grid_end = month_end + timedelta(days=trailing_days)
    return grid_start, month_end, grid_end


def _sum_amount(db: Session, start: datetime, end: datetime, conditions: list | None = None) -> float:
    total = db.execute(
        select(func.coalesce(func.sum(_status_normalized_metric_expr(AqcSaleRecord.amount)), 0)).where(
            *(conditions or []),
            AqcSaleRecord.sold_at >= start,
            AqcSaleRecord.sold_at <= end,
        )
    ).scalar()
    return float(total or 0)


def _calc_uplift(current: float, previous: float) -> float:
    return round(current - previous, 2)


def _calc_average_ticket(amount: float, quantity: int) -> float:
    if quantity <= 0:
        return 0.0
    return round(amount / quantity, 2)


def _build_metrics(db: Session, now: datetime, conditions: list | None = None) -> list[SalesMetricOut]:
    metrics: list[SalesMetricOut] = []
    for key in ("day", "week", "month", "ytd"):
        start, end = _period_window(key, now)
        previous_start, previous_end = _previous_period_window(key, now)
        current_sales = _sum_amount(db, start, end, conditions)
        previous_sales = _sum_amount(db, previous_start, previous_end, conditions)
        metrics.append(
            SalesMetricOut(
                key=key,  # type: ignore[arg-type]
                label=PERIOD_META[key]["label"],
                sales=round(current_sales, 2),
                uplift=_calc_uplift(current_sales, previous_sales),
            )
        )
    return metrics


def _build_y_ticks(max_value: float) -> list[float]:
    if max_value <= 0:
        return [0.0, 250.0, 500.0, 750.0, 1000.0]

    rough_step = max(max_value / 4, 1.0)
    magnitude = 10 ** math.floor(math.log10(rough_step))
    normalized = rough_step / magnitude

    if normalized <= 1:
        step = 1 * magnitude
    elif normalized <= 2:
        step = 2 * magnitude
    elif normalized <= 5:
        step = 5 * magnitude
    else:
        step = 10 * magnitude

    top = step * 4
    while top < max_value:
        top += step
    return [round(step * idx, 2) for idx in range(int(top / step) + 1)]


def _summary_totals(rows: list[AqcSaleRecord]) -> dict[str, float | int]:
    receivable_total = 0.0
    received_total = 0.0
    coupon_total = 0.0
    quantity_total = 0
    order_nums: set[str] = set()

    for row in rows:
        receivable_amount, received_amount, coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        receivable_total += receivable_amount
        received_total += received_amount
        coupon_total += coupon_amount
        quantity_total += quantity
        order_num = _resolve_order_num(row)
        if order_num:
            order_nums.add(order_num)

    discount_total = max(receivable_total - received_total, 0.0)
    return {
        "receivableTotal": round(receivable_total, 2),
        "receivedTotal": round(received_total, 2),
        "couponTotal": round(coupon_total, 2),
        "discountAmountTotal": round(discount_total, 2),
        "averageTicketValue": _calc_average_ticket(received_total, quantity_total),
        "quantityTotal": int(quantity_total),
        "orderCount": int(len(order_nums)),
    }


def _pick_top_group_stats(rows: list[AqcSaleRecord], label_getter) -> dict[str, str | float | int]:
    totals: dict[str, dict[str, float | int]] = {}
    for row in rows:
        label = _clean_text(label_getter(row), 255)
        if not label:
            continue
        bucket = totals.setdefault(label, {"amount": 0.0, "quantity": 0})
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        bucket["amount"] = round(float(bucket["amount"] or 0) + received_amount, 2)
        bucket["quantity"] = int(bucket["quantity"] or 0) + quantity

    if not totals:
        return {"name": "暂无", "amount": 0.0, "quantity": 0}

    top_name, top_stats = sorted(
        totals.items(),
        key=lambda item: (-float(item[1]["amount"] or 0), -int(item[1]["quantity"] or 0), item[0]),
    )[0]
    return {
        "name": top_name,
        "amount": round(float(top_stats["amount"] or 0), 2),
        "quantity": int(top_stats["quantity"] or 0),
    }


def _shop_name_by_id(db: Session, shop_id: int | None) -> str:
    if shop_id is None:
        return ""
    result = db.execute(select(AqcShop.name).where(AqcShop.id == shop_id).limit(1)).scalar_one_or_none()
    return _clean_text(result, 255)


def _resolve_summary_shop_context(
    db: Session,
    *,
    scoped_conditions: list,
    shop_id: int | None = None,
    shop_name: str | None = None,
    salesperson: str | None = None,
) -> tuple[int | None, str]:
    if shop_id is not None:
        return shop_id, _shop_name_by_id(db, shop_id)

    clean_shop_name = _clean_text(shop_name, 255)
    if clean_shop_name:
        return None, clean_shop_name

    clean_salesperson = _clean_text(salesperson, 80)
    if not clean_salesperson:
        return None, ""

    matched_users = _find_salesperson_users(db, clean_salesperson, active_only=False)
    preferred_shop_id = next((int(user.shop_id) for user in matched_users if user.shop_id is not None), None)
    if preferred_shop_id is not None:
        resolved_shop_name = _shop_name_by_id(db, preferred_shop_id)
        if resolved_shop_name:
            return preferred_shop_id, resolved_shop_name

    row = _latest_salesperson_sale_row(db, scoped_conditions=scoped_conditions, salesperson=clean_salesperson)
    if row is None:
        return None, ""
    return row.shop_id, _resolve_shop_name(row)


def _to_date_token(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _build_sale_recommended_period_options(db: Session, *, base_conditions: list, now: datetime) -> list[SalesRecommendedPeriodOptionOut]:
    canonical_options: list[dict[str, str | int | bool]] = []
    for period_key in SALES_RECOMMENDED_PERIOD_KEYS:
        _, start, end, _ = _resolve_account_period_window(period_key, None, None, now)
        count = db.execute(
            select(func.count(AqcSaleRecord.id)).where(
                *base_conditions,
                AqcSaleRecord.sold_at >= start,
                AqcSaleRecord.sold_at <= end,
            )
        ).scalar() or 0
        canonical_options.append({
            "key": period_key,
            "label": SALES_RECOMMENDED_PERIOD_LABELS.get(period_key, period_key),
            "count": int(count),
            "dateFrom": _to_date_token(start),
            "dateTo": _to_date_token(end),
            "recommended": False,
        })

    rank_map = {key: index for index, key in enumerate(SALES_RECOMMENDED_PERIOD_KEYS)}
    recommended_keys = [
        str(item["key"])
        for item in sorted(
            canonical_options,
            key=lambda item: (-int(item["count"]), rank_map.get(str(item["key"]), len(rank_map))),
        )[:3]
    ]

    ordered: list[SalesRecommendedPeriodOptionOut] = []
    seen: set[str] = set()

    for period_key in recommended_keys:
        matched = next((item for item in canonical_options if item["key"] == period_key), None)
        if matched is None:
            continue
        seen.add(period_key)
        ordered.append(SalesRecommendedPeriodOptionOut(**{**matched, "recommended": True}))

    for item in canonical_options:
        period_key = str(item["key"])
        if period_key in seen:
            continue
        ordered.append(SalesRecommendedPeriodOptionOut(**item))

    return ordered


def _summary_champion_labels(period: str, rows: list[AqcSaleRecord]) -> dict[str, object]:
    prefix_map = {
        "yesterday": "昨日",
        "day": "今日",
        "week": "本周",
        "month": "本月",
        "ytd": "本年",
        "range": "时间范围",
    }
    prefix = prefix_map.get(period, "当前")
    top_salesperson = _pick_top_group_stats(rows, _resolve_salesperson)
    top_shop = _pick_top_group_stats(rows, lambda row: simplify_shop_name(_resolve_shop_name(row)))

    return {
        "topSalespersonLabel": f"{prefix}个人销冠",
        "topShopLabel": f"{prefix}店铺销冠",
        "topSalespersonName": str(top_salesperson["name"] or "暂无"),
        "topShopName": str(top_shop["name"] or "暂无"),
        "topSalesperson": top_salesperson,
        "topShop": top_shop,
    }


def _get_sale_record_for_write(db: Session, record_id: int, user: AqcUser) -> AqcSaleRecord | None:
    conditions = [AqcSaleRecord.id == record_id]
    conditions.extend(scoped_sales_conditions(user))
    return (
        db.execute(select(AqcSaleRecord).where(*conditions).limit(1))
        .scalars()
        .first()
    )


def _can_edit_sale_record(user: AqcUser) -> bool:
    return get_aqc_role_key(user) == "aqc_admin"


def _apply_sale_record_payload(
    db: Session,
    *,
    record: AqcSaleRecord | None,
    payload: SaleRecordCreateRequest,
    user: AqcUser,
) -> tuple[dict[str, object] | None, str | None]:
    sale_kind = _normalize_sale_kind(payload.saleKind or (record.sale_kind if record else SALE_KIND_GOODS))
    goods_item: AqcGoodsItem | None = None
    shop: AqcShop | None = None
    ship_shop: AqcShop | None = None
    if sale_kind == SALE_KIND_GOODS and payload.goodsId is not None:
        goods_item = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == payload.goodsId).limit(1)).scalars().first()
        if goods_item is None:
            return None, "所选商品不存在"
    if payload.shopId is not None:
        shop = db.execute(select(AqcShop).where(AqcShop.id == payload.shopId).limit(1)).scalars().first()
        if shop is None:
            return None, "所选销售店铺不存在"
    if payload.shipShopId is not None:
        ship_shop = db.execute(select(AqcShop).where(AqcShop.id == payload.shipShopId).limit(1)).scalars().first()
        if ship_shop is None:
            return None, "所选发货店铺不存在"
    allowed_shop_ids = user_shop_ids(user)
    if allowed_shop_ids and payload.shopId is not None and payload.shopId not in allowed_shop_ids and get_aqc_role_key(user) != "aqc_admin":
        return None, "当前账号不能录入其他销售店铺的销售"
    if allowed_shop_ids and payload.shipShopId is not None and payload.shipShopId not in allowed_shop_ids and get_aqc_role_key(user) != "aqc_admin":
        return None, "当前账号不能选择其他发货店铺"

    sold_at = _parse_sold_at(payload.soldAt)
    salesperson = _resolve_salesperson_name(db, payload.salesperson, user)
    default_shop_id = allowed_shop_ids[0] if allowed_shop_ids else user.shop_id

    if sale_kind == SALE_KIND_REPAIR:
        resolved_shop_id = shop.id if shop else (payload.shopId if payload.shopId is not None else (record.shop_id if record else default_shop_id))
        if resolved_shop_id is None:
            return None, "维修销售请选择销售店铺"

        if shop is None and resolved_shop_id is not None:
            shop = db.execute(select(AqcShop).where(AqcShop.id == int(resolved_shop_id)).limit(1)).scalars().first()
        if shop is None:
            return None, "所选销售店铺不存在"

        receivable_amount = _to_amount(
            payload.receivableAmount
            if payload.receivableAmount is not None
            else (payload.receivedAmount if payload.receivedAmount is not None else payload.amount)
        )
        received_amount = _to_amount(
            payload.receivedAmount
            if payload.receivedAmount is not None
            else (payload.amount if payload.amount is not None else receivable_amount)
        )
        if receivable_amount <= Decimal("0.00"):
            receivable_amount = received_amount
        if receivable_amount <= Decimal("0.00"):
            return None, "请输入正确的实收金额"
        if received_amount <= Decimal("0.00"):
            return None, "请输入正确的实收金额"
        if receivable_amount <= Decimal("0.00") or received_amount >= receivable_amount:
            discount_rate = Decimal("10.00")
        else:
            discount_rate = (received_amount / receivable_amount * Decimal("10")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        _, shop_name = normalize_shop_name(_clean_text(payload.shopName, 255) or _clean_text(shop.name if shop else "", 255))
        if not shop_name and user.assigned_shop is not None:
            _, shop_name = normalize_shop_name(_clean_text(user.assigned_shop.name, 255))
        return {
            "sale_kind": sale_kind,
            "sold_at": sold_at,
            "goods_item": None,
            "goods_code": "",
            "goods_brand": "",
            "goods_series": "",
            "goods_model": "维修销售",
            "goods_barcode": "",
            "unit_price": receivable_amount,
            "receivable_amount": receivable_amount,
            "received_amount": received_amount,
            "coupon_amount": Decimal("0.00"),
            "discount_rate": discount_rate,
            "channel": _clean_text(payload.channel, 50) or "维修",
            "shop_id": resolved_shop_id,
            "shop_name": shop_name,
            "ship_shop_id": None,
            "ship_shop_name": "",
            "salesperson": salesperson,
            "index_key": "维修",
            "customer_name": "",
            "note": (payload.note or "").strip(),
            "quantity": 1,
        }, None

    goods_code = _clean_text(payload.goodsCode, 64) or _clean_text(goods_item.product_code if goods_item else record.goods_code if record else "", 64)
    goods_brand = _clean_text(payload.goodsBrand, 120) or _clean_text(goods_item.brand if goods_item else record.goods_brand if record else "", 120)
    goods_series = _clean_text(payload.goodsSeries, 120) or _clean_text(goods_item.series_name if goods_item else record.goods_series if record else "", 120)
    goods_model = _clean_text(payload.goodsModel, 191) or _clean_text(goods_item.model_name if goods_item else record.goods_model if record else "", 191)
    goods_barcode = _clean_text(payload.goodsBarcode, 64) or _clean_text(goods_item.barcode if goods_item else record.goods_barcode if record else "", 64)
    goods_original_price = goods_item.original_price if goods_item and goods_item.original_price is not None else None
    quantity = max(int(payload.quantity or 1), 1)
    unit_price = _to_amount(
        payload.unitPrice
        if payload.unitPrice is not None
        else (goods_original_price if goods_original_price not in (None, Decimal("0.00")) else (goods_item.price if goods_item else (record.unit_price if record else 0)))
    )
    receivable_amount = _to_amount(
        payload.receivableAmount
        if payload.receivableAmount is not None
        else (unit_price * quantity)
    )
    received_amount = _to_amount(
        payload.receivedAmount
        if payload.receivedAmount is not None
        else (payload.amount if payload.amount is not None else receivable_amount)
    )
    coupon_amount = _to_amount(payload.couponAmount)
    channel = _clean_text(payload.channel, 50) or ("门店" if shop is not None else _clean_text(record.channel if record else "", 50))
    _, shop_name = normalize_shop_name(_clean_text(payload.shopName, 255) or _clean_text(shop.name if shop else "", 255))
    _, ship_shop_name = normalize_shop_name(
        _clean_text(payload.shipShopName, 255)
        or _clean_text(ship_shop.name if ship_shop else "", 255)
        or _clean_text(payload.shopName, 255)
        or _clean_text(shop.name if shop else "", 255)
    )
    if not shop_name and payload.shopId is None and record is not None and record.shop_id is None:
        shop_name = ""
    if not ship_shop_name and payload.shipShopId is None and record is not None and record.ship_shop_id is None:
        ship_shop_name = shop_name
    if not shop_name and shop is None and payload.channel == "门店" and user.assigned_shop is not None:
        _, shop_name = normalize_shop_name(_clean_text(user.assigned_shop.name, 255))
    if not ship_shop_name and ship_shop is None and payload.channel == "门店" and user.assigned_shop is not None:
        _, ship_shop_name = normalize_shop_name(_clean_text(user.assigned_shop.name, 255))

    if receivable_amount <= Decimal("0.00"):
        return None, "请输入正确的应收金额"
    if received_amount <= Decimal("0.00"):
        return None, "请输入正确的实收金额"
    if coupon_amount < Decimal("0.00"):
        return None, "优惠券金额不能小于 0"
    if channel == "门店" and shop is None and payload.shopId is None and not allowed_shop_ids:
        return None, "门店销售请选择销售店铺"

    if receivable_amount <= Decimal("0.00") or received_amount >= receivable_amount:
        discount_rate = Decimal("10.00")
    else:
        discount_rate = (received_amount / receivable_amount * Decimal("10")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    resolved_shop_id = shop.id if shop else (payload.shopId if payload.shopId is not None else (record.shop_id if record else default_shop_id))
    default_ship_shop_id = resolved_shop_id
    resolved_ship_shop_id = (
        ship_shop.id
        if ship_shop
        else (
            payload.shipShopId
            if payload.shipShopId is not None
            else (record.ship_shop_id if record and record.ship_shop_id is not None else default_ship_shop_id)
        )
    )
    if channel != "门店" and payload.shopId is None:
        resolved_shop_id = None
        if not payload.shopName:
            shop_name = ""
    if channel != "门店" and payload.shipShopId is None:
        resolved_ship_shop_id = None
        if not payload.shipShopName:
            ship_shop_name = ""

    return {
        "sale_kind": sale_kind,
        "sold_at": sold_at,
        "goods_item": goods_item,
        "goods_code": goods_code,
        "goods_brand": goods_brand,
        "goods_series": goods_series,
        "goods_model": goods_model,
        "goods_barcode": goods_barcode,
        "unit_price": unit_price,
        "receivable_amount": receivable_amount,
        "received_amount": received_amount,
        "coupon_amount": coupon_amount,
        "discount_rate": discount_rate,
        "channel": channel,
        "shop_id": resolved_shop_id,
        "shop_name": shop_name,
        "ship_shop_id": resolved_ship_shop_id,
        "ship_shop_name": ship_shop_name,
        "salesperson": salesperson,
        "index_key": _normalize_sale_index_key(goods_series, goods_brand, goods_model),
        "customer_name": _clean_text(payload.customerName, 120),
        "note": (payload.note or "").strip(),
        "quantity": quantity,
    }, None


def _sync_sale_inventory(
    db: Session,
    *,
    before_goods: AqcGoodsItem | None,
    before_shop: AqcShop | None,
    before_quantity: int,
    after_goods: AqcGoodsItem | None,
    after_shop: AqcShop | None,
    after_quantity: int,
    operator: AqcUser | None,
    change_prefix: str,
    order_num: str,
    related_type: str,
    related_id: int | None,
) -> None:
    actor_name = inventory_actor_name(operator)
    if (
        before_goods is not None
        and after_goods is not None
        and before_shop is not None
        and after_shop is not None
        and int(before_goods.id or 0) == int(after_goods.id or 0)
        and int(before_shop.id or 0) == int(after_shop.id or 0)
    ):
        delta = int(before_quantity or 0) - int(after_quantity or 0)
        if delta == 0:
            return
        apply_inventory_delta(
            db,
            goods_item=after_goods,
            shop=after_shop,
            delta=delta,
            change_content=f"{change_prefix}调整：订单 {order_num}",
            operator_id=operator.id if operator is not None else None,
            operator_name=actor_name,
            related_type=related_type,
            related_id=related_id,
        )
        db.flush()
        recalculate_goods_stock(db, [int(after_goods.id)])
        return
    if before_goods is not None and before_shop is not None and before_quantity:
        apply_inventory_delta(
            db,
            goods_item=before_goods,
            shop=before_shop,
            delta=int(before_quantity),
            change_content=f"{change_prefix}回补：订单 {order_num}",
            operator_id=operator.id if operator is not None else None,
            operator_name=actor_name,
            related_type=related_type,
            related_id=related_id,
        )
    if after_goods is not None and after_shop is not None and after_quantity:
        apply_inventory_delta(
            db,
            goods_item=after_goods,
            shop=after_shop,
            delta=-int(after_quantity),
            change_content=f"{change_prefix}扣减：订单 {order_num}",
            operator_id=operator.id if operator is not None else None,
            operator_name=actor_name,
            related_type=related_type,
            related_id=related_id,
        )
    touched_goods_ids = {
        int(item.id)
        for item in (before_goods, after_goods)
        if item is not None and item.id is not None
    }
    if touched_goods_ids:
        db.flush()
        recalculate_goods_stock(db, sorted(touched_goods_ids))


@router.post("/records", response_model=MessageResponse)
def create_sale_record(
    payload: SaleRecordCreateRequest,
    user: AqcUser = Depends(require_permissions("sales.write")),
    db: Session = Depends(get_db),
):
    resolved, error = _apply_sale_record_payload(db, record=None, payload=payload, user=user)
    if error or resolved is None:
        return {"success": False, "message": error or "销售数据无效"}

    order_num = _clean_text(payload.orderNum, 32) or _generate_sale_order_num(db, resolved["sold_at"])
    existing_order_num = db.execute(select(AqcSaleRecord.id).where(AqcSaleRecord.order_num == order_num).limit(1)).scalar()
    if existing_order_num is not None:
        order_num = _generate_sale_order_num(db, resolved["sold_at"])

    record = AqcSaleRecord(
        sold_at=resolved["sold_at"],
        sale_kind=str(resolved["sale_kind"]),
        order_num=order_num,
        goods_id=resolved["goods_item"].id if resolved["goods_item"] else None,
        goods_code=resolved["goods_code"],
        goods_brand=resolved["goods_brand"],
        goods_series=resolved["goods_series"],
        goods_model=resolved["goods_model"],
        goods_barcode=resolved["goods_barcode"],
        unit_price=resolved["unit_price"],
        receivable_amount=resolved["receivable_amount"],
        amount=resolved["received_amount"],
        coupon_amount=resolved["coupon_amount"],
        discount_rate=resolved["discount_rate"],
        quantity=int(resolved["quantity"]),
        channel=resolved["channel"],
        sale_status="normal",
        shop_id=resolved["shop_id"],
        shop_name=resolved["shop_name"] or (user.assigned_shop.name if user.assigned_shop and resolved["shop_id"] else ""),
        ship_shop_id=resolved["ship_shop_id"],
        ship_shop_name=resolved["ship_shop_name"] or (resolved["shop_name"] or ""),
        salesperson=resolved["salesperson"],
        index_key=resolved["index_key"],
        customer_name=resolved["customer_name"],
        note=resolved["note"],
        created_by=user.id,
    )
    db.add(record)
    db.flush()
    target_shop = (
        db.execute(select(AqcShop).where(AqcShop.id == int(resolved["ship_shop_id"])).limit(1)).scalars().first()
        if resolved["ship_shop_id"] is not None
        else None
    )
    _sync_sale_inventory(
        db,
        before_goods=None,
        before_shop=None,
        before_quantity=0,
        after_goods=resolved["goods_item"],
        after_shop=target_shop,
        after_quantity=int(resolved["quantity"] or 0),
        operator=user,
        change_prefix="销售录入",
        order_num=order_num,
        related_type="sale_record",
        related_id=int(record.id),
    )
    db.commit()
    return {"success": True, "message": f"销售录入成功，订单号 {order_num}"}


@router.post("/template-import", response_model=SalesTemplateImportResponse)
async def import_sale_records_from_template(
    request: Request,
    dry_run: bool = Query(default=False),
    x_file_name: str | None = Header(default=None, alias="X-File-Name"),
    user: AqcUser = Depends(require_permissions("sales.write")),
    db: Session = Depends(get_db),
):
    role_key = get_aqc_role_key(user)
    allowed_shop_scope = None if role_key == "aqc_admin" else user_shop_ids(user)
    if role_key != "aqc_admin" and not allowed_shop_scope:
        return {"success": False, "message": "当前账号未配置可导入的门店范围", "stats": {}}

    filename = unquote((x_file_name or "").strip()) or "sales-template.xlsx"
    if Path(filename).suffix.lower() != ".xlsx":
        return {"success": False, "message": "仅支持上传 .xlsx 销售表", "stats": {}}

    content = await request.body()
    if not content:
        return {"success": False, "message": "上传内容为空，请重新选择销售表", "stats": {}}

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            tmp_file.write(content)
            temp_path = tmp_file.name

        if dry_run:
            stats, _ = inspect_sales_template_import(db, temp_path, allowed_shop_ids=allowed_shop_scope)
            has_issues = bool(stats.get("unmatchedGoods") or stats.get("unmatchedShops") or stats.get("outOfScopeShops"))
            return {
                "success": not has_issues,
                "message": _sales_template_import_message(stats, dry_run=True),
                "stats": stats,
            }

        stats = import_sales_template(
            db,
            temp_path,
            creator_id=user.id,
            creator_name=inventory_actor_name(user),
            allowed_shop_ids=allowed_shop_scope,
        )
        db.commit()
        return {
            "success": True,
            "message": _sales_template_import_message(stats, dry_run=False),
            "stats": stats,
        }
    except ValueError as exc:
        db.rollback()
        try:
            stats, _ = inspect_sales_template_import(db, temp_path, allowed_shop_ids=allowed_shop_scope)
        except Exception:
            stats = {}
        return {"success": False, "message": str(exc), "stats": stats}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"销售表导入失败：{exc}", "stats": {}}
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


@router.put("/records/{record_id}", response_model=MessageResponse)
def update_sale_record(
    record_id: int,
    payload: SaleRecordCreateRequest,
    user: AqcUser = Depends(require_permissions("sales.write")),
    db: Session = Depends(get_db),
):
    if not _can_edit_sale_record(user):
        return {"success": False, "message": "当前账号无权编辑销售记录"}
    record = _get_sale_record_for_write(db, record_id, user)
    if record is None:
        return {"success": False, "message": "销售记录不存在"}
    if _clean_text(record.sale_status, 20) != "normal":
        return {"success": False, "message": "退货关联销售记录不能编辑"}

    resolved, error = _apply_sale_record_payload(db, record=record, payload=payload, user=user)
    if error or resolved is None:
        return {"success": False, "message": error or "销售数据无效"}

    previous_goods = (
        db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == int(record.goods_id)).limit(1)).scalars().first()
        if record.goods_id is not None
        else None
    )
    previous_shop = (
        db.execute(select(AqcShop).where(AqcShop.id == int(record.ship_shop_id or record.shop_id)).limit(1)).scalars().first()
        if (record.ship_shop_id is not None or record.shop_id is not None)
        else None
    )
    previous_quantity = int(record.quantity or 0)
    record.sold_at = resolved["sold_at"]
    record.sale_kind = str(resolved["sale_kind"])
    record.goods_id = resolved["goods_item"].id if resolved["goods_item"] else None
    record.goods_code = resolved["goods_code"]
    record.goods_brand = resolved["goods_brand"]
    record.goods_series = resolved["goods_series"]
    record.goods_model = resolved["goods_model"]
    record.goods_barcode = resolved["goods_barcode"]
    record.unit_price = resolved["unit_price"]
    record.receivable_amount = resolved["receivable_amount"]
    record.amount = resolved["received_amount"]
    record.coupon_amount = resolved["coupon_amount"]
    record.discount_rate = resolved["discount_rate"]
    record.quantity = int(resolved["quantity"])
    record.channel = resolved["channel"]
    record.shop_id = resolved["shop_id"]
    record.shop_name = resolved["shop_name"]
    record.ship_shop_id = resolved["ship_shop_id"]
    record.ship_shop_name = resolved["ship_shop_name"]
    record.salesperson = resolved["salesperson"]
    record.index_key = resolved["index_key"]
    record.customer_name = resolved["customer_name"]
    record.note = resolved["note"]
    db.flush()
    next_shop = (
        db.execute(select(AqcShop).where(AqcShop.id == int(record.ship_shop_id or record.shop_id)).limit(1)).scalars().first()
        if (record.ship_shop_id is not None or record.shop_id is not None)
        else None
    )
    _sync_sale_inventory(
        db,
        before_goods=previous_goods,
        before_shop=previous_shop,
        before_quantity=previous_quantity,
        after_goods=resolved["goods_item"],
        after_shop=next_shop,
        after_quantity=int(resolved["quantity"] or 0),
        operator=user,
        change_prefix="销售修改",
        order_num=record.order_num,
        related_type="sale_record",
        related_id=int(record.id),
    )
    db.commit()
    return {"success": True, "message": f"销售记录已更新，订单号 {record.order_num}"}


@router.get("/meta", response_model=SaleRecordMetaResponse)
def sale_record_meta(
    sale_kind: str = Query(default=SALE_KIND_GOODS),
    record_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    order_num: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    shop_id: int | None = Query(default=None, ge=1),
    shop_name: str | None = None,
    salesperson: str | None = None,
    sale_status: str | None = None,
    index_key: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    conditions = _build_sale_conditions(
        db,
        sale_kind=sale_kind,
        record_id=record_id,
        keyword=q or "",
        order_num=order_num,
        brand=brand,
        series=series,
        model=model,
        shop_id=shop_id,
        shop_name=shop_name,
        salesperson=salesperson,
        sale_status=sale_status,
        index_key=index_key,
        date_from=date_from,
        date_to=date_to,
    )
    conditions.extend(scoped_sales_conditions(user))
    recommended_period_conditions = _build_sale_conditions(
        db,
        sale_kind=sale_kind,
        record_id=record_id,
        keyword=q or "",
        order_num=order_num,
        brand=brand,
        series=series,
        model=model,
        shop_id=shop_id,
        shop_name=shop_name,
        salesperson=salesperson,
        sale_status=sale_status,
        index_key=index_key,
    )
    recommended_period_conditions.extend(scoped_sales_conditions(user))

    total_items = db.execute(select(func.count(AqcSaleRecord.id)).where(*conditions)).scalar() or 0

    def build_options(column, *, empty_value: str = ""):
        rows = db.execute(
            select(column, func.count(AqcSaleRecord.id))
            .where(*conditions, column != empty_value)
            .group_by(column)
            .order_by(func.count(AqcSaleRecord.id).desc(), column.asc())
            .limit(200)
        ).all()
        return [
            SalesFilterOptionOut(value=str(value or "").strip(), label=str(value or "").strip(), count=int(count or 0))
            for value, count in rows
            if str(value or "").strip()
        ]

    index_rows = db.execute(
        select(AqcSaleRecord.index_key, func.count(AqcSaleRecord.id))
        .where(*conditions, AqcSaleRecord.index_key != "")
        .group_by(AqcSaleRecord.index_key)
        .order_by(AqcSaleRecord.index_key.asc())
    ).all()
    index_options = [
        SalesIndexOptionOut(key=str(key or "").strip(), count=int(count or 0))
        for key, count in index_rows
        if str(key or "").strip()
    ]
    recommended_period_options = _build_sale_recommended_period_options(
        db,
        base_conditions=recommended_period_conditions,
        now=datetime.now(SHANGHAI_TZ).replace(tzinfo=None),
    )

    return {
        "success": True,
        "totalItems": int(total_items),
        "brandOptions": build_options(AqcSaleRecord.goods_brand),
        "seriesOptions": build_options(AqcSaleRecord.goods_series),
        "shopOptions": build_options(AqcSaleRecord.shop_name),
        "salespersonOptions": build_options(AqcSaleRecord.salesperson),
        "indexOptions": index_options,
        "recommendedPeriodOptions": recommended_period_options,
    }


@router.get("/records", response_model=SaleRecordListResponse)
def list_sale_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sale_kind: str = Query(default=SALE_KIND_GOODS),
    record_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    order_num: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    shop_id: int | None = Query(default=None, ge=1),
    shop_name: str | None = None,
    salesperson: str | None = None,
    sale_status: str | None = None,
    index_key: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_field: str = Query(default="sold_at"),
    sort_order: str = Query(default="desc"),
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    conditions = _build_sale_conditions(
        db,
        sale_kind=sale_kind,
        record_id=record_id,
        keyword=q or "",
        order_num=order_num,
        brand=brand,
        series=series,
        model=model,
        shop_id=shop_id,
        shop_name=shop_name,
        salesperson=salesperson,
        sale_status=sale_status,
        index_key=index_key,
        date_from=date_from,
        date_to=date_to,
    )
    conditions.extend(scoped_sales_conditions(user))
    sort_key = _normalize_sort_field(sort_field)
    sort_direction = _normalize_sort_order(sort_order)
    sort_column = SALE_SORT_FIELD_MAP[sort_key]
    sort_clause = sort_column.asc() if sort_direction == "asc" else sort_column.desc()

    total = db.execute(select(func.count(AqcSaleRecord.id)).where(*conditions)).scalar() or 0
    rows = (
        db.execute(
            select(AqcSaleRecord)
            .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
            .where(*conditions)
            .order_by(sort_clause, AqcSaleRecord.sold_at.desc(), AqcSaleRecord.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    records = [_to_sale_out(item) for item in rows]
    return {"success": True, "total": int(total), "records": records}


@router.delete("/records/{record_id}", response_model=MessageResponse)
def delete_sale_record(
    record_id: int,
    user: AqcUser = Depends(require_permissions("sales.manage")),
    db: Session = Depends(get_db),
):
    record = db.execute(select(AqcSaleRecord).where(AqcSaleRecord.id == record_id).limit(1)).scalars().first()
    if record is None:
        return {"success": False, "message": "销售记录不存在"}
    if _clean_text(record.sale_status, 20) != "normal":
        return {"success": False, "message": "退货关联销售记录不能删除"}
    goods_item = (
        db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == int(record.goods_id)).limit(1)).scalars().first()
        if record.goods_id is not None
        else None
    )
    shop = (
        db.execute(select(AqcShop).where(AqcShop.id == int(record.ship_shop_id or record.shop_id)).limit(1)).scalars().first()
        if (record.ship_shop_id is not None or record.shop_id is not None)
        else None
    )
    _sync_sale_inventory(
        db,
        before_goods=goods_item,
        before_shop=shop,
        before_quantity=int(record.quantity or 0),
        after_goods=None,
        after_shop=None,
        after_quantity=0,
        operator=user,
        change_prefix="销售删除",
        order_num=record.order_num,
        related_type="sale_record",
        related_id=int(record.id),
    )
    db.delete(record)
    db.commit()
    return {"success": True, "message": "销售记录已删除"}


@router.get("/summary", response_model=SalesSummaryResponse)
def sales_summary(
    period: str = Query(default="day"),
    sale_kind: str = Query(default=SALE_KIND_GOODS),
    record_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    order_num: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    shop_id: int | None = Query(default=None, ge=1),
    shop_name: str | None = None,
    salesperson: str | None = None,
    index_key: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    now = datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
    base_conditions = _build_sale_conditions(
        db,
        sale_kind=sale_kind,
        record_id=record_id,
        keyword=q or "",
        order_num=order_num,
        brand=brand,
        series=series,
        model=model,
        shop_id=shop_id,
        shop_name=shop_name,
        salesperson=salesperson,
        index_key=index_key,
    )
    conditions = [*base_conditions, *scoped_sales_conditions(user)]

    custom_range = _resolve_summary_custom_range(date_from, date_to)
    if custom_range is not None:
        start, end = custom_range
        period_key = "range"
        metric_label = "时间范围"
        title = f"{_format_summary_range_label(start, end)} 销售额"
        bucket = _resolve_range_bucket(start, end)
        previous_start, previous_end = _previous_custom_range_window(start, end)
    else:
        period_key = _normalize_period(period)
        meta = PERIOD_META[period_key]
        start, end = _period_window(period_key, now)
        metric_label = meta["label"]
        title = meta["title"]
        bucket = meta["bucket"]
        previous_start, previous_end = _previous_period_window(period_key, now)

    rows = (
        db.execute(
            select(AqcSaleRecord)
            .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
            .where(*conditions, AqcSaleRecord.sold_at >= start, AqcSaleRecord.sold_at <= end)
            .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
    )
        .scalars()
        .all()
    )

    axis = _build_bucket_axis(start, end, bucket)
    amount_by_bucket = {item: 0.0 for item in axis}
    quantity_by_bucket = {item: 0 for item in axis}

    for row in rows:
        key = _bucket_key(row.sold_at, bucket)
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        if key in amount_by_bucket:
            amount_by_bucket[key] += received_amount
            quantity_by_bucket[key] += quantity

    running_total = 0.0
    points: list[SalesPointOut] = []
    for key in axis:
        running_total += amount_by_bucket[key]
        points.append(
            SalesPointOut(
                x=key,
                y=round(running_total, 2),
                segmentSales=round(amount_by_bucket[key], 2),
                quantity=int(quantity_by_bucket[key]),
            )
        )

    current_sales = round(running_total, 2)
    previous_sales = _sum_amount(db, previous_start, previous_end, conditions)
    uplift = _calc_uplift(current_sales, previous_sales)

    metrics = (
        [
            SalesMetricOut(
                key="range",
                label=metric_label,
                sales=current_sales,
                uplift=uplift,
            ),
        ]
        if period_key == "range"
        else _build_metrics(db, now, conditions)
    )
    y_ticks = _build_y_ticks(max((point.y for point in points), default=0.0))
    totals = _summary_totals(rows)
    champion_period = period_key
    champion_rows = rows
    if period_key == "day":
        champion_period = "yesterday"
        champion_rows = (
            db.execute(
                select(AqcSaleRecord)
                .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
                .where(*conditions, AqcSaleRecord.sold_at >= previous_start, AqcSaleRecord.sold_at <= previous_end)
                .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
            )
            .scalars()
            .all()
        )
    champions = _summary_champion_labels(champion_period, champion_rows)

    return {
        "success": True,
        "period": period_key,
        "title": title,
        "sales": current_sales,
        "uplift": uplift,
        **totals,
        **champions,
        "metrics": metrics,
        "points": points,
        "xTicks": axis,
        "yTicks": y_ticks,
    }


@router.get("/account-performance", response_model=AccountPerformanceResponse)
def account_performance(
    scope: str = Query(default="shop"),
    period: str = Query(default="this_month"),
    date_from: str | None = None,
    date_to: str | None = None,
    commission_period: str | None = Query(default=None),
    commission_date_from: str | None = None,
    commission_date_to: str | None = None,
    commission_rate: float | None = Query(default=None, ge=0, le=1),
    ranking_period: str | None = Query(default=None),
    ranking_date_from: str | None = None,
    ranking_date_to: str | None = None,
    user: AqcUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
    commission_period_key, commission_start, commission_end, commission_period_label = _resolve_account_period_window(
        commission_period or period,
        commission_date_from or date_from,
        commission_date_to or date_to,
        now,
    )
    ranking_period_key, ranking_start, ranking_end, ranking_period_label = _resolve_account_period_window(
        ranking_period or period,
        ranking_date_from or date_from,
        ranking_date_to or date_to,
        now,
    )
    date_from_label = commission_start.strftime("%Y-%m-%d")
    date_to_label = commission_end.strftime("%Y-%m-%d")

    current_user_candidates = set(_current_user_salesperson_candidates(user))
    current_role_key = get_aqc_role_key(user)
    if current_role_key == "aqc_departed":
        own_sales_amount = 0.0
    else:
        own_rows = (
            db.execute(
                select(AqcSaleRecord)
                .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
                .where(
                    AqcSaleRecord.salesperson.in_(sorted(current_user_candidates)) if current_user_candidates else false(),
                    AqcSaleRecord.sold_at >= commission_start,
                    AqcSaleRecord.sold_at <= commission_end,
                )
                .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
            )
            .scalars()
            .all()
        )
        own_sales_amount = round(
            sum(
                _sale_metric_snapshot(row)[1]
                for row in own_rows
                if _clean_text(_resolve_salesperson(row), 80) in current_user_candidates
            ),
            2,
        )
    resolved_commission_rate = max(0.0, min(float(commission_rate if commission_rate is not None else 0.02), 1.0))
    commission_amount = round(own_sales_amount * resolved_commission_rate, 2)

    ranking_conditions = [] if current_role_key != "aqc_departed" else [false()]
    resolved_scope = "shop" if str(scope or "").strip().lower() == "shop" else "company"
    scope_shop_id = None
    scope_shop_name = ""
    if resolved_scope == "shop":
        scope_shop_id, scope_shop_name = _resolve_account_rank_shop_context(db, user, ranking_conditions)
        if scope_shop_id is not None and scope_shop_name:
            ranking_conditions.append(or_(AqcSaleRecord.shop_id == scope_shop_id, AqcSaleRecord.shop_name == scope_shop_name))
        elif scope_shop_id is not None:
            ranking_conditions.append(AqcSaleRecord.shop_id == scope_shop_id)
        elif scope_shop_name:
            ranking_conditions.append(AqcSaleRecord.shop_name == scope_shop_name)
        else:
            resolved_scope = "company"

    ranking_rows = (
        db.execute(
            select(AqcSaleRecord)
            .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
            .where(*ranking_conditions, AqcSaleRecord.sold_at >= ranking_start, AqcSaleRecord.sold_at <= ranking_end)
            .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
        )
        .scalars()
        .all()
    )
    ranking_items = _aggregate_salesperson_rankings(ranking_rows)
    current_display_name = _clean_text(user.display_name or user.username, 80) or "我"
    current_entry = next((item for item in ranking_items if item.name in current_user_candidates), None)
    current_rank = int(current_entry.rank) if current_entry is not None else 0
    current_index = current_rank - 1 if current_rank > 0 else -1
    previous_entry = ranking_items[current_index - 1] if current_index > 0 else None
    next_entry = ranking_items[current_index + 1] if current_index >= 0 and current_index + 1 < len(ranking_items) else None
    if current_entry is None:
        current_entry = AccountPerformanceRankItemOut(rank=0, name=current_display_name, amount=round(own_sales_amount, 2), quantity=0)

    formula_prefix = commission_period_label if commission_period_key != "range" else "时间范围"
    return {
        "success": True,
        "period": commission_period_key,
        "periodLabel": commission_period_label,
        "rangeLabel": _format_summary_range_label(commission_start, commission_end),
        "commissionPeriod": commission_period_key,
        "commissionPeriodLabel": commission_period_label,
        "commissionRangeLabel": _format_summary_range_label(commission_start, commission_end),
        "rankingPeriod": ranking_period_key,
        "rankingPeriodLabel": ranking_period_label,
        "rankingRangeLabel": _format_summary_range_label(ranking_start, ranking_end),
        "dateFrom": date_from_label,
        "dateTo": date_to_label,
        "employmentDate": getattr(user, "employment_date", None),
        "joinedDays": _compute_joined_days(getattr(user, "employment_date", None), now),
        "commissionRate": resolved_commission_rate,
        "salesAmount": own_sales_amount,
        "commissionAmount": commission_amount,
        "formulaText": f"{formula_prefix}销售额 ¥ {own_sales_amount:.2f} × {_format_commission_rate_label(resolved_commission_rate)}",
        "rankScope": resolved_scope,
        "rankScopeLabel": "店铺内排名" if resolved_scope == "shop" else "全公司排名",
        "shopName": scope_shop_name,
        "currentRank": current_rank,
        "rankingCount": len(ranking_items),
        "currentEntry": current_entry,
        "previousEntry": previous_entry,
        "nextEntry": next_entry,
        "rankings": ranking_items,
    }


@router.get("/calendar", response_model=SalesCalendarResponse)
def sales_calendar(
    month: str | None = None,
    sale_kind: str = Query(default=SALE_KIND_GOODS),
    record_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    order_num: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    shop_id: int | None = Query(default=None, ge=1),
    shop_name: str | None = None,
    salesperson: str | None = None,
    index_key: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    normalized_sale_kind = _normalize_sale_kind(sale_kind)
    month_start = _parse_calendar_month(month)
    grid_start, month_end, grid_end = _calendar_grid_bounds(month_start)
    grid_end_with_time = grid_end.replace(hour=23, minute=59, second=59, microsecond=999999)

    conditions = _build_sale_conditions(
        db,
        sale_kind=sale_kind,
        record_id=record_id,
        keyword=q or "",
        order_num=order_num,
        brand=brand,
        series=series,
        model=model,
        shop_id=shop_id,
        shop_name=shop_name,
        salesperson=salesperson,
        index_key=index_key,
        date_from=date_from,
        date_to=date_to,
    )
    conditions.extend(scoped_sales_conditions(user))

    rows = (
        db.execute(
            select(AqcSaleRecord)
            .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
            .where(
                *conditions,
                AqcSaleRecord.sold_at >= grid_start,
                AqcSaleRecord.sold_at <= grid_end_with_time,
            )
            .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
        )
        .scalars()
        .all()
    )

    amount_map: dict[str, float] = {}
    quantity_map: dict[str, int] = {}
    breakdown_mode = ""
    breakdown_title = ""
    if salesperson and str(salesperson).strip():
        breakdown_mode = ""
        breakdown_title = ""
    elif (shop_name and str(shop_name).strip()) or shop_id is not None:
        breakdown_mode = "salesperson"
        breakdown_title = "销售员销售额"
    else:
        breakdown_mode = "shop"
        breakdown_title = "门店销售额"
    breakdown_map: dict[str, dict[str, dict[str, object]]] = {}
    for row in rows:
        day_key = row.sold_at.strftime("%Y-%m-%d")
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        amount_map[day_key] = round(amount_map.get(day_key, 0.0) + received_amount, 2)
        quantity_map[day_key] = quantity_map.get(day_key, 0) + quantity
        if breakdown_mode == "shop":
            label = _resolve_shop_name(row)
        elif breakdown_mode == "salesperson":
            label = _resolve_salesperson(row)
        else:
            label = ""
        if label:
            day_breakdowns = breakdown_map.setdefault(day_key, {})
            current = day_breakdowns.setdefault(
                label,
                {
                    "amount": 0.0,
                    "quantity": 0,
                    "orderNums": set(),
                    "drilldownTitle": "店铺内销售员统计" if breakdown_mode == "shop" else "",
                    "drilldowns": {},
                },
            )
            current["amount"] = round(float(current["amount"]) + received_amount, 2)
            current["quantity"] = int(current["quantity"]) + quantity
            order_num = _resolve_order_num(row)
            if order_num:
                type_cast(set, current["orderNums"]).add(order_num)

            if breakdown_mode == "shop":
                detail_label = _resolve_salesperson(row) or "未分配销售员"
                drilldowns = type_cast(dict[str, dict[str, object]], current["drilldowns"])
                detail = drilldowns.setdefault(
                    detail_label,
                    {"amount": 0.0, "quantity": 0, "orderNums": set(), "entries": {}},
                )
                detail["amount"] = round(float(detail["amount"]) + received_amount, 2)
                detail["quantity"] = int(detail["quantity"]) + quantity
                if order_num:
                    type_cast(set, detail["orderNums"]).add(order_num)
                entry_label = _resolve_calendar_person_entry_label(row)
                entries = type_cast(dict[str, dict[str, object]], detail["entries"])
                entry = entries.setdefault(entry_label, {"amount": 0.0, "quantity": 0, "orderNums": set()})
                entry["amount"] = round(float(entry["amount"]) + received_amount, 2)
                entry["quantity"] = int(entry["quantity"]) + quantity
                if order_num:
                    type_cast(set, entry["orderNums"]).add(order_num)

    today = datetime.now(SHANGHAI_TZ).date()
    days = []
    cursor = grid_start
    total_amount = 0.0
    total_quantity = 0
    active_days = 0

    while cursor <= grid_end:
        key = cursor.strftime("%Y-%m-%d")
        amount = round(amount_map.get(key, 0.0), 2)
        quantity = int(quantity_map.get(key, 0))
        average_ticket = _calc_average_ticket(amount, quantity)
        is_current_month = cursor.year == month_start.year and cursor.month == month_start.month

        if is_current_month:
            total_amount += amount
            total_quantity += quantity
            if amount != 0 or quantity != 0:
                active_days += 1

        days.append(
            {
                "date": key,
                "day": cursor.day,
                "amount": amount,
                "quantity": quantity,
                "averageTicketValue": average_ticket,
                "isCurrentMonth": is_current_month,
                "isToday": cursor.date() == today,
                "breakdownMode": breakdown_mode,
                "breakdownTitle": breakdown_title,
                "breakdowns": [
                    SalesCalendarBreakdownOut(
                        label=label,
                        amount=round(float(stats.get("amount") or 0), 2),
                        quantity=int(stats.get("quantity") or 0),
                        averageTicketValue=_calc_average_ticket(
                            round(float(stats.get("amount") or 0), 2),
                            int(stats.get("quantity") or 0),
                        ),
                        orderCount=len(type_cast(set, stats.get("orderNums") or set())),
                        drilldownTitle=str(stats.get("drilldownTitle") or ""),
                        drilldowns=[
                            SalesCalendarDrilldownItemOut(
                                label=detail_label,
                                amount=round(float(detail_stats.get("amount") or 0), 2),
                                quantity=int(detail_stats.get("quantity") or 0),
                                averageTicketValue=_calc_average_ticket(
                                    round(float(detail_stats.get("amount") or 0), 2),
                                    int(detail_stats.get("quantity") or 0),
                                ),
                                orderCount=len(type_cast(set, detail_stats.get("orderNums") or set())),
                                entries=_build_calendar_person_entries_from_map(
                                    type_cast(dict[str, dict[str, object]], detail_stats.get("entries") or {}),
                                    sale_kind=normalized_sale_kind,
                                ),
                            )
                            for detail_label, detail_stats in sorted(
                                type_cast(dict[str, dict[str, object]], stats.get("drilldowns") or {}).items(),
                                key=lambda item: (-float(item[1].get("amount") or 0), item[0]),
                            )
                        ],
                    )
                    for label, stats in sorted(
                        breakdown_map.get(key, {}).items(),
                        key=lambda item: (-float(item[1].get("amount") or 0), item[0]),
                    )
                ],
            }
        )
        cursor += timedelta(days=1)

    return {
        "success": True,
        "month": month_start.strftime("%Y-%m"),
        "monthLabel": month_start.strftime("%Y年%m月"),
        "totalAmount": round(total_amount, 2),
        "totalQuantity": int(total_quantity),
        "activeDays": int(active_days),
        "days": days,
    }

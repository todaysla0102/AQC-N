from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Event, Thread
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import SessionLocal, get_db
from ..deps import get_aqc_role_key, require_permissions, to_iso, user_shop_ids
from ..models import (
    AqcGoodsInventory,
    AqcInventoryLog,
    AqcNotification,
    AqcReportLog,
    AqcReportSetting,
    AqcSaleRecord,
    AqcShop,
    AqcShopTargetMonth,
    AqcUser,
    AqcWorkOrder,
    AqcWorkOrderItem,
)
from .sales import _resolve_salesperson, _sale_metric_snapshot
from .work_orders import DRAFT_STATUSES, WORK_ORDER_TYPES


router = APIRouter(prefix="/reports", tags=["reports"])

SHANGHAI_TZ_NAME = "Asia/Shanghai"
REPORT_PERIOD_LABELS = {
    "day": "日报",
    "week": "周报",
    "month": "月报",
}
REPORT_RECIPIENT_ROLE_KEYS = ("aqc_admin", "aqc_manager", "aqc_sales", "aqc_engineer")
REPORT_SETTING_DEFAULT_ROLE_KEYS = ("aqc_admin", "aqc_manager", "aqc_sales")
REPORT_SCOPE_COMPANY = "company"
REPORT_SCOPE_SHOP = "shop"
REPORT_SCOPE_USER = "user"
REPORT_NOTIFICATION_TYPE = "report_delivery"
REPORT_DISABLED_SHOP_NAMES = {"aqc flow"}
REPORT_SHOP_TYPE_STORE = 0
REPORT_SHOP_TYPE_WAREHOUSE = 1
REPORT_SHOP_TYPE_OTHER_WAREHOUSE = 2
REPORT_SHOP_TYPE_REPAIR = 3
REPORT_RUNNER_STOP = Event()
REPORT_RUNNER_STARTED = False
SHANGHAI_TZ = ZoneInfo(SHANGHAI_TZ_NAME)


def _now() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(tzinfo=None)


def _clean_text(value: object | None, limit: int = 255) -> str:
    return str(value or "").strip()[:limit]


def _json_loads(raw_value: str | None, fallback):
    try:
        parsed = json.loads(raw_value or "")
    except Exception:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _normalize_role_keys(values: list[object] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        key = _clean_text(item, 40).lower()
        if key not in REPORT_RECIPIENT_ROLE_KEYS or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _normalize_user_ids(values: list[object] | None) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for item in values or []:
        try:
            user_id = int(item)
        except Exception:
            continue
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        result.append(user_id)
    return result


def _period_key_label(period_key: str) -> str:
    return REPORT_PERIOD_LABELS.get(_clean_text(period_key, 20), "报告")


def _time_gate(now: datetime, hour: int, minute: int) -> bool:
    return (now.hour, now.minute) >= (int(hour), int(minute))


def _normalize_weekday(value: object | None, *, default: int = 0) -> int:
    try:
        weekday = int(value)
    except Exception:
        return default
    return weekday if 0 <= weekday <= 6 else default


def _normalize_day_of_month(value: object | None, *, default: int = 1) -> int:
    try:
        day_value = int(value)
    except Exception:
        return default
    return day_value if 1 <= day_value <= 31 else default


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def _day_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, value.day)


def _week_start(value: datetime) -> datetime:
    base = _day_start(value)
    return base - timedelta(days=base.weekday())


def _next_month_start(value: datetime) -> datetime:
    if value.month == 12:
        return datetime(value.year + 1, 1, 1)
    return datetime(value.year, value.month + 1, 1)


def _effective_day_of_month(now: datetime, configured_day: int) -> int:
    current_month_start = _month_start(now)
    current_month_end = _next_month_start(current_month_start) - timedelta(days=1)
    return min(_normalize_day_of_month(configured_day, default=1), current_month_end.day)


def _period_schedule_due(
    now: datetime,
    period_key: str,
    *,
    hour: int = 7,
    minute: int = 0,
    weekday: int = 0,
    day_of_month: int = 1,
) -> bool:
    if not _time_gate(now, hour, minute):
        return False
    current_day = _day_start(now)
    clean_period_key = _clean_text(period_key, 20)
    if clean_period_key == "day":
        return True
    if clean_period_key == "week":
        return current_day.weekday() == _normalize_weekday(weekday, default=0)
    if clean_period_key == "month":
        return current_day.day == _effective_day_of_month(now, _normalize_day_of_month(day_of_month, default=1))
    return False


def _format_range_label(start_at: datetime, end_at: datetime, period_key: str) -> str:
    if period_key == "day":
        return start_at.strftime("%Y-%m-%d")
    if period_key == "week":
        return f"{start_at.strftime('%Y-%m-%d')} 至 {end_at.strftime('%Y-%m-%d')}"
    if period_key == "month":
        return start_at.strftime("%Y-%m")
    return f"{start_at.strftime('%Y-%m-%d')} 至 {end_at.strftime('%Y-%m-%d')}"


def _report_window_for_test(now: datetime, period_key: str) -> tuple[str, datetime, datetime] | None:
    current_day = _day_start(now)
    if period_key == "day":
        target_day = current_day - timedelta(days=1)
        return target_day.strftime("%Y-%m-%d"), target_day, target_day + timedelta(days=1) - timedelta(microseconds=1)
    if period_key == "week":
        current_week = _week_start(now)
        target_start = current_week - timedelta(days=7)
        return target_start.strftime("%Y-%m-%d"), target_start, current_week - timedelta(microseconds=1)
    if period_key == "month":
        current_month = _month_start(now)
        target_end = current_month - timedelta(microseconds=1)
        target_start = _month_start(target_end)
        return target_start.strftime("%Y-%m"), target_start, target_end
    return None


def _report_window_for_schedule(
    now: datetime,
    period_key: str,
    *,
    push_hour: int = 7,
    push_minute: int = 0,
    push_weekday: int = 0,
    push_day_of_month: int = 1,
) -> tuple[str, datetime, datetime] | None:
    if not _period_schedule_due(
        now,
        period_key,
        hour=push_hour,
        minute=push_minute,
        weekday=push_weekday,
        day_of_month=push_day_of_month,
    ):
        return None
    current_day = _day_start(now)
    if period_key == "day":
        target_day = current_day - timedelta(days=1)
        return target_day.strftime("%Y-%m-%d"), target_day, target_day + timedelta(days=1) - timedelta(microseconds=1)
    if period_key == "week":
        current_week = _week_start(now)
        target_start = current_week - timedelta(days=7)
        return target_start.strftime("%Y-%m-%d"), target_start, current_week - timedelta(microseconds=1)
    if period_key == "month":
        target_end = _month_start(now) - timedelta(microseconds=1)
        target_start = _month_start(target_end)
        return target_start.strftime("%Y-%m"), target_start, target_end
    return None


def _shift_year_safe(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def _percentage_change(current: float, previous: float) -> float | None:
    if abs(previous) < 0.005:
        return None
    return round((current - previous) / previous * 100, 2)


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if abs(denominator) < 0.005:
        return None
    return round(numerator / denominator, 4)


def _scope_shop_key(shop_ids: list[int]) -> str:
    normalized = sorted({int(item) for item in shop_ids if int(item) > 0})
    return f",{','.join(str(item) for item in normalized)}," if normalized else ""


def _display_name(user: AqcUser | None) -> str:
    return _clean_text(user.display_name if user else "", 80) or _clean_text(user.username if user else "", 80) or "未命名成员"


def _report_role_label(role_key: str) -> str:
    mapping = {
        "aqc_admin": "管理员",
        "aqc_manager": "店长",
        "aqc_sales": "销售员",
        "aqc_engineer": "工程师",
    }
    return mapping.get(role_key, role_key)


def _is_reportable_shop(shop: AqcShop | None) -> bool:
    if shop is None:
        return False
    clean_name = _clean_text(shop.name, 255).lower()
    is_store = bool(shop.legacy_id is not None or shop.shop_type is None or int(shop.shop_type or 0) == 0)
    return is_store and bool(getattr(shop, "report_enabled", False)) and clean_name not in REPORT_DISABLED_SHOP_NAMES


def _resolved_report_shop_type(shop: AqcShop | None) -> int:
    if shop is None:
        return REPORT_SHOP_TYPE_STORE
    raw_type = int(getattr(shop, "shop_type", 0) or 0)
    if getattr(shop, "legacy_id", None) is None and raw_type == REPORT_SHOP_TYPE_REPAIR:
        return REPORT_SHOP_TYPE_REPAIR
    if getattr(shop, "legacy_id", None) is None and raw_type == REPORT_SHOP_TYPE_OTHER_WAREHOUSE:
        return REPORT_SHOP_TYPE_OTHER_WAREHOUSE
    if getattr(shop, "legacy_id", None) is None and raw_type == REPORT_SHOP_TYPE_WAREHOUSE:
        return REPORT_SHOP_TYPE_WAREHOUSE
    return REPORT_SHOP_TYPE_STORE


def _reportable_shop_ids(shop_map: dict[int, AqcShop]) -> list[int]:
    return [shop_id for shop_id, shop in shop_map.items() if _is_reportable_shop(shop)]


def _is_inventory_location(shop: AqcShop | None) -> bool:
    if shop is None:
        return False
    clean_name = _clean_text(shop.name, 255).lower()
    return bool(getattr(shop, "is_enabled", True)) and clean_name not in REPORT_DISABLED_SHOP_NAMES


def _inventory_scope_shop_ids(scope: dict[str, Any], shop_map: dict[int, AqcShop]) -> list[int]:
    all_location_ids = [
        int(shop_id)
        for shop_id, shop in shop_map.items()
        if _is_inventory_location(shop)
    ]
    non_store_location_ids = [
        int(shop_id)
        for shop_id, shop in shop_map.items()
        if _is_inventory_location(shop) and _resolved_report_shop_type(shop) != REPORT_SHOP_TYPE_STORE
    ]
    if scope["type"] == REPORT_SCOPE_COMPANY:
        return sorted(all_location_ids)

    scoped_shop_ids = [int(item) for item in scope.get("shopIds") or [] if int(item) > 0]
    if not scoped_shop_ids:
        return sorted(non_store_location_ids)
    return sorted({*scoped_shop_ids, *non_store_location_ids})


def _get_shop_map(db: Session) -> dict[int, AqcShop]:
    rows = db.execute(select(AqcShop).order_by(AqcShop.id.asc())).scalars().all()
    return {int(item.id): item for item in rows if item.id is not None}


def _parse_setting(setting: AqcReportSetting) -> dict[str, Any]:
    return {
        "id": int(setting.id),
        "periodKey": _clean_text(setting.period_key, 20),
        "periodLabel": _period_key_label(setting.period_key),
        "enabled": bool(setting.enabled),
        "recipientRoleKeys": _normalize_role_keys(_json_loads(setting.recipient_role_keys_json, [])),
        "recipientUserIds": _normalize_user_ids(_json_loads(setting.recipient_user_ids_json, [])),
        "pushTime": f"{int(setting.push_hour or 7):02d}:{int(setting.push_minute or 0):02d}",
        "pushWeekday": _normalize_weekday(getattr(setting, "push_weekday", 0), default=0),
        "pushDayOfMonth": _normalize_day_of_month(getattr(setting, "push_day_of_month", 1), default=1),
        "cleanupTime": f"{int(setting.cleanup_hour or 23):02d}:{int(setting.cleanup_minute or 59):02d}",
        "cleanupWeekday": _normalize_weekday(getattr(setting, "cleanup_weekday", 0), default=0),
        "cleanupDayOfMonth": _normalize_day_of_month(getattr(setting, "cleanup_day_of_month", 1), default=1),
        "retentionDays": int(setting.retention_days or 0),
        "lastPeriodKey": _clean_text(setting.last_period_key, 32),
        "lastCleanupDate": _clean_text(setting.last_cleanup_date, 10),
        "lastRunAt": to_iso(setting.last_run_at),
        "updatedAt": to_iso(setting.updated_at),
    }


def _load_report_settings(db: Session) -> list[AqcReportSetting]:
    return (
        db.execute(
            select(AqcReportSetting)
            .order_by(AqcReportSetting.period_key.asc(), AqcReportSetting.id.asc())
        )
        .scalars()
        .all()
    )


def _resolve_setting_recipients(db: Session, setting: AqcReportSetting) -> list[AqcUser]:
    role_keys = _normalize_role_keys(_json_loads(setting.recipient_role_keys_json, []))
    user_ids = _normalize_user_ids(_json_loads(setting.recipient_user_ids_json, []))
    active_users = db.execute(
        select(AqcUser)
        .options(selectinload(AqcUser.assigned_shop))
        .where(AqcUser.is_active.is_(True))
        .order_by(AqcUser.id.asc())
    ).scalars().all()

    result: list[AqcUser] = []
    seen: set[int] = set()
    for user in active_users:
        if int(user.id or 0) <= 0:
            continue
        user_role_key = get_aqc_role_key(user)
        if user_role_key == "aqc_departed":
            continue
        should_include = int(user.id) in user_ids
        if role_keys and user_role_key in role_keys:
            should_include = True
        if not role_keys and not user_ids and user_role_key in REPORT_SETTING_DEFAULT_ROLE_KEYS:
            should_include = True
        if not should_include or int(user.id) in seen:
            continue
        seen.add(int(user.id))
        result.append(user)
    return result


def _resolve_user_scope(user: AqcUser, shop_map: dict[int, AqcShop]) -> dict[str, Any] | None:
    role_key = get_aqc_role_key(user)
    enabled_shop_ids = _reportable_shop_ids(shop_map)
    if role_key == "aqc_admin":
        if not enabled_shop_ids:
            return None
        return {
            "type": REPORT_SCOPE_COMPANY,
            "label": "总报告",
            "shopIds": enabled_shop_ids,
            "shopNames": [
                _clean_text(shop_map.get(shop_id).name if shop_map.get(shop_id) else "", 255)
                for shop_id in enabled_shop_ids
                if shop_id in shop_map
            ],
            "primaryShopId": None,
            "userId": None,
            "userName": "",
        }

    shop_ids = [shop_id for shop_id in user_shop_ids(user) if shop_id in enabled_shop_ids]
    shop_names = [
        _clean_text(shop_map.get(shop_id).name if shop_map.get(shop_id) else "", 255)
        for shop_id in shop_ids
        if shop_id in shop_map
    ]
    shop_names = [item for item in shop_names if item]
    if shop_ids:
        label = shop_names[0] if len(shop_names) == 1 else "、".join(shop_names[:3])
        if len(shop_names) > 3:
            label = f"{label} 等 {len(shop_names)} 个门店"
        return {
            "type": REPORT_SCOPE_SHOP,
            "label": label or "所属门店报告",
            "shopIds": shop_ids,
            "shopNames": shop_names,
            "primaryShopId": int(shop_ids[0]),
            "userId": None,
            "userName": "",
        }
    return None


def _load_sales_rows(db: Session, *, start_at: datetime, end_at: datetime, scope: dict[str, Any], goods_only: bool = False) -> list[AqcSaleRecord]:
    stmt = (
        select(AqcSaleRecord)
        .options(selectinload(AqcSaleRecord.creator).load_only(AqcUser.id, AqcUser.display_name, AqcUser.username, AqcUser.phone))
        .where(
            AqcSaleRecord.sold_at >= start_at,
            AqcSaleRecord.sold_at <= end_at,
            AqcSaleRecord.sale_status != "return_entry",
        )
        .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
    )
    if goods_only:
        stmt = stmt.where(AqcSaleRecord.sale_kind == "goods")

    if scope["shopIds"]:
        stmt = stmt.where(AqcSaleRecord.shop_id.in_(scope["shopIds"]))
    elif scope["type"] == REPORT_SCOPE_USER:
        user_name = _clean_text(scope["userName"], 80)
        conditions = []
        if scope["userId"]:
            conditions.append(AqcSaleRecord.created_by == int(scope["userId"]))
        if user_name:
            conditions.append(AqcSaleRecord.salesperson == user_name)
        if conditions:
            stmt = stmt.where(or_(*conditions))

    return db.execute(stmt).scalars().all()


def _sales_summary_totals(rows: list[AqcSaleRecord]) -> dict[str, Any]:
    received_total = 0.0
    receivable_total = 0.0
    coupon_total = 0.0
    quantity_total = 0
    order_count = 0
    order_nums: set[str] = set()

    for row in rows:
        receivable_amount, received_amount, coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        receivable_total += receivable_amount
        received_total += received_amount
        coupon_total += coupon_amount
        quantity_total += int(quantity or 0)
        order_num = _clean_text(getattr(row, "order_num", None), 32)
        if order_num:
            order_nums.add(order_num)

    if order_nums:
        order_count = len(order_nums)
    elif quantity_total > 0:
        order_count = len(rows)

    average_ticket_value = round(received_total / order_count, 2) if order_count > 0 else 0.0
    average_quantity_per_order = round(quantity_total / order_count, 2) if order_count > 0 else 0.0
    discount_amount = round(max(receivable_total - received_total, 0.0), 2)

    return {
        "receivedTotal": round(received_total, 2),
        "receivableTotal": round(receivable_total, 2),
        "couponTotal": round(coupon_total, 2),
        "discountAmount": discount_amount,
        "quantityTotal": int(quantity_total),
        "orderCount": int(order_count),
        "averageTicketValue": average_ticket_value,
        "averageQuantityPerOrder": average_quantity_per_order,
    }


def _group_sales_by_shop(rows: list[AqcSaleRecord]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = _clean_text(getattr(row, "shop_name", None), 255) or "未归属门店"
        bucket = buckets.setdefault(label, {"shopName": label, "salesAmount": 0.0, "quantity": 0, "orderNums": set()})
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        bucket["salesAmount"] += received_amount
        bucket["quantity"] += int(quantity or 0)
        order_num = _clean_text(getattr(row, "order_num", None), 32)
        if order_num:
            bucket["orderNums"].add(order_num)

    rows_out: list[dict[str, Any]] = []
    for item in buckets.values():
        order_count = len(item["orderNums"]) or int(item["quantity"] > 0)
        rows_out.append({
            "shopName": item["shopName"],
            "salesAmount": round(float(item["salesAmount"]), 2),
            "quantity": int(item["quantity"]),
            "orderCount": int(order_count),
            "averageTicketValue": round(float(item["salesAmount"]) / order_count, 2) if order_count > 0 else 0.0,
        })
    rows_out.sort(key=lambda item: (-float(item["salesAmount"]), -int(item["quantity"]), item["shopName"]))
    return rows_out


def _group_sales_by_product(rows: list[AqcSaleRecord]) -> list[dict[str, Any]]:
    buckets: dict[tuple[int | None, str], dict[str, Any]] = {}
    for row in rows:
        goods_id = int(getattr(row, "goods_id", 0) or 0) or None
        label = _clean_text(getattr(row, "goods_model", None), 191) or "未识别商品"
        bucket = buckets.setdefault((goods_id, label), {
            "goodsId": goods_id,
            "goodsModel": label,
            "goodsBrand": _clean_text(getattr(row, "goods_brand", None), 120),
            "goodsSeries": _clean_text(getattr(row, "goods_series", None), 120),
            "quantity": 0,
            "salesAmount": 0.0,
        })
        if not bucket["goodsBrand"]:
            bucket["goodsBrand"] = _clean_text(getattr(row, "goods_brand", None), 120)
        if not bucket["goodsSeries"]:
            bucket["goodsSeries"] = _clean_text(getattr(row, "goods_series", None), 120)
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        bucket["quantity"] += int(quantity or 0)
        bucket["salesAmount"] += received_amount
    rows_out = [{
        "goodsId": item["goodsId"],
        "goodsModel": item["goodsModel"],
        "goodsBrand": item["goodsBrand"],
        "goodsSeries": item["goodsSeries"],
        "quantity": int(item["quantity"]),
        "salesAmount": round(float(item["salesAmount"]), 2),
    } for item in buckets.values()]
    rows_out.sort(key=lambda item: (-int(item["quantity"]), -float(item["salesAmount"]), item["goodsModel"]))
    return rows_out


def _group_sales_by_salesperson(rows: list[AqcSaleRecord]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = _clean_text(_resolve_salesperson(row), 80) or "未登记人员"
        bucket = buckets.setdefault(label, {
            "name": label,
            "salesAmount": 0.0,
            "quantity": 0,
            "orderNums": set(),
            "shopBreakdown": {},
            "salesDetails": [],
        })
        _receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        bucket["salesAmount"] += received_amount
        bucket["quantity"] += int(quantity or 0)
        order_num = _clean_text(getattr(row, "order_num", None), 32)
        if order_num:
            bucket["orderNums"].add(order_num)
        shop_name = _clean_text(getattr(row, "shop_name", None), 255) or "未归属门店"
        shop_bucket = bucket["shopBreakdown"].setdefault(shop_name, {
            "shopName": shop_name,
            "salesAmount": 0.0,
            "quantity": 0,
        })
        shop_bucket["salesAmount"] += received_amount
        shop_bucket["quantity"] += int(quantity or 0)
        bucket["salesDetails"].append({
            "soldAt": to_iso(getattr(row, "sold_at", None)),
            "orderNum": order_num,
            "goodsId": int(getattr(row, "goods_id", 0) or 0) or None,
            "goodsModel": _clean_text(getattr(row, "goods_model", None), 191) or "未识别商品",
            "shopId": int(getattr(row, "shop_id", 0) or 0) or None,
            "shopName": shop_name,
            "quantity": int(quantity or 0),
            "salesAmount": round(float(received_amount), 2),
        })
    rows_out = []
    for item in buckets.values():
        shop_breakdown = sorted(
            [
                {
                    "shopName": shop_item["shopName"],
                    "salesAmount": round(float(shop_item["salesAmount"]), 2),
                    "quantity": int(shop_item["quantity"]),
                }
                for shop_item in item["shopBreakdown"].values()
            ],
            key=lambda shop_item: (-float(shop_item["salesAmount"]), -int(shop_item["quantity"]), shop_item["shopName"]),
        )
        sales_details = sorted(
            item["salesDetails"],
            key=lambda detail: (
                detail.get("soldAt") or "",
                detail.get("orderNum") or "",
                detail.get("goodsModel") or "",
            ),
            reverse=True,
        )
        rows_out.append({
            "name": item["name"],
            "salesAmount": round(float(item["salesAmount"]), 2),
            "quantity": int(item["quantity"]),
            "orderCount": int(len(item["orderNums"])),
            "topShop": shop_breakdown[0] if shop_breakdown else None,
            "shopBreakdown": shop_breakdown,
            "salesDetails": sales_details,
        })
    rows_out.sort(key=lambda item: (-float(item["salesAmount"]), -int(item["quantity"]), item["name"]))
    return rows_out


def _load_purchase_quantity(db: Session, *, start_at: datetime, end_at: datetime, scope: dict[str, Any]) -> int:
    stmt = (
        select(AqcWorkOrderItem)
        .join(AqcWorkOrder, AqcWorkOrder.id == AqcWorkOrderItem.work_order_id)
        .where(
            AqcWorkOrder.order_type == "purchase",
            AqcWorkOrder.status == "approved",
            AqcWorkOrder.approved_at.is_not(None),
            AqcWorkOrder.approved_at >= start_at,
            AqcWorkOrder.approved_at <= end_at,
        )
    )
    if scope["shopIds"]:
        stmt = stmt.where(AqcWorkOrder.target_shop_id.in_(scope["shopIds"]))
    rows = db.execute(stmt).scalars().all()
    return sum(max(int(item.quantity or 0), 0) for item in rows)


def _build_sales_amount_module(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    period_key: str,
    scope: dict[str, Any],
) -> dict[str, Any]:
    current_rows = _load_sales_rows(db, start_at=start_at, end_at=end_at, scope=scope, goods_only=False)
    previous_span = end_at - start_at
    previous_end = start_at - timedelta(microseconds=1)
    previous_start = previous_end - previous_span
    previous_rows = _load_sales_rows(db, start_at=previous_start, end_at=previous_end, scope=scope, goods_only=False)
    year_ago_start = _shift_year_safe(start_at, -1)
    year_ago_end = _shift_year_safe(end_at, -1)
    year_ago_rows = _load_sales_rows(db, start_at=year_ago_start, end_at=year_ago_end, scope=scope, goods_only=False)

    current_totals = _sales_summary_totals(current_rows)
    previous_totals = _sales_summary_totals(previous_rows)
    year_ago_totals = _sales_summary_totals(year_ago_rows)
    shop_breakdown = _group_sales_by_shop(current_rows)
    salesperson_ranking = _group_sales_by_salesperson(current_rows)

    current_sales = float(current_totals["receivedTotal"])
    previous_sales = float(previous_totals["receivedTotal"])
    year_ago_sales = float(year_ago_totals["receivedTotal"])

    return {
        "title": "销售金额报告",
        "summary": {
            **current_totals,
            "momChangePercent": _percentage_change(current_sales, previous_sales),
            "yoyChangePercent": _percentage_change(current_sales, year_ago_sales),
            "shopCount": len(shop_breakdown),
        },
        "highlights": [
            f"总销售额 ¥ {current_sales:.2f}",
            f"客单价 ¥ {float(current_totals['averageTicketValue']):.2f}",
            f"环比 {'--' if _percentage_change(current_sales, previous_sales) is None else f'{_percentage_change(current_sales, previous_sales):.2f}%'}",
            f"同比 {'--' if _percentage_change(current_sales, year_ago_sales) is None else f'{_percentage_change(current_sales, year_ago_sales):.2f}%'}",
        ],
        "details": {
            "shopBreakdown": shop_breakdown,
            "salespersonRanking": salesperson_ranking[:20],
            "previousPeriod": previous_totals,
            "yearAgoPeriod": year_ago_totals,
            "periodKey": period_key,
        },
    }


def _build_sales_goods_module(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    scope: dict[str, Any],
) -> dict[str, Any]:
    current_rows = _load_sales_rows(db, start_at=start_at, end_at=end_at, scope=scope, goods_only=True)
    previous_span = end_at - start_at
    previous_end = start_at - timedelta(microseconds=1)
    previous_start = previous_end - previous_span
    previous_rows = _load_sales_rows(db, start_at=previous_start, end_at=previous_end, scope=scope, goods_only=True)
    year_ago_rows = _load_sales_rows(
        db,
        start_at=_shift_year_safe(start_at, -1),
        end_at=_shift_year_safe(end_at, -1),
        scope=scope,
        goods_only=True,
    )
    totals = _sales_summary_totals(current_rows)
    previous_totals = _sales_summary_totals(previous_rows)
    year_ago_totals = _sales_summary_totals(year_ago_rows)
    product_rows = _group_sales_by_product(current_rows)
    top_product = product_rows[0] if product_rows else {
        "goodsModel": "暂无",
        "goodsBrand": "",
        "goodsSeries": "",
        "quantity": 0,
        "salesAmount": 0.0,
    }
    purchase_quantity = _load_purchase_quantity(db, start_at=start_at, end_at=end_at, scope=scope)
    current_stock_stmt = select(func.sum(AqcGoodsInventory.quantity))
    if scope["shopIds"]:
        current_stock_stmt = current_stock_stmt.where(AqcGoodsInventory.shop_id.in_(scope["shopIds"]))
    current_stock_quantity = int(db.execute(current_stock_stmt).scalar() or 0)

    return {
        "title": "销售商品报告",
        "summary": {
            "salesQuantity": int(totals["quantityTotal"]),
            "productCount": len(product_rows),
            "topProduct": top_product,
            "salesToPurchaseRatio": _safe_ratio(float(totals["quantityTotal"]), float(purchase_quantity)),
            "sellThroughRate": _safe_ratio(float(totals["quantityTotal"]), float(current_stock_quantity + int(totals["quantityTotal"]))),
            "momChangePercent": _percentage_change(float(totals["quantityTotal"]), float(previous_totals["quantityTotal"])),
            "yoyChangePercent": _percentage_change(float(totals["quantityTotal"]), float(year_ago_totals["quantityTotal"])),
        },
        "highlights": [
            f"总销售件数 {int(totals['quantityTotal'])}",
            f"销量最高商品 {top_product['goodsModel']}",
            f"进销比 {'--' if _safe_ratio(float(totals['quantityTotal']), float(purchase_quantity)) is None else round(float(totals['quantityTotal']) / max(float(purchase_quantity), 1), 2)}",
        ],
        "details": {
            "products": product_rows,
            "previousPeriod": previous_totals,
            "yearAgoPeriod": year_ago_totals,
            "purchaseQuantity": int(purchase_quantity),
            "currentStockQuantity": int(current_stock_quantity),
        },
    }


def _load_inventory_logs(db: Session, *, start_at: datetime, end_at: datetime, scope: dict[str, Any]) -> list[AqcInventoryLog]:
    stmt = (
        select(AqcInventoryLog)
        .where(AqcInventoryLog.created_at >= start_at, AqcInventoryLog.created_at <= end_at)
        .order_by(AqcInventoryLog.created_at.desc(), AqcInventoryLog.id.desc())
    )
    if scope["shopIds"]:
        stmt = stmt.where(AqcInventoryLog.shop_id.in_(scope["shopIds"]))
    return db.execute(stmt).scalars().all()


def _build_inventory_module(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    scope: dict[str, Any],
) -> dict[str, Any]:
    shop_map = _get_shop_map(db)
    inventory_scope_ids = _inventory_scope_shop_ids(scope, shop_map)
    inventory_stmt = select(AqcGoodsInventory, AqcShop).join(AqcShop, AqcShop.id == AqcGoodsInventory.shop_id)
    if inventory_scope_ids:
        inventory_stmt = inventory_stmt.where(AqcGoodsInventory.shop_id.in_(inventory_scope_ids))
    inventory_rows = db.execute(inventory_stmt).all()
    current_total = 0
    location_rows: dict[int, dict[str, Any]] = {}

    def ensure_location_row(shop_id: int | None, *, fallback_name: str = "") -> dict[str, Any] | None:
        clean_shop_id = int(shop_id or 0)
        if clean_shop_id <= 0:
            return None
        existing = location_rows.get(clean_shop_id)
        if existing is not None:
            return existing
        shop = shop_map.get(clean_shop_id)
        label = _clean_text(getattr(shop, "name", None), 255) or _clean_text(fallback_name, 255) or "未归属点位"
        row = {
            "shopId": clean_shop_id,
            "shopName": label,
            "shopType": _resolved_report_shop_type(shop),
            "quantity": 0,
            "changeInQuantity": 0,
            "changeOutQuantity": 0,
            "netChangeQuantity": 0,
            "changeCount": 0,
            "recentLogs": [],
        }
        location_rows[clean_shop_id] = row
        return row

    for inventory, shop in inventory_rows:
        quantity = int(inventory.quantity or 0)
        current_total += quantity
        location = ensure_location_row(int(inventory.shop_id or 0), fallback_name=_clean_text(getattr(shop, "name", None), 255))
        if location is not None:
            location["quantity"] += quantity

    inventory_log_scope = {**scope, "shopIds": inventory_scope_ids}
    log_rows = _load_inventory_logs(db, start_at=start_at, end_at=end_at, scope=inventory_log_scope)
    change_in = 0
    change_out = 0
    net_change = 0
    detail_rows: list[dict[str, Any]] = []
    for item in log_rows:
        before = int(item.quantity_before or 0)
        after = int(item.quantity_after or 0)
        delta = after - before
        net_change += delta
        if delta > 0:
            change_in += delta
        elif delta < 0:
            change_out += abs(delta)
        location = ensure_location_row(int(item.shop_id or 0), fallback_name=_clean_text(item.shop_name, 255))
        if location is not None:
            location["netChangeQuantity"] += delta
            location["changeCount"] += 1
            if delta > 0:
                location["changeInQuantity"] += delta
            elif delta < 0:
                location["changeOutQuantity"] += abs(delta)

        detail = {
            "goodsId": int(item.goods_item_id or 0) if item.goods_item_id is not None else None,
            "createdAt": to_iso(item.created_at),
            "shopId": int(item.shop_id or 0) if item.shop_id is not None else None,
            "shopName": _clean_text(item.shop_name, 255),
            "shopType": _resolved_report_shop_type(shop_map.get(int(item.shop_id or 0))),
            "goodsModel": _clean_text(item.goods_model, 191),
            "changeContent": _clean_text(item.change_content, 255),
            "quantityBefore": before,
            "quantityAfter": after,
            "delta": delta,
            "operatorName": _clean_text(item.operator_name, 80),
            "relatedType": _clean_text(item.related_type, 40),
            "relatedId": int(item.related_id) if item.related_id is not None else None,
        }
        detail_rows.append(detail)
        if location is not None:
            location["recentLogs"].append(detail)

    shop_breakdown = sorted(
        [
            item
            for item in location_rows.values()
            if int(item["quantity"]) != 0 or int(item["netChangeQuantity"]) != 0
        ],
        key=lambda item: (
            -int(item["quantity"]),
            -abs(int(item["netChangeQuantity"])),
            item["shopType"],
            item["shopName"],
        ),
    )
    return {
        "title": "库存报告",
        "summary": {
            "currentTotalQuantity": int(current_total),
            "changeInQuantity": int(change_in),
            "changeOutQuantity": int(change_out),
            "netChangeQuantity": int(net_change),
            "shopCount": len(shop_breakdown),
        },
        "highlights": [
            f"当前库存总数 {int(current_total)}",
            f"周期内入库 {int(change_in)} / 出库 {int(change_out)}",
            f"库存净变动 {int(net_change)}",
        ],
        "details": {
            "shopBreakdown": shop_breakdown,
            "changeLogs": detail_rows,
        },
    }


def _build_salesperson_module(rows: list[AqcSaleRecord]) -> dict[str, Any]:
    ranking = _group_sales_by_salesperson(rows)
    return {
        "title": "销售员报告",
        "summary": {
            "memberCount": len(ranking),
            "topSalesperson": ranking[0] if ranking else None,
        },
        "highlights": [
            f"参与销售成员 {len(ranking)} 人",
            f"销冠 {ranking[0]['name']} · ¥ {ranking[0]['salesAmount']:.2f}" if ranking else "本周期暂无销售员排行",
        ],
        "details": {
            "ranking": ranking[:50],
        },
    }


def _build_target_module(db: Session, *, period_end: datetime, scope: dict[str, Any]) -> dict[str, Any] | None:
    month_key = period_end.strftime("%Y-%m")
    month_start = datetime(period_end.year, period_end.month, 1)
    shop_stmt = select(AqcShop).where(AqcShop.target_enabled.is_(True), AqcShop.report_enabled.is_(True))
    if scope["shopIds"]:
        shop_stmt = shop_stmt.where(AqcShop.id.in_(scope["shopIds"]))
    target_shops = db.execute(shop_stmt.order_by(AqcShop.id.asc())).scalars().all()
    if not target_shops:
        return None

    config_rows = db.execute(
        select(AqcShopTargetMonth).where(
            AqcShopTargetMonth.month_key == month_key,
            AqcShopTargetMonth.shop_id.in_([int(item.id) for item in target_shops]),
        )
    ).scalars().all()
    config_map = {int(item.shop_id): item for item in config_rows if item.shop_id is not None}

    sales_rows = db.execute(
        select(AqcSaleRecord)
        .where(
            AqcSaleRecord.sale_kind == "goods",
            AqcSaleRecord.sale_status != "return_entry",
            AqcSaleRecord.sold_at >= month_start,
            AqcSaleRecord.sold_at <= period_end,
            AqcSaleRecord.shop_id.in_([int(item.id) for item in target_shops]),
        )
        .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
    ).scalars().all()
    sales_bucket: dict[int, float] = defaultdict(float)
    for row in sales_rows:
        _receivable_amount, received_amount, _coupon_amount, _quantity, _sale_status = _sale_metric_snapshot(row)
        sales_bucket[int(row.shop_id or 0)] += received_amount

    detail_rows: list[dict[str, Any]] = []
    completion_values: list[float] = []
    for shop in target_shops:
        config = config_map.get(int(shop.id))
        target_amount = float(Decimal(str(getattr(config, "target_amount", 0) or 0)))
        actual_amount = round(float(sales_bucket.get(int(shop.id), 0.0)), 2)
        completion_ratio = round(actual_amount / target_amount, 4) if target_amount > 0 else 0.0
        completion_values.append(completion_ratio)
        detail_rows.append({
            "shopId": int(shop.id),
            "shopName": _clean_text(shop.name, 255),
            "targetAmount": round(target_amount, 2),
            "actualAmount": actual_amount,
            "completionRatio": completion_ratio,
        })
    detail_rows.sort(key=lambda item: (-item["completionRatio"], -item["actualAmount"], item["shopName"]))
    return {
        "title": "目标报告",
        "summary": {
            "enabledShopCount": len(detail_rows),
            "averageCompletionRatio": round(sum(completion_values) / len(completion_values), 4) if completion_values else 0.0,
        },
        "highlights": [
            f"启用目标门店 {len(detail_rows)} 家",
            f"平均目标完成度 {round((sum(completion_values) / len(completion_values) * 100) if completion_values else 0.0, 2)}%",
        ],
        "details": {
            "shops": detail_rows,
            "monthKey": month_key,
        },
    }


def _work_order_matches_scope(order: AqcWorkOrder, item_rows: list[AqcWorkOrderItem], scope: dict[str, Any]) -> bool:
    if scope["type"] == REPORT_SCOPE_USER:
        return int(order.applicant_id or 0) == int(scope["userId"] or 0) or int(order.approver_id or 0) == int(scope["userId"] or 0)
    if not scope["shopIds"]:
        return scope["type"] == REPORT_SCOPE_COMPANY
    scope_shop_ids = {int(item) for item in scope["shopIds"]}
    linked_shop_ids = {
        int(order.source_shop_id or 0),
        int(order.target_shop_id or 0),
    }
    for item in item_rows:
        linked_shop_ids.update({
            int(item.sale_shop_id or 0),
            int(item.receive_shop_id or 0),
            int(item.ship_shop_id or 0),
        })
    linked_shop_ids.discard(0)
    return bool(scope_shop_ids.intersection(linked_shop_ids))


def _build_work_order_module(db: Session, *, start_at: datetime, end_at: datetime, scope: dict[str, Any]) -> dict[str, Any]:
    orders = db.execute(
        select(AqcWorkOrder)
        .options(selectinload(AqcWorkOrder.items))
        .order_by(AqcWorkOrder.created_at.desc(), AqcWorkOrder.id.desc())
    ).scalars().all()

    scoped_orders = [item for item in orders if _work_order_matches_scope(item, list(item.items or []), scope)]
    approved_in_period = [
        item for item in scoped_orders
        if item.approved_at is not None and item.approved_at >= start_at and item.approved_at <= end_at and _clean_text(item.status, 20) == "approved"
    ]
    pending_now = [item for item in scoped_orders if _clean_text(item.status, 20) == "pending"]
    draft_now = [item for item in scoped_orders if _clean_text(item.status, 20) in DRAFT_STATUSES]

    recent_rows = []
    for item in approved_in_period:
        recent_rows.append({
            "orderNum": _clean_text(item.order_num, 32),
            "orderType": _clean_text(item.order_type, 20),
            "orderTypeLabel": WORK_ORDER_TYPES.get(_clean_text(item.order_type, 20), {}).get("label", _clean_text(item.order_type, 20)),
            "status": _clean_text(item.status, 20),
            "reason": _clean_text(item.reason, 255),
            "applicantName": _clean_text(item.applicant_name, 80),
            "approverName": _clean_text(item.approver_name, 80),
            "approvedAt": to_iso(item.approved_at),
        })

    return {
        "title": "工单报告",
        "summary": {
            "approvedCount": len(approved_in_period),
            "pendingCount": len(pending_now),
            "draftCount": len(draft_now),
        },
        "highlights": [
            f"本周期审批通过 {len(approved_in_period)} 单",
            f"当前待审批 {len(pending_now)} 单",
            f"当前草稿 {len(draft_now)} 单",
        ],
        "details": {
            "approvedOrders": recent_rows,
            "pendingOrders": [
                {
                    "orderNum": _clean_text(item.order_num, 32),
                    "orderTypeLabel": WORK_ORDER_TYPES.get(_clean_text(item.order_type, 20), {}).get("label", _clean_text(item.order_type, 20)),
                    "reason": _clean_text(item.reason, 255),
                    "applicantName": _clean_text(item.applicant_name, 80),
                    "createdAt": to_iso(item.created_at),
                }
                for item in pending_now
            ],
            "draftOrders": [
                {
                    "orderNum": _clean_text(item.order_num, 32),
                    "orderTypeLabel": WORK_ORDER_TYPES.get(_clean_text(item.order_type, 20), {}).get("label", _clean_text(item.order_type, 20)),
                    "reason": _clean_text(item.reason, 255),
                    "applicantName": _clean_text(item.applicant_name, 80),
                    "createdAt": to_iso(item.created_at),
                }
                for item in draft_now
            ],
        },
    }


def _build_report_payload(
    db: Session,
    *,
    period_key: str,
    period_token: str,
    start_at: datetime,
    end_at: datetime,
    scope: dict[str, Any],
) -> dict[str, Any]:
    sales_rows = _load_sales_rows(db, start_at=start_at, end_at=end_at, scope=scope, goods_only=False)
    sales_amount_module = _build_sales_amount_module(
        db,
        start_at=start_at,
        end_at=end_at,
        period_key=period_key,
        scope=scope,
    )
    sales_goods_module = _build_sales_goods_module(
        db,
        start_at=start_at,
        end_at=end_at,
        scope=scope,
    )
    inventory_module = _build_inventory_module(
        db,
        start_at=start_at,
        end_at=end_at,
        scope=scope,
    )
    salesperson_module = _build_salesperson_module(sales_rows)
    target_module = _build_target_module(db, period_end=end_at, scope=scope)
    work_order_module = _build_work_order_module(db, start_at=start_at, end_at=end_at, scope=scope)

    modules = {
        "salesAmount": sales_amount_module,
        "salesGoods": sales_goods_module,
        "inventory": inventory_module,
        "salesperson": salesperson_module,
        "workOrders": work_order_module,
    }
    if target_module is not None:
        modules["target"] = target_module

    report_title = f"{_format_range_label(start_at, end_at, period_key)} {_period_key_label(period_key)} · {scope['label']}"
    amount_summary = sales_amount_module["summary"]
    highlights = [
        f"销售额 ¥ {float(amount_summary['receivedTotal']):.2f}",
        f"销量 {int(sales_goods_module['summary']['salesQuantity'])} 件",
        f"库存总数 {int(inventory_module['summary']['currentTotalQuantity'])}",
        f"审批通过工单 {int(work_order_module['summary']['approvedCount'])} 单",
    ]
    if target_module is not None:
        highlights.append(
            f"平均目标完成度 {round(float(target_module['summary']['averageCompletionRatio']) * 100, 2)}%"
        )

    return {
        "title": report_title,
        "period": {
            "key": period_key,
            "label": _period_key_label(period_key),
            "token": period_token,
            "rangeLabel": _format_range_label(start_at, end_at, period_key),
            "startAt": to_iso(start_at),
            "endAt": to_iso(end_at),
        },
        "scope": {
            "type": scope["type"],
            "label": scope["label"],
            "shopIds": scope["shopIds"],
            "shopNames": scope["shopNames"],
            "userId": scope["userId"],
            "userName": scope["userName"],
        },
        "summary": {
            "salesAmount": amount_summary,
            "salesGoods": sales_goods_module["summary"],
            "inventory": inventory_module["summary"],
            "salesperson": salesperson_module["summary"],
            "target": target_module["summary"] if target_module is not None else None,
            "workOrders": work_order_module["summary"],
        },
        "highlights": highlights,
        "modules": modules,
    }


def _load_existing_report(
    db: Session,
    *,
    period_key: str,
    period_token: str,
    scope: dict[str, Any],
) -> AqcReportLog | None:
    stmt = select(AqcReportLog).where(
        AqcReportLog.period_key == period_key,
        AqcReportLog.period_token == period_token,
        AqcReportLog.scope_type == scope["type"],
        AqcReportLog.scope_shop_ids_key == _scope_shop_key(scope["shopIds"]),
        AqcReportLog.scope_user_id == (int(scope["userId"]) if scope["userId"] is not None else None),
    ).limit(1)
    return db.execute(stmt).scalars().first()


def _scope_from_report_log(row: AqcReportLog) -> dict[str, Any]:
    shop_ids = _normalize_user_ids(_json_loads(row.scope_shop_ids_json, []))
    return {
        "type": _clean_text(row.scope_type, 20),
        "label": _clean_text(row.scope_label, 255),
        "shopIds": shop_ids,
        "shopNames": [],
        "primaryShopId": int(row.primary_shop_id) if row.primary_shop_id is not None else None,
        "userId": int(row.scope_user_id) if row.scope_user_id is not None else None,
        "userName": _clean_text(row.scope_user_name, 80),
    }


def _apply_report_payload_to_log(
    row: AqcReportLog,
    *,
    payload: dict[str, Any],
    period_key: str,
    period_token: str,
    start_at: datetime,
    end_at: datetime,
    scope: dict[str, Any],
    generated_by: int | None = None,
) -> None:
    row.period_key = period_key
    row.period_token = period_token
    row.period_label = _period_key_label(period_key)
    row.range_label = _format_range_label(start_at, end_at, period_key)
    row.scope_type = _clean_text(scope["type"], 20)
    row.scope_label = _clean_text(scope["label"], 255)
    row.scope_shop_ids_json = _json_dumps(scope["shopIds"])
    row.scope_shop_ids_key = _scope_shop_key(scope["shopIds"])
    row.primary_shop_id = scope["primaryShopId"]
    row.scope_user_id = scope["userId"]
    row.scope_user_name = _clean_text(scope["userName"], 80)
    row.report_title = _clean_text(payload["title"], 160)
    row.window_start = start_at
    row.window_end = end_at
    row.highlights_json = _json_dumps(payload["highlights"])
    row.payload_json = _json_dumps(payload)
    row.generated_by = generated_by


def _refresh_report_log_payload(db: Session, row: AqcReportLog) -> dict[str, Any]:
    scope = _scope_from_report_log(row)
    payload = _build_report_payload(
        db,
        period_key=_clean_text(row.period_key, 20),
        period_token=_clean_text(row.period_token, 32),
        start_at=row.window_start,
        end_at=row.window_end,
        scope=scope,
    )
    _apply_report_payload_to_log(
        row,
        payload=payload,
        period_key=_clean_text(row.period_key, 20),
        period_token=_clean_text(row.period_token, 32),
        start_at=row.window_start,
        end_at=row.window_end,
        scope=scope,
        generated_by=int(row.generated_by) if row.generated_by is not None else None,
    )
    db.flush()
    return payload


def _ensure_report_log(
    db: Session,
    *,
    period_key: str,
    period_token: str,
    start_at: datetime,
    end_at: datetime,
    scope: dict[str, Any],
    generated_by: int | None = None,
) -> AqcReportLog:
    payload = _build_report_payload(
        db,
        period_key=period_key,
        period_token=period_token,
        start_at=start_at,
        end_at=end_at,
        scope=scope,
    )
    existing = _load_existing_report(
        db,
        period_key=period_key,
        period_token=period_token,
        scope=scope,
    )
    if existing is not None:
        _apply_report_payload_to_log(
            existing,
            payload=payload,
            period_key=period_key,
            period_token=period_token,
            start_at=start_at,
            end_at=end_at,
            scope=scope,
            generated_by=generated_by,
        )
        db.flush()
        return existing

    log = AqcReportLog(
        period_key=period_key,
        period_token=period_token,
        period_label=_period_key_label(period_key),
        range_label=_format_range_label(start_at, end_at, period_key),
        scope_type=scope["type"],
        scope_label=_clean_text(scope["label"], 255),
        scope_shop_ids_json=_json_dumps(scope["shopIds"]),
        scope_shop_ids_key=_scope_shop_key(scope["shopIds"]),
        primary_shop_id=scope["primaryShopId"],
        scope_user_id=scope["userId"],
        scope_user_name=_clean_text(scope["userName"], 80),
        report_title=_clean_text(payload["title"], 160),
        window_start=start_at,
        window_end=end_at,
        highlights_json=_json_dumps(payload["highlights"]),
        payload_json=_json_dumps(payload),
        generated_by=generated_by,
    )
    db.add(log)
    db.flush()
    return log


def _serialize_report_log(item: AqcReportLog) -> dict[str, Any]:
    return {
        "id": int(item.id),
        "title": _clean_text(item.report_title, 160),
        "periodKey": _clean_text(item.period_key, 20),
        "periodLabel": _clean_text(item.period_label, 40),
        "periodToken": _clean_text(item.period_token, 32),
        "rangeLabel": _clean_text(item.range_label, 120),
        "scopeType": _clean_text(item.scope_type, 20),
        "scopeLabel": _clean_text(item.scope_label, 255),
        "primaryShopId": int(item.primary_shop_id) if item.primary_shop_id is not None else None,
        "createdAt": to_iso(item.created_at) or "",
        "highlights": _json_loads(item.highlights_json, []),
    }


def _serialize_notification(item: AqcNotification) -> dict[str, Any]:
    payload = _json_loads(item.payload_json, {})
    return {
        "id": int(item.id),
        "notificationType": _clean_text(item.notification_type, 40),
        "title": _clean_text(item.title, 120),
        "content": _clean_text(item.content, 500),
        "status": _clean_text(item.status, 20),
        "isPersistent": bool(item.is_persistent),
        "isRead": bool(item.is_read),
        "relatedType": _clean_text(item.related_type, 40),
        "relatedId": int(item.related_id) if item.related_id is not None else None,
        "createdBy": int(item.created_by) if item.created_by is not None else None,
        "createdByName": _clean_text(item.created_by_name, 80),
        "createdAt": to_iso(item.created_at) or "",
        "readAt": to_iso(item.read_at),
        "handledAt": to_iso(item.handled_at),
        "dismissedAt": to_iso(item.dismissed_at),
        "payload": payload,
    }


def _upsert_report_notification(
    db: Session,
    *,
    user: AqcUser,
    report: AqcReportLog,
    created_by: int | None = None,
) -> None:
    existing = db.execute(
        select(AqcNotification)
        .where(
            AqcNotification.user_id == int(user.id),
            AqcNotification.notification_type == REPORT_NOTIFICATION_TYPE,
            AqcNotification.related_type == "report_log",
            AqcNotification.related_id == int(report.id),
            AqcNotification.dismissed_at.is_(None),
        )
        .limit(1)
    ).scalars().first()
    if existing is None:
        db.add(
            AqcNotification(
                user_id=int(user.id),
                notification_type=REPORT_NOTIFICATION_TYPE,
                title=_clean_text(report.report_title, 120),
                content="",
                status="sent",
                is_persistent=True,
                is_read=False,
                related_type="report_log",
                related_id=int(report.id),
                payload_json=_json_dumps({
                    "reportId": int(report.id),
                    "periodKey": _clean_text(report.period_key, 20),
                    "scopeLabel": _clean_text(report.scope_label, 255),
                }),
                created_by=created_by,
                created_by_name="系统报告",
            )
        )
        return

    existing.title = _clean_text(report.report_title, 120)
    existing.content = ""
    existing.status = "sent"
    existing.is_persistent = True
    existing.is_read = False
    existing.read_at = None
    existing.dismissed_at = None
    existing.payload_json = _json_dumps({
        "reportId": int(report.id),
        "periodKey": _clean_text(report.period_key, 20),
        "scopeLabel": _clean_text(report.scope_label, 255),
    })


def _user_can_access_report(user: AqcUser, report: AqcReportLog) -> bool:
    role_key = get_aqc_role_key(user)
    if role_key == "aqc_admin":
        return True
    if _clean_text(report.scope_type, 20) == REPORT_SCOPE_USER:
        return int(report.scope_user_id or 0) == int(user.id or 0)
    report_shop_ids = _normalize_user_ids(_json_loads(report.scope_shop_ids_json, []))
    if not report_shop_ids:
        return False
    return bool(set(report_shop_ids).intersection(user_shop_ids(user)))


def _report_visibility_conditions(user: AqcUser) -> list:
    if get_aqc_role_key(user) == "aqc_admin":
        return []
    conditions = [and_(AqcReportLog.scope_type == REPORT_SCOPE_USER, AqcReportLog.scope_user_id == int(user.id or 0))]
    shop_ids = user_shop_ids(user)
    for shop_id in shop_ids:
        conditions.append(AqcReportLog.scope_shop_ids_key.like(f"%,{int(shop_id)},%"))
    return [or_(*conditions)] if conditions else [AqcReportLog.id == -1]


def _generate_reports_for_setting(
    db: Session,
    *,
    setting: AqcReportSetting,
    period_token: str,
    start_at: datetime,
    end_at: datetime,
    users: list[AqcUser],
    generated_by: int | None = None,
    update_setting_cursor: bool = True,
) -> list[AqcReportLog]:
    if not users:
        return []
    shop_map = _get_shop_map(db)
    scope_groups: dict[tuple, dict[str, Any]] = {}
    for user in users:
        scope = _resolve_user_scope(user, shop_map)
        if scope is None:
            continue
        key = (
            scope["type"],
            tuple(scope["shopIds"]),
            int(scope["userId"] or 0),
        )
        group = scope_groups.setdefault(key, {"scope": scope, "users": []})
        group["users"].append(user)

    reports: list[AqcReportLog] = []
    for item in scope_groups.values():
        report = _ensure_report_log(
            db,
            period_key=_clean_text(setting.period_key, 20),
            period_token=period_token,
            start_at=start_at,
            end_at=end_at,
            scope=item["scope"],
            generated_by=generated_by,
        )
        for user in item["users"]:
            _upsert_report_notification(db, user=user, report=report, created_by=generated_by)
        reports.append(report)

    if update_setting_cursor:
        setting.last_period_key = _clean_text(period_token, 32)
        setting.last_run_at = _now()
        if generated_by is not None:
            setting.updated_by = generated_by
    return reports


def _parse_clock_value(value: object | None, *, default_hour: int, default_minute: int) -> tuple[int, int]:
    text = _clean_text(value, 5)
    if ":" not in text:
        return default_hour, default_minute
    hour_text, minute_text = text.split(":", 1)
    try:
        hour = int(hour_text)
        minute = int(minute_text)
    except Exception:
        return default_hour, default_minute
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return default_hour, default_minute
    return hour, minute


def _report_config_anchor(settings: list[AqcReportSetting]) -> AqcReportSetting | None:
    for key in ("day", "week", "month"):
        for item in settings:
            if _clean_text(item.period_key, 20) == key:
                return item
    return settings[0] if settings else None


def _dismiss_due_report_notifications(db: Session, settings: list[AqcReportSetting], now: datetime) -> None:
    rows = db.execute(
        select(AqcNotification).where(
            AqcNotification.notification_type == REPORT_NOTIFICATION_TYPE,
            AqcNotification.is_persistent.is_(True),
            AqcNotification.dismissed_at.is_(None),
        )
    ).scalars().all()
    if not rows:
        for setting in settings:
            period_key = _clean_text(setting.period_key, 20)
            if period_key not in REPORT_PERIOD_LABELS:
                continue
            if not _period_schedule_due(
                now,
                period_key,
                hour=int(getattr(setting, "cleanup_hour", 23) or 23),
                minute=int(getattr(setting, "cleanup_minute", 59) or 59),
                weekday=int(getattr(setting, "cleanup_weekday", 0) or 0),
                day_of_month=int(getattr(setting, "cleanup_day_of_month", 1) or 1),
            ):
                continue
            today_key = now.strftime("%Y-%m-%d")
            if _clean_text(setting.last_cleanup_date, 10) != today_key:
                setting.last_cleanup_date = today_key
        return

    rows_by_period: dict[str, list[AqcNotification]] = defaultdict(list)
    for item in rows:
        payload = _json_loads(item.payload_json, {})
        period_key = _clean_text(payload.get("periodKey"), 20)
        if period_key:
            rows_by_period[period_key].append(item)

    dismissed_at = datetime.utcnow()
    today_key = now.strftime("%Y-%m-%d")
    for setting in settings:
        period_key = _clean_text(setting.period_key, 20)
        if period_key not in REPORT_PERIOD_LABELS:
            continue
        if not _period_schedule_due(
            now,
            period_key,
            hour=int(getattr(setting, "cleanup_hour", 23) or 23),
            minute=int(getattr(setting, "cleanup_minute", 59) or 59),
            weekday=int(getattr(setting, "cleanup_weekday", 0) or 0),
            day_of_month=int(getattr(setting, "cleanup_day_of_month", 1) or 1),
        ):
            continue
        if _clean_text(setting.last_cleanup_date, 10) == today_key:
            continue
        for item in rows_by_period.get(period_key, []):
            item.dismissed_at = dismissed_at
            item.is_read = True
            if item.read_at is None:
                item.read_at = dismissed_at
        setting.last_cleanup_date = today_key


def _prune_expired_reports(db: Session, settings: list[AqcReportSetting]) -> None:
    now_utc = datetime.utcnow()
    for setting in settings:
        retention_days = max(int(getattr(setting, "retention_days", 0) or 0), 0)
        if retention_days <= 0:
            continue
        cutoff = now_utc - timedelta(days=retention_days)
        expired_rows = db.execute(
            select(AqcReportLog).where(
                AqcReportLog.period_key == _clean_text(setting.period_key, 20),
                AqcReportLog.created_at < cutoff,
            )
        ).scalars().all()
        if not expired_rows:
            continue
        expired_ids = [int(item.id) for item in expired_rows if item.id is not None]
        if expired_ids:
            notification_rows = db.execute(
                select(AqcNotification).where(
                    AqcNotification.related_type == "report_log",
                    AqcNotification.related_id.in_(expired_ids),
                )
            ).scalars().all()
            for notification in notification_rows:
                db.delete(notification)
        for row in expired_rows:
            db.delete(row)


def run_due_reports_once() -> None:
    db = SessionLocal()
    try:
        now = _now()
        settings = db.execute(
            select(AqcReportSetting)
            .where(AqcReportSetting.enabled.is_(True))
            .order_by(AqcReportSetting.period_key.asc(), AqcReportSetting.id.asc())
        ).scalars().all()
        _prune_expired_reports(db, settings)
        _dismiss_due_report_notifications(db, settings, now)
        for setting in settings:
            period_key = _clean_text(setting.period_key, 20)
            window = _report_window_for_schedule(
                now,
                period_key,
                push_hour=int(setting.push_hour or 7),
                push_minute=int(setting.push_minute or 0),
                push_weekday=int(getattr(setting, "push_weekday", 0) or 0),
                push_day_of_month=int(getattr(setting, "push_day_of_month", 1) or 1),
            )
            if window is None:
                continue
            period_token, start_at, end_at = window
            if _clean_text(setting.last_period_key, 32) == period_token:
                continue
            recipients = _resolve_setting_recipients(db, setting)
            if not recipients:
                continue
            _generate_reports_for_setting(
                db,
                setting=setting,
                period_token=period_token,
                start_at=start_at,
                end_at=end_at,
                users=recipients,
                generated_by=None,
                update_setting_cursor=True,
            )
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _report_runner_loop() -> None:
    while not REPORT_RUNNER_STOP.wait(90):
        run_due_reports_once()


def start_report_schedule_runner() -> None:
    global REPORT_RUNNER_STARTED
    if REPORT_RUNNER_STARTED:
        return
    REPORT_RUNNER_STOP.clear()
    REPORT_RUNNER_STARTED = True
    run_due_reports_once()
    runner = Thread(target=_report_runner_loop, name="aqc-report-scheduler", daemon=True)
    runner.start()


def stop_report_schedule_runner() -> None:
    global REPORT_RUNNER_STARTED
    REPORT_RUNNER_STOP.set()
    REPORT_RUNNER_STARTED = False


@router.get("/settings")
def report_settings(
    user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    settings = _load_report_settings(db)
    return {
        "success": True,
        "settings": [_parse_setting(item) for item in settings],
        "roleOptions": [
            {"value": key, "label": _report_role_label(key)}
            for key in REPORT_RECIPIENT_ROLE_KEYS
        ],
    }


@router.put("/settings")
def save_report_settings(
    payload: dict[str, Any],
    user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    items = payload.get("settings") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="报告设置格式不正确")

    rows = {str(item.period_key): item for item in _load_report_settings(db)}
    updated: list[AqcReportSetting] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        period_key = _clean_text(item.get("periodKey"), 20)
        if period_key not in REPORT_PERIOD_LABELS:
            continue
        row = rows.get(period_key)
        if row is None:
            row = AqcReportSetting(period_key=period_key, created_by=int(user.id), updated_by=int(user.id))
            db.add(row)
            rows[period_key] = row
        row.enabled = bool(item.get("enabled", True))
        row.recipient_role_keys_json = json.dumps(
            _normalize_role_keys(item.get("recipientRoleKeys") if isinstance(item.get("recipientRoleKeys"), list) else []),
            ensure_ascii=True,
        )
        row.recipient_user_ids_json = json.dumps(
            _normalize_user_ids(item.get("recipientUserIds") if isinstance(item.get("recipientUserIds"), list) else []),
            ensure_ascii=True,
        )
        row.push_hour, row.push_minute = _parse_clock_value(item.get("pushTime"), default_hour=int(getattr(row, "push_hour", 7) or 7), default_minute=int(getattr(row, "push_minute", 0) or 0))
        row.push_weekday = _normalize_weekday(item.get("pushWeekday"), default=int(getattr(row, "push_weekday", 0) or 0))
        row.push_day_of_month = _normalize_day_of_month(item.get("pushDayOfMonth"), default=int(getattr(row, "push_day_of_month", 1) or 1))
        row.cleanup_hour, row.cleanup_minute = _parse_clock_value(item.get("cleanupTime"), default_hour=int(getattr(row, "cleanup_hour", 23) or 23), default_minute=int(getattr(row, "cleanup_minute", 59) or 59))
        row.cleanup_weekday = _normalize_weekday(item.get("cleanupWeekday"), default=int(getattr(row, "cleanup_weekday", 0) or 0))
        row.cleanup_day_of_month = _normalize_day_of_month(item.get("cleanupDayOfMonth"), default=int(getattr(row, "cleanup_day_of_month", 1) or 1))
        try:
            row.retention_days = max(int(item.get("retentionDays", getattr(row, "retention_days", 0) or 0)), 0)
        except Exception:
            row.retention_days = max(int(getattr(row, "retention_days", 0) or 0), 0)
        row.updated_by = int(user.id)
        updated.append(row)
    db.commit()
    return {
        "success": True,
        "message": "报告设置已保存",
        "settings": [_parse_setting(item) for item in _load_report_settings(db)],
    }


@router.post("/test")
def send_report_test(
    payload: dict[str, Any],
    user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    period_key = _clean_text(payload.get("periodKey"), 20)
    user_ids = _normalize_user_ids(payload.get("userIds") if isinstance(payload.get("userIds"), list) else [])
    if period_key not in REPORT_PERIOD_LABELS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择日报、周报或月报")
    if not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择至少一位测试接收成员")

    recipients = db.execute(
        select(AqcUser)
        .options(selectinload(AqcUser.assigned_shop))
        .where(AqcUser.id.in_(user_ids), AqcUser.is_active.is_(True))
        .order_by(AqcUser.id.asc())
    ).scalars().all()
    if not recipients:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到可推送的测试成员")

    window = _report_window_for_test(_now(), period_key)
    if window is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前无法生成该类型报告")
    period_token, start_at, end_at = window
    setting = db.execute(select(AqcReportSetting).where(AqcReportSetting.period_key == period_key).limit(1)).scalars().first()
    if setting is None:
        setting = AqcReportSetting(
            period_key=period_key,
            enabled=True,
            recipient_role_keys_json=json.dumps(list(REPORT_SETTING_DEFAULT_ROLE_KEYS), ensure_ascii=True),
            recipient_user_ids_json="[]",
            created_by=int(user.id),
            updated_by=int(user.id),
        )
        db.add(setting)
        db.flush()

    reports = _generate_reports_for_setting(
        db,
        setting=setting,
        period_token=period_token,
        start_at=start_at,
        end_at=end_at,
        users=recipients,
        generated_by=int(user.id),
        update_setting_cursor=False,
    )
    db.commit()
    if not reports:
        return {
            "success": False,
            "message": "所选成员没有可生成报告的已启用门店",
            "reportIds": [],
        }
    return {
        "success": True,
        "message": f"已生成 {len(reports)} 份{_period_key_label(period_key)}测试报告并推送通知",
        "reportIds": [int(item.id) for item in reports],
    }


@router.get("/logs")
def list_report_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    period_key: str | None = None,
    scope_type: str | None = None,
    scope_label: str | None = None,
    date_start: str | None = None,
    date_end: str | None = None,
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcReportLog)
    count_stmt = select(func.count(AqcReportLog.id))
    visibility = _report_visibility_conditions(user)
    if visibility:
        stmt = stmt.where(*visibility)
        count_stmt = count_stmt.where(*visibility)

    clean_keyword = _clean_text(q, 120)
    if clean_keyword:
        like = f"%{clean_keyword}%"
        stmt = stmt.where(
            or_(
                AqcReportLog.report_title.like(like),
                AqcReportLog.scope_label.like(like),
                AqcReportLog.range_label.like(like),
                AqcReportLog.highlights_json.like(like),
            )
        )
        count_stmt = count_stmt.where(
            or_(
                AqcReportLog.report_title.like(like),
                AqcReportLog.scope_label.like(like),
                AqcReportLog.range_label.like(like),
                AqcReportLog.highlights_json.like(like),
            )
        )

    clean_period_key = _clean_text(period_key, 20)
    if clean_period_key in REPORT_PERIOD_LABELS:
        stmt = stmt.where(AqcReportLog.period_key == clean_period_key)
        count_stmt = count_stmt.where(AqcReportLog.period_key == clean_period_key)

    clean_scope_type = _clean_text(scope_type, 20)
    if clean_scope_type in {REPORT_SCOPE_COMPANY, REPORT_SCOPE_SHOP, REPORT_SCOPE_USER}:
        stmt = stmt.where(AqcReportLog.scope_type == clean_scope_type)
        count_stmt = count_stmt.where(AqcReportLog.scope_type == clean_scope_type)

    clean_scope_label = _clean_text(scope_label, 120)
    if clean_scope_label:
        like = f"%{clean_scope_label}%"
        stmt = stmt.where(AqcReportLog.scope_label.like(like))
        count_stmt = count_stmt.where(AqcReportLog.scope_label.like(like))

    if _clean_text(date_start, 20):
        try:
            parsed_start = datetime.fromisoformat(_clean_text(date_start, 20))
            stmt = stmt.where(AqcReportLog.created_at >= parsed_start)
            count_stmt = count_stmt.where(AqcReportLog.created_at >= parsed_start)
        except Exception:
            pass
    if _clean_text(date_end, 20):
        try:
            parsed_end = datetime.fromisoformat(_clean_text(date_end, 20)) + timedelta(days=1)
            stmt = stmt.where(AqcReportLog.created_at < parsed_end)
            count_stmt = count_stmt.where(AqcReportLog.created_at < parsed_end)
        except Exception:
            pass

    rows = db.execute(
        stmt.order_by(AqcReportLog.created_at.desc(), AqcReportLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    total = int(db.execute(count_stmt).scalar() or 0)
    return {
        "success": True,
        "total": total,
        "logs": [_serialize_report_log(item) for item in rows],
    }


@router.get("/latest")
def latest_report(
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcReportLog)
    visibility = _report_visibility_conditions(user)
    if visibility:
        stmt = stmt.where(*visibility)
    row = db.execute(
        stmt.order_by(AqcReportLog.created_at.desc(), AqcReportLog.id.desc()).limit(1)
    ).scalars().first()
    if row is None:
        return {"success": True, "report": None}
    payload = _refresh_report_log_payload(db, row)
    db.commit()
    return {"success": True, "report": {"id": int(row.id), **payload}}


@router.get("/{report_id}")
def report_detail(
    report_id: int,
    user: AqcUser = Depends(require_permissions("sales.read")),
    db: Session = Depends(get_db),
):
    row = db.execute(select(AqcReportLog).where(AqcReportLog.id == int(report_id)).limit(1)).scalars().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    if not _user_can_access_report(user, row):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权查看该报告")
    payload = _refresh_report_log_payload(db, row)
    db.commit()
    return {
        "success": True,
        "report": {
            "id": int(row.id),
            "createdAt": to_iso(row.created_at),
            **payload,
        },
    }

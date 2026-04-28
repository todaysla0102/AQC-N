from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, inspect, or_, select, text
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..deps import require_permissions, to_iso, to_local_iso
from ..models import AqcOrderUploadLog, AqcUser
from ..schemas import OrderDetailResponse, OrderListResponse, OrderUploadLogListResponse, OrderUploadResponse


router = APIRouter(prefix="/orders", tags=["orders"])


STATUS_LABELS = {
    0: "未支付",
    1: "已支付",
    2: "已发货",
    3: "已收货",
    4: "已完成",
    5: "申请售后",
    9: "已售后",
    88: "已取消",
}

PAY_TYPE_LABELS = {
    1: "微信支付",
    2: "钱包支付",
}

LEGACY_TABLE_CANDIDATES = {
    "orders": ("shopping_order",),
    "order_items": ("shopping_order_item",),
    "goods": ("goods_item",),
    "goods_specs": ("goods_spec",),
    "users": ("user_item", "users"),
    "addresses": ("user_address",),
    "admins": ("admin_users",),
}


def _normalized_prefix() -> str:
    prefix = (settings.aqco_full_prefix or "aqco_").strip() or "aqco_"
    if not re.fullmatch(r"[A-Za-z0-9_]+", prefix):
        return "aqco_"
    return prefix


def _table(name: str) -> str:
    return f"{_normalized_prefix()}{name}"


def _resolved_tables(table_names: set[str] | None = None) -> dict[str, str]:
    resolved: dict[str, str] = {}
    available = set(table_names or ())

    for key, candidates in LEGACY_TABLE_CANDIDATES.items():
        selected = None
        for candidate in candidates:
            table_name = _table(candidate)
            if not available or table_name in available:
                selected = table_name
                break
        if selected is None:
            selected = _table(candidates[0])
        resolved[key] = selected

    return resolved


def _ensure_mirror_tables(db: Session) -> tuple[bool, str | None]:
    table_names = set(inspect(db.get_bind()).get_table_names())
    missing: list[str] = []
    for candidates in LEGACY_TABLE_CANDIDATES.values():
        if any(_table(candidate) in table_names for candidate in candidates):
            continue
        missing.append("/".join(_table(candidate) for candidate in candidates))
    if missing:
        return False, f"缺少 AQC-O 全量镜像表，请先执行完整迁移：{', '.join(missing[:4])}"
    return True, None


def _to_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _status_label(status: int) -> str:
    return STATUS_LABELS.get(status, f"状态{status}")


def _pay_type_label(pay_type: int) -> str:
    return PAY_TYPE_LABELS.get(pay_type, "未知支付")


def _can_upload(status: int, is_imported: bool, upload_count: int) -> bool:
    return status >= 1 and status < 9 and not is_imported and upload_count <= 0


def _extract_response_message(payload) -> str | None:
    if isinstance(payload, dict):
        for key in ("message", "msg", "reason", "returnMsg", "errorMsg"):
            value = str(payload.get(key) or "").strip()
            if value:
                return value
    if isinstance(payload, str):
        value = payload.strip()
        if value:
            return value
    return None


def _upload_success(payload) -> bool:
    if isinstance(payload, dict):
        if payload.get("success") is True:
            return True
        if payload.get("success") is False:
            return False
        if payload.get("result") is True:
            return True
        if payload.get("result") is False:
            return False

        code = str(
            payload.get("returnCode")
            or payload.get("code")
            or payload.get("status")
            or ""
        ).strip().lower()
        if code:
            return code in {"0", "200", "success", "ok"}

    return payload is not None


def _serialize_upload(log: AqcOrderUploadLog) -> dict:
    response_message = _extract_response_message(_safe_json(log.response_payload))
    return {
        "id": log.id,
        "legacyOrderId": int(log.legacy_order_id),
        "legacyOrderNum": log.legacy_order_num or "",
        "legacyOrderItemId": log.legacy_order_item_id,
        "generatedOrderNum": log.generated_order_num,
        "cargoName": log.cargo_name or "",
        "success": bool(log.success),
        "errorMessage": log.error_message,
        "responseMessage": response_message,
        "createdBy": log.created_by,
        "createdByName": log.creator.display_name if log.creator else None,
        "uploadedAt": to_iso(log.uploaded_at) or "",
    }


def _safe_json(raw: str | None):
    text_value = str(raw or "").strip()
    if not text_value:
        return None
    try:
        return json.loads(text_value)
    except Exception:
        return text_value


def _build_order_out(row) -> dict:
    status = _to_int(row["status"], 0)
    pay_type = _to_int(row["pay_type"], 0)
    is_imported = _to_bool(row["is_import"])
    upload_count = _to_int(row["upload_count"], 0)
    return {
        "id": _to_int(row["id"], 0),
        "orderNum": str(row["order_num"] or "").strip(),
        "userName": str(row["user_name"] or "").strip() or None,
        "adminName": str(row["admin_name"] or "").strip() or None,
        "recipientName": str(row["recipient_name"] or "").strip(),
        "recipientPhone": str(row["recipient_phone"] or "").strip(),
        "recipientAddress": str(row["recipient_address"] or "").strip(),
        "goodsSummary": str(row["goods_summary"] or "").strip(),
        "itemCount": _to_int(row["item_count"], 0),
        "quantityTotal": _to_int(row["quantity_total"], 0),
        "total": _to_float(row["total"]),
        "totalFee": _to_float(row["total_fee"]),
        "pocket": _to_float(row["pocket"]),
        "score": _to_int(row["score"], 0),
        "payType": pay_type,
        "payTypeLabel": _pay_type_label(pay_type),
        "status": status,
        "statusLabel": _status_label(status),
        "isImported": is_imported,
        "uploadCount": upload_count,
        "lastUploadedAt": to_iso(row["last_uploaded_at"]),
        "logisticsNum": str(row["logistics_num"] or "").strip() or None,
        "remark": str(row["remark"] or "").strip(),
        "createdAt": to_local_iso(row["created_at"]) or "",
    }


def _fetch_order_row(db: Session, order_id: int):
    tables = _resolved_tables(set(inspect(db.get_bind()).get_table_names()))
    sql = text(
        f"""
        SELECT
            o.id,
            o.order_num,
            COALESCE(u.name, '') AS user_name,
            COALESCE(a.name, a.username, '') AS admin_name,
            COALESCE(o.logistics_name, '') AS recipient_name,
            COALESCE(CAST(o.logistics_phone AS CHAR), '') AS recipient_phone,
            COALESCE(o.logistics_address, '') AS recipient_address,
            COALESCE(
                (
                    SELECT GROUP_CONCAT(
                        CONCAT(COALESCE(g.name_ch, CONCAT('商品#', i.goods_item_id)), ' x', COALESCE(i.num, 1))
                        SEPARATOR ' / '
                    )
                    FROM `{tables["order_items"]}` i
                    LEFT JOIN `{tables["goods"]}` g ON g.id = i.goods_item_id
                    WHERE i.order_id = o.id
                ),
                ''
            ) AS goods_summary,
            COALESCE((SELECT COUNT(*) FROM `{tables["order_items"]}` i WHERE i.order_id = o.id), 0) AS item_count,
            COALESCE((SELECT SUM(COALESCE(i.num, 1)) FROM `{tables["order_items"]}` i WHERE i.order_id = o.id), 0) AS quantity_total,
            COALESCE(o.total, 0) AS total,
            COALESCE(o.total_fee, 0) AS total_fee,
            COALESCE(o.pocket, 0) AS pocket,
            COALESCE(o.score, 0) AS score,
            COALESCE(o.pay_type, 0) AS pay_type,
            COALESCE(o.status, 0) AS status,
            COALESCE(o.is_import, 0) AS is_import,
            (
                SELECT COUNT(*)
                FROM aqc_order_upload_logs l
                WHERE l.legacy_order_id = o.id
            ) AS upload_count,
            (
                SELECT MAX(l.uploaded_at)
                FROM aqc_order_upload_logs l
                WHERE l.legacy_order_id = o.id
            ) AS last_uploaded_at,
            COALESCE(o.logistics_num, '') AS logistics_num,
            COALESCE(o.remark, '') AS remark,
            o.created_at,
            o.address_id,
            o.logistics_type,
            o.logistics_id
        FROM `{tables["orders"]}` o
        LEFT JOIN `{tables["users"]}` u ON u.id = o.user_id
        LEFT JOIN `{tables["admins"]}` a ON a.id = o.admin_id
        WHERE o.id = :order_id
        LIMIT 1
        """
    )
    return db.execute(sql, {"order_id": order_id}).mappings().first()


@router.get("", response_model=OrderListResponse)
def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    status: int | None = Query(default=None),
    imported: bool | None = Query(default=None),
    _user: AqcUser = Depends(require_permissions("orders.read")),
    db: Session = Depends(get_db),
):
    ok, message = _ensure_mirror_tables(db)
    if not ok:
        return {"success": False, "total": 0, "orders": [], "message": message}

    tables = _resolved_tables(set(inspect(db.get_bind()).get_table_names()))
    filters = ["1=1"]
    params: dict[str, object] = {}

    keyword = (q or "").strip()
    if keyword:
        params["like"] = f"%{keyword}%"
        filters.append(
            f"""(
                o.order_num LIKE :like
                OR o.logistics_name LIKE :like
                OR CAST(o.logistics_phone AS CHAR) LIKE :like
                OR o.logistics_address LIKE :like
                OR o.remark LIKE :like
                OR EXISTS (
                    SELECT 1
                    FROM `{tables["order_items"]}` i
                    LEFT JOIN `{tables["goods"]}` g ON g.id = i.goods_item_id
                    WHERE i.order_id = o.id
                      AND COALESCE(g.name_ch, '') LIKE :like
                )
            )"""
        )

    if status is not None:
        params["status"] = int(status)
        filters.append("COALESCE(o.status, 0) = :status")

    if imported is not None:
        params["imported"] = 1 if imported else 0
        filters.append("COALESCE(o.is_import, 0) = :imported")

    where_sql = " AND ".join(filters)

    total_sql = text(f"SELECT COUNT(*) FROM `{tables['orders']}` o WHERE {where_sql}")
    total = _to_int(db.execute(total_sql, params).scalar(), 0)

    rows_sql = text(
        f"""
        SELECT
            o.id,
            o.order_num,
            COALESCE(u.name, '') AS user_name,
            COALESCE(a.name, a.username, '') AS admin_name,
            COALESCE(o.logistics_name, '') AS recipient_name,
            COALESCE(CAST(o.logistics_phone AS CHAR), '') AS recipient_phone,
            COALESCE(o.logistics_address, '') AS recipient_address,
            COALESCE(
                (
                    SELECT GROUP_CONCAT(
                        CONCAT(COALESCE(g.name_ch, CONCAT('商品#', i.goods_item_id)), ' x', COALESCE(i.num, 1))
                        SEPARATOR ' / '
                    )
                    FROM `{tables["order_items"]}` i
                    LEFT JOIN `{tables["goods"]}` g ON g.id = i.goods_item_id
                    WHERE i.order_id = o.id
                ),
                ''
            ) AS goods_summary,
            COALESCE((SELECT COUNT(*) FROM `{tables["order_items"]}` i WHERE i.order_id = o.id), 0) AS item_count,
            COALESCE((SELECT SUM(COALESCE(i.num, 1)) FROM `{tables["order_items"]}` i WHERE i.order_id = o.id), 0) AS quantity_total,
            COALESCE(o.total, 0) AS total,
            COALESCE(o.total_fee, 0) AS total_fee,
            COALESCE(o.pocket, 0) AS pocket,
            COALESCE(o.score, 0) AS score,
            COALESCE(o.pay_type, 0) AS pay_type,
            COALESCE(o.status, 0) AS status,
            COALESCE(o.is_import, 0) AS is_import,
            (
                SELECT COUNT(*)
                FROM aqc_order_upload_logs l
                WHERE l.legacy_order_id = o.id
            ) AS upload_count,
            (
                SELECT MAX(l.uploaded_at)
                FROM aqc_order_upload_logs l
                WHERE l.legacy_order_id = o.id
            ) AS last_uploaded_at,
            COALESCE(o.logistics_num, '') AS logistics_num,
            COALESCE(o.remark, '') AS remark,
            o.created_at
        FROM `{tables["orders"]}` o
        LEFT JOIN `{tables["users"]}` u ON u.id = o.user_id
        LEFT JOIN `{tables["admins"]}` a ON a.id = o.admin_id
        WHERE {where_sql}
        ORDER BY o.created_at DESC, o.id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = db.execute(rows_sql, params).mappings().all()

    return {
        "success": True,
        "total": total,
        "orders": [_build_order_out(row) for row in rows],
    }


@router.get("/logs", response_model=OrderUploadLogListResponse)
def list_order_upload_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    order_id: int | None = Query(default=None, ge=1),
    success: bool | None = Query(default=None),
    date_start: str | None = Query(default=None),
    date_end: str | None = Query(default=None),
    _user: AqcUser = Depends(require_permissions("orders.read")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcOrderUploadLog).options(selectinload(AqcOrderUploadLog.creator))
    count_stmt = select(func.count(AqcOrderUploadLog.id))
    summary_stmt = select(
        func.count(AqcOrderUploadLog.id),
        func.sum(case((AqcOrderUploadLog.success.is_(True), 1), else_=0)),
    )

    clean_keyword = str(q or "").strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        conditions = [
            AqcOrderUploadLog.legacy_order_num.like(like),
            AqcOrderUploadLog.generated_order_num.like(like),
            AqcOrderUploadLog.cargo_name.like(like),
            AqcOrderUploadLog.error_message.like(like),
            AqcOrderUploadLog.response_payload.like(like),
        ]
        if clean_keyword.isdigit():
            conditions.append(AqcOrderUploadLog.legacy_order_id == int(clean_keyword))
        keyword_condition = or_(*conditions)
        stmt = stmt.where(keyword_condition)
        count_stmt = count_stmt.where(keyword_condition)
        summary_stmt = summary_stmt.where(keyword_condition)

    if order_id is not None:
        stmt = stmt.where(AqcOrderUploadLog.legacy_order_id == int(order_id))
        count_stmt = count_stmt.where(AqcOrderUploadLog.legacy_order_id == int(order_id))
        summary_stmt = summary_stmt.where(AqcOrderUploadLog.legacy_order_id == int(order_id))

    if success is not None:
        stmt = stmt.where(AqcOrderUploadLog.success.is_(bool(success)))
        count_stmt = count_stmt.where(AqcOrderUploadLog.success.is_(bool(success)))
        summary_stmt = summary_stmt.where(AqcOrderUploadLog.success.is_(bool(success)))

    parsed_date_start = date_start.strip() if isinstance(date_start, str) else ""
    if parsed_date_start:
        try:
            start_at = datetime.strptime(parsed_date_start, "%Y-%m-%d")
        except ValueError:
            start_at = None
        if start_at is not None:
            stmt = stmt.where(AqcOrderUploadLog.uploaded_at >= start_at)
            count_stmt = count_stmt.where(AqcOrderUploadLog.uploaded_at >= start_at)
            summary_stmt = summary_stmt.where(AqcOrderUploadLog.uploaded_at >= start_at)

    parsed_date_end = date_end.strip() if isinstance(date_end, str) else ""
    if parsed_date_end:
        try:
            end_at = datetime.strptime(parsed_date_end, "%Y-%m-%d")
        except ValueError:
            end_at = None
        if end_at is not None:
            end_at = end_at.replace(hour=0, minute=0, second=0, microsecond=0)
            next_day = end_at + timedelta(days=1)
            stmt = stmt.where(AqcOrderUploadLog.uploaded_at < next_day)
            count_stmt = count_stmt.where(AqcOrderUploadLog.uploaded_at < next_day)
            summary_stmt = summary_stmt.where(AqcOrderUploadLog.uploaded_at < next_day)

    total = int(db.execute(count_stmt).scalar() or 0)
    summary_row = db.execute(summary_stmt).one()
    success_count = int(summary_row[1] or 0)
    rows = (
        db.execute(
            stmt.order_by(AqcOrderUploadLog.uploaded_at.desc(), AqcOrderUploadLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return {
        "success": True,
        "total": total,
        "successCount": success_count,
        "failedCount": max(total - success_count, 0),
        "uploads": [_serialize_upload(log) for log in rows],
    }


@router.get("/{order_id}", response_model=OrderDetailResponse)
def get_order_detail(
    order_id: int,
    _user: AqcUser = Depends(require_permissions("orders.read")),
    db: Session = Depends(get_db),
):
    ok, message = _ensure_mirror_tables(db)
    if not ok:
        return {"success": False, "order": None, "message": message}

    row = _fetch_order_row(db, order_id)
    if row is None:
        return {"success": False, "order": None, "message": "订单不存在"}

    tables = _resolved_tables(set(inspect(db.get_bind()).get_table_names()))
    items_sql = text(
        f"""
        SELECT
            i.id,
            i.goods_item_id,
            COALESCE(g.name_ch, CONCAT('商品#', i.goods_item_id)) AS goods_name,
            i.goods_spec_id,
            NULLIF(TRIM(COALESCE(gs.properties, '')), '') AS goods_spec_name,
            NULLIF(TRIM(COALESCE(g.goodspec, '')), '') AS goodspec,
            COALESCE(i.num, 1) AS quantity,
            COALESCE(i.price, 0) AS price,
            COALESCE(i.total_amount, COALESCE(i.num, 1) * COALESCE(i.price, 0)) AS total_amount,
            COALESCE(i.score, 0) AS score,
            CASE
                WHEN COALESCE(g.weight, 0) > 0 THEN ROUND(g.weight / 1000, 3)
                ELSE NULL
            END AS weight_kg
        FROM `{tables["order_items"]}` i
        LEFT JOIN `{tables["goods"]}` g ON g.id = i.goods_item_id
        LEFT JOIN `{tables["goods_specs"]}` gs ON gs.id = i.goods_spec_id
        WHERE i.order_id = :order_id
        ORDER BY i.id ASC
        """
    )
    item_rows = db.execute(items_sql, {"order_id": order_id}).mappings().all()

    uploads = (
        db.execute(
            select(AqcOrderUploadLog)
            .options(selectinload(AqcOrderUploadLog.creator))
            .where(AqcOrderUploadLog.legacy_order_id == order_id)
            .order_by(AqcOrderUploadLog.uploaded_at.desc(), AqcOrderUploadLog.id.desc())
        )
        .scalars()
        .all()
    )

    order = _build_order_out(row)
    order["addressId"] = _to_int(row["address_id"], 0) or None
    order["logisticsType"] = _to_int(row["logistics_type"], 0) or None
    order["logisticsCompanyId"] = _to_int(row["logistics_id"], 0) or None
    order["items"] = [
        {
            "id": _to_int(item["id"], 0),
            "goodsItemId": _to_int(item["goods_item_id"], 0) or None,
            "goodsName": str(item["goods_name"] or "").strip(),
            "goodsSpecId": _to_int(item["goods_spec_id"], 0) or None,
            "goodsSpecName": str(item["goods_spec_name"] or "").strip() or None,
            "goodspec": str(item["goodspec"] or "").strip() or None,
            "quantity": _to_int(item["quantity"], 0),
            "price": _to_float(item["price"]),
            "totalAmount": _to_float(item["total_amount"]),
            "score": _to_int(item["score"], 0),
            "weightKg": _to_float(item["weight_kg"]) if item["weight_kg"] is not None else None,
        }
        for item in item_rows
    ]
    order["uploads"] = [_serialize_upload(log) for log in uploads]
    order["canUpload"] = _can_upload(order["status"], order["isImported"], order["uploadCount"])

    return {"success": True, "order": order}


def _post_order_upload(payload: dict[str, str]) -> tuple[object | None, str | None]:
    body = urlencode(payload).encode("utf-8")
    req = UrlRequest(
        url=settings.order_upload_api_url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "AQC-N-OrderUploader/1.0",
        },
    )

    try:
        with urlopen(req, timeout=max(3, int(settings.order_upload_timeout or 20))) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(raw), None
            except Exception:
                return raw, None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(raw), None
        except Exception:
            return None, f"上传失败（HTTP {exc.code}）"
    except URLError:
        return None, "物流上传服务不可达"
    except Exception as exc:
        return None, f"物流上传异常: {exc}"


def _resolve_sender(db: Session) -> tuple[str, str, str]:
    tables = _resolved_tables(set(inspect(db.get_bind()).get_table_names()))
    sender = db.execute(
        text(
            f"""
            SELECT
                COALESCE(name, '') AS name,
                COALESCE(CAST(mobile AS CHAR), '') AS mobile,
                CONCAT(COALESCE(province, ''), COALESCE(city, ''), COALESCE(district, ''), COALESCE(address, '')) AS addr
            FROM `{tables["addresses"]}`
            WHERE user_id = :user_id
            ORDER BY id ASC
            LIMIT 1
            """
        ),
        {"user_id": int(settings.order_upload_sender_user_id or 1)},
    ).mappings().first()

    name = str((sender or {}).get("name") or settings.order_upload_sender_name or "").strip()
    mobile = str((sender or {}).get("mobile") or settings.order_upload_sender_mobile or "").strip()
    addr = str((sender or {}).get("addr") or settings.order_upload_sender_addr or "").strip()
    return name, mobile, addr


@router.post("/{order_id}/upload", response_model=OrderUploadResponse)
def upload_order(
    order_id: int,
    user: AqcUser = Depends(require_permissions("orders.upload")),
    db: Session = Depends(get_db),
):
    ok, message = _ensure_mirror_tables(db)
    if not ok:
        return {
            "success": False,
            "message": message or "AQC-O 订单镜像未就绪",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    row = _fetch_order_row(db, order_id)
    if row is None:
        return {
            "success": False,
            "message": "订单不存在",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    existing_uploads = _to_int(row["upload_count"], 0)
    status = _to_int(row["status"], 0)
    is_imported = _to_bool(row["is_import"])
    if not _can_upload(status, is_imported, existing_uploads):
        return {
            "success": False,
            "message": "该订单当前不可上传，可能已上传或状态不满足条件",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    if not settings.order_upload_appid or not settings.order_upload_appsecret or not settings.order_upload_appuid:
        return {
            "success": False,
            "message": "订单上传参数未配置完整",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    sender_name, sender_mobile, sender_addr = _resolve_sender(db)
    if not sender_name or not sender_mobile or not sender_addr:
        return {
            "success": False,
            "message": "寄件人信息不完整，无法按 AQC-O 方式上传订单",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    tables = _resolved_tables(set(inspect(db.get_bind()).get_table_names()))
    items_sql = text(
        f"""
        SELECT
            i.id,
            i.goods_item_id,
            i.goods_spec_id,
            COALESCE(i.num, 1) AS quantity,
            COALESCE(g.name_ch, CONCAT('商品#', i.goods_item_id)) AS goods_name,
            COALESCE(g.weight, 0) AS weight
        FROM `{tables["order_items"]}` i
        LEFT JOIN `{tables["goods"]}` g ON g.id = i.goods_item_id
        WHERE i.order_id = :order_id
        ORDER BY i.id ASC
        """
    )
    item_rows = db.execute(items_sql, {"order_id": order_id}).mappings().all()
    if not item_rows:
        return {
            "success": False,
            "message": "订单明细为空，无法上传",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    receiver_name = str(row["recipient_name"] or "").strip()
    receiver_mobile = str(row["recipient_phone"] or "").strip()
    receiver_addr = str(row["recipient_address"] or "").strip()
    if not receiver_name or not receiver_mobile or not receiver_addr:
        return {
            "success": False,
            "message": "收件人信息不完整，无法上传",
            "uploadedCount": 0,
            "failedCount": 0,
            "generatedOrderNums": [],
            "uploads": [],
        }

    timestamp = int(round(time.time() * 1000))
    first_sign = hashlib.md5(f"{settings.order_upload_appid}{timestamp}{settings.order_upload_appuid}".encode("utf-8")).hexdigest().upper()
    sign = hashlib.md5(f"{settings.order_upload_appsecret}{first_sign}".encode("utf-8")).hexdigest().upper()

    uploaded_count = 0
    failed_count = 0
    generated_order_nums: list[str] = []
    created_logs: list[AqcOrderUploadLog] = []

    for item in item_rows:
        item_id = _to_int(item["id"], 0)
        quantity = max(1, _to_int(item["quantity"], 1))
        goods_name = str(item["goods_name"] or "未命名商品").strip() or "未命名商品"
        weight_kg = max(0.0, _to_float(item["weight"]) / 1000)

        for _unit_index in range(quantity):
            generated_order_num = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(10000, 99999)}-{item_id}"
            request_data = {
                "recMobile": receiver_mobile,
                "recName": receiver_name,
                "recAddr": receiver_addr,
                "sendMobile": sender_mobile,
                "sendName": sender_name,
                "sendAddr": sender_addr,
                "orderNum": generated_order_num,
                "cargo": goods_name,
                "count": 1,
                "payment": "SHIPPER",
                "weight": weight_kg,
                "comment": "",
                "items": {
                    "itemName": goods_name,
                    "itemSpec": "单规格",
                    "itemCount": 1,
                },
            }
            request_payload = {
                "appid": settings.order_upload_appid,
                "sign": sign,
                "timestamp": str(timestamp),
                "appuid": settings.order_upload_appuid,
                "data": json.dumps(request_data, ensure_ascii=False),
            }

            response_payload, error_message = _post_order_upload(request_payload)
            success = error_message is None and _upload_success(response_payload)
            if success:
                uploaded_count += 1
                generated_order_nums.append(generated_order_num)
            else:
                failed_count += 1

            response_text = ""
            if response_payload is not None:
                if isinstance(response_payload, str):
                    response_text = response_payload
                else:
                    response_text = json.dumps(response_payload, ensure_ascii=False)

            log = AqcOrderUploadLog(
                legacy_order_id=order_id,
                legacy_order_num=str(row["order_num"] or "").strip(),
                legacy_order_item_id=item_id or None,
                generated_order_num=generated_order_num,
                cargo_name=goods_name[:255],
                request_payload=json.dumps(request_payload, ensure_ascii=False),
                response_payload=response_text,
                success=success,
                error_message=error_message or (None if success else (_extract_response_message(response_payload) or "上传失败")),
                created_by=user.id,
            )
            db.add(log)
            created_logs.append(log)

    db.flush()

    if uploaded_count > 0 and failed_count == 0:
        db.execute(
            text(
                f"""
                UPDATE `{tables["orders"]}`
                SET is_import = 1, status = 2
                WHERE id = :order_id
                """
            ),
            {"order_id": order_id},
        )
        message = f"订单上传成功，共生成 {uploaded_count} 条物流单"
    elif uploaded_count > 0:
        message = f"订单部分上传成功：成功 {uploaded_count} 条，失败 {failed_count} 条"
    else:
        message = "订单上传失败"

    db.commit()

    persisted_logs = (
        db.execute(
            select(AqcOrderUploadLog)
            .options(selectinload(AqcOrderUploadLog.creator))
            .where(AqcOrderUploadLog.id.in_([log.id for log in created_logs]))
            .order_by(AqcOrderUploadLog.uploaded_at.desc(), AqcOrderUploadLog.id.desc())
        )
        .scalars()
        .all()
        if created_logs
        else []
    )

    return {
        "success": uploaded_count > 0,
        "message": message,
        "uploadedCount": uploaded_count,
        "failedCount": failed_count,
        "generatedOrderNums": generated_order_nums,
        "uploads": [_serialize_upload(log) for log in persisted_logs],
    }

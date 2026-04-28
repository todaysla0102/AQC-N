from __future__ import annotations

import json
import random
from threading import Event, Thread
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import SessionLocal, get_db
from ..deps import get_aqc_role_key, require_permissions, to_iso, to_local_iso, user_shop_ids
from ..goods_attributes import compose_goods_name, split_model_attribute
from ..inventory import (
    SHOP_TYPE_OTHER_WAREHOUSE,
    SHOP_TYPE_STORE,
    SHOP_TYPE_WAREHOUSE,
    apply_inventory_delta,
    recalculate_goods_stock,
    simplify_shop_name,
)
from ..models import (
    AqcGroup,
    AqcGroupMember,
    AqcGoodsItem,
    AqcGoodsInventory,
    AqcSaleRecord,
    AqcShop,
    AqcUser,
    AqcWorkOrder,
    AqcWorkOrderAction,
    AqcWorkOrderAllocationDraft,
    AqcWorkOrderItem,
    AqcWorkOrderSchedule,
    AqcWorkOrderSetting,
)
from ..schemas import (
    MessageResponse,
    WorkOrderActionOut,
    WorkOrderApproverOptionOut,
    WorkOrderCategoryOptionOut,
    WorkOrderAllocationConfirmResponse,
    WorkOrderAllocationDraftOut,
    WorkOrderAllocationDraftResponse,
    WorkOrderAllocationDraftSaveRequest,
    WorkOrderAllocationRowOut,
    WorkOrderAllocationTargetOut,
    WorkOrderDashboardResponse,
    WorkOrderDefaultApproverSettingOut,
    WorkOrderDetailOut,
    WorkOrderDetailResponse,
    WorkOrderGroupOptionOut,
    WorkOrderItemInput,
    WorkOrderItemOut,
    WorkOrderLogListResponse,
    WorkOrderLogOut,
    WorkOrderListResponse,
    WorkOrderMetaResponse,
    WorkOrderReviewRequest,
    WorkOrderScheduleListResponse,
    WorkOrderScheduleOut,
    WorkOrderScheduleSaveRequest,
    WorkOrderSettingsResponse,
    WorkOrderSettingsSaveRequest,
    WorkOrderSaveRequest,
    WorkOrderShopOptionOut,
    WorkOrderStatusOptionOut,
    WorkOrderSummaryOut,
    WorkOrderTypeOptionOut,
    WorkOrderUserOptionOut,
)


router = APIRouter(prefix="/work-orders", tags=["work-orders"])
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
DRAFT_STATUSES = {"draft", "rejected"}
WORK_ORDER_TYPES = {
    "transfer": {"label": "商品调拨单", "prefix": "DB", "category": "goods"},
    "purchase": {"label": "商品进货单", "prefix": "SJ", "category": "goods"},
    "return": {"label": "商品退货单", "prefix": "ST", "category": "goods"},
    "damage": {"label": "商品报损单", "prefix": "BS", "category": "goods"},
    "sale": {"label": "销售单", "prefix": "XS", "category": "sales"},
    "sale_return": {"label": "销售退货单", "prefix": "XT", "category": "sales"},
    "sale_exchange": {"label": "销售换货单", "prefix": "XH", "category": "sales"},
}
WORK_ORDER_CATEGORIES = {
    "goods": "商品类工单",
    "sales": "销售类工单",
}
WORK_ORDER_STATUSES = {
    "draft": "草稿",
    "pending": "待审批",
    "approved": "已通过",
    "rejected": "未通过",
}
WORK_ORDER_SCHEDULE_PERIODS = {
    "day": "按日",
    "week": "按周",
    "month": "按月",
}
SALE_STATUS_LABELS = {
    "normal": "正常",
    "returned": "已退货",
    "return_entry": "退货冲销",
}
WORK_ORDER_ACTIONS = {
    "saved": "保存草稿",
    "submitted": "提交审批",
    "withdrawn": "撤回至草稿",
    "approved": "审批通过",
    "rejected": "审批驳回",
}
SCHEDULE_RUNNER_STOP = Event()
SCHEDULE_RUNNER_STARTED = False
SALES_ORDER_TYPES = {"sale", "sale_return", "sale_exchange"}
SALES_RETURN_LIKE_TYPES = {"sale_return", "sale_exchange"}
SHOP_TYPE_REPAIR = 3


def _clean_text(value: str | None, max_length: int) -> str:
    return (value or "").strip()[:max_length]


def _to_amount(value: Decimal | float | int | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(tzinfo=None)


def _parse_form_date(raw: str | None) -> datetime:
    clean = _clean_text(raw, 40)
    if not clean:
        return _now_shanghai()
    try:
        parsed = datetime.fromisoformat(clean.replace("T", " "))
        if parsed.tzinfo is not None:
            return parsed.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
        return parsed
    except Exception:
        return _now_shanghai()


def _parse_filter_date(raw: str | None, *, end: bool = False) -> datetime | None:
    clean = _clean_text(raw, 40)
    if not clean:
        return None
    try:
        if len(clean) <= 10:
            base = datetime.fromisoformat(clean)
            if end:
                return base + timedelta(days=1)
            return base
        parsed = datetime.fromisoformat(clean.replace("T", " "))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _work_order_type_label(order_type: str) -> str:
    return WORK_ORDER_TYPES.get(order_type, WORK_ORDER_TYPES["transfer"])["label"]


def _to_work_order_setting_out(order_type: str, setting: AqcWorkOrderSetting | None = None) -> WorkOrderDefaultApproverSettingOut:
    return WorkOrderDefaultApproverSettingOut(
        orderType=_clean_text(order_type, 20),
        orderTypeLabel=_work_order_type_label(order_type),
        approverId=int(setting.approver_id) if setting is not None and setting.approver_id is not None else None,
        approverName=_clean_text(setting.approver_name if setting is not None else "", 80),
    )


def _load_work_order_setting_map(db: Session) -> dict[str, AqcWorkOrderSetting]:
    rows = db.execute(select(AqcWorkOrderSetting)).scalars().all()
    return {
        _clean_text(item.order_type, 20): item
        for item in rows
        if _clean_text(item.order_type, 20)
    }


def _validate_setting_approver(db: Session, approver_id: int | None) -> AqcUser | None:
    if approver_id is None:
        return None
    approver = db.execute(
        select(AqcUser).where(AqcUser.id == int(approver_id), AqcUser.is_active.is_(True)).limit(1)
    ).scalars().first()
    if approver is None:
        raise ValueError("负责人不存在或已停用")
    if get_aqc_role_key(approver) != "aqc_admin":
        raise ValueError("负责人必须为管理员账号")
    return approver


def _resolve_work_order_default_approver(db: Session, order_type: str) -> AqcUser | None:
    normalized_type = _clean_text(order_type, 20)
    if not normalized_type:
        return None
    setting = db.execute(
        select(AqcWorkOrderSetting).where(AqcWorkOrderSetting.order_type == normalized_type).limit(1)
    ).scalars().first()
    if setting is None or setting.approver_id is None:
        return None
    try:
        return _validate_setting_approver(db, int(setting.approver_id))
    except Exception:
        return None


def _work_order_category(order_type: str) -> str:
    return _clean_text(WORK_ORDER_TYPES.get(order_type, WORK_ORDER_TYPES["transfer"]).get("category"), 20) or "goods"


def _work_order_category_label(order_type: str) -> str:
    return WORK_ORDER_CATEGORIES.get(_work_order_category(order_type), WORK_ORDER_CATEGORIES["goods"])


def _work_order_status_label(status: str) -> str:
    return WORK_ORDER_STATUSES.get(status, status or "")


def _sale_status_label(status: str) -> str:
    return SALE_STATUS_LABELS.get(status, status or "")


def _display_name(user: AqcUser | None) -> str:
    if user is None:
        return ""
    return _clean_text(user.display_name or user.username, 80)


def _is_admin(user: AqcUser) -> bool:
    return get_aqc_role_key(user) == "aqc_admin"


def _group_ids_for_user(db: Session, user_id: int) -> list[int]:
    rows = db.execute(
        select(AqcGroupMember.group_id)
        .join(AqcGroup, AqcGroup.id == AqcGroupMember.group_id)
        .where(AqcGroupMember.user_id == int(user_id), AqcGroup.is_active.is_(True))
    ).scalars().all()
    return sorted({int(item) for item in rows if item is not None})


def _default_group_for_user(db: Session, user_id: int) -> AqcGroup | None:
    return (
        db.execute(
            select(AqcGroup)
            .join(AqcGroupMember, AqcGroupMember.group_id == AqcGroup.id)
            .where(
                AqcGroupMember.user_id == int(user_id),
                AqcGroupMember.is_default.is_(True),
                AqcGroup.is_active.is_(True),
            )
            .limit(1)
        )
        .scalars()
        .first()
    )


def _backfill_shared_drafts_for_accessible_groups(db: Session, user: AqcUser) -> None:
    group_ids = _group_ids_for_user(db, int(user.id or 0))
    if not group_ids:
        return
    membership_rows = db.execute(
        select(AqcGroupMember.group_id, AqcGroupMember.user_id, AqcGroup.name)
        .join(AqcGroup, AqcGroup.id == AqcGroupMember.group_id)
        .where(AqcGroupMember.group_id.in_(group_ids), AqcGroup.is_active.is_(True))
    ).all()
    if not membership_rows:
        return
    user_group_counts: dict[int, set[int]] = {}
    for group_id, member_user_id, _group_name in membership_rows:
        user_group_counts.setdefault(int(member_user_id), set()).add(int(group_id))
    touched = False
    for group_id, member_user_id, group_name in membership_rows:
        if len(user_group_counts.get(int(member_user_id), set())) != 1:
            continue
        rows = db.execute(
            select(AqcWorkOrder).where(
                AqcWorkOrder.applicant_id == int(member_user_id),
                AqcWorkOrder.status.in_(sorted(DRAFT_STATUSES)),
                AqcWorkOrder.shared_group_id.is_(None),
            )
        ).scalars().all()
        for order in rows:
            order.shared_group_id = int(group_id)
            order.shared_group_name = _clean_text(group_name, 80)
            order.shared_by_id = int(member_user_id)
            order.shared_by_name = _clean_text(order.applicant_name, 80)
            touched = True
    if touched:
        db.commit()


def _is_group_member(db: Session, group_id: int | None, user_id: int) -> bool:
    if group_id is None:
        return False
    exists = db.execute(
        select(AqcGroupMember.id).where(
            AqcGroupMember.group_id == int(group_id),
            AqcGroupMember.user_id == int(user_id),
        ).limit(1)
    ).scalar()
    return exists is not None


def _can_view_order(db: Session, user: AqcUser, order: AqcWorkOrder) -> bool:
    if _is_admin(user):
        return True
    return (
        int(order.applicant_id or 0) == int(user.id or 0)
        or int(order.approver_id or 0) == int(user.id or 0)
        or _is_group_member(db, order.shared_group_id, int(user.id or 0))
    )


def _can_edit_order(db: Session, user: AqcUser, order: AqcWorkOrder) -> bool:
    if order.status not in DRAFT_STATUSES:
        return False
    if int(order.applicant_id or 0) == int(user.id or 0):
        return True
    return _is_group_member(db, order.shared_group_id, int(user.id or 0))


def _can_review_order(user: AqcUser, order: AqcWorkOrder) -> bool:
    return (
        _is_admin(user)
        and order.status == "pending"
        and int(order.approver_id or 0) == int(user.id or 0)
    )


def _can_withdraw_order(user: AqcUser, order: AqcWorkOrder) -> bool:
    return (
        int(order.applicant_id or 0) == int(user.id or 0)
        and order.status == "pending"
        and not bool(order.stock_applied)
    )


def _can_delete_order(db: Session, user: AqcUser, order: AqcWorkOrder) -> bool:
    if bool(order.stock_applied):
        return False
    if order.status in DRAFT_STATUSES:
        return _can_edit_order(db, user, order)
    return int(order.applicant_id or 0) == int(user.id or 0) and order.status == "pending"


def _generate_order_num(db: Session, order_type: str) -> str:
    prefix = WORK_ORDER_TYPES.get(order_type, WORK_ORDER_TYPES["transfer"])["prefix"]
    today = _now_shanghai().strftime("%Y-%m-%d")
    for _ in range(80):
        candidate = f"{prefix}-{today}-{random.randint(100, 999)}"
        exists = db.execute(select(AqcWorkOrder.id).where(AqcWorkOrder.order_num == candidate).limit(1)).scalar()
        if exists is None:
            return candidate
    raise ValueError("工单编号生成失败，请重试")


def _generate_sale_order_num(db: Session, sold_at: datetime | None = None) -> str:
    target_date = sold_at or _now_shanghai()
    prefix = f"Clo{target_date.strftime('%Y%m%d')}"
    for _ in range(120):
        candidate = f"{prefix}{random.randint(0, 999999999):09d}"[:32]
        exists = db.execute(select(AqcSaleRecord.id).where(AqcSaleRecord.order_num == candidate).limit(1)).scalar()
        if exists is None:
            return candidate
    fallback_seed = int(datetime.now(SHANGHAI_TZ).timestamp() * 1000000) % 1_000_000_000
    return f"{prefix}{fallback_seed:09d}"[:32]


def _compose_goods_name(brand: str, series: str, goods_name: str) -> str:
    parts = [part for part in (brand, series, goods_name) if part]
    return " ".join(parts).strip()[:191] or goods_name[:191] or "未命名商品"


def _normalize_index_key(goods_name: str, brand: str, series: str) -> str:
    seed = goods_name.strip() or brand.strip() or series.strip()
    if not seed:
        return "#"
    for ch in seed:
        if ch.isascii() and ch.isalnum():
            return ch.upper()
        if ch.isdigit():
            return ch
    return "#"


def _goods_signature(
    *,
    brand: str = "",
    series: str = "",
    goods_name: str = "",
) -> tuple[str, str, str]:
    return (
        _clean_text(brand, 120),
        _clean_text(series, 120),
        _clean_text(goods_name, 191),
    )


def _find_goods_by_signature(
    db: Session,
    *,
    brand: str = "",
    series: str = "",
    goods_name: str = "",
) -> list[AqcGoodsItem]:
    signature = _goods_signature(brand=brand, series=series, goods_name=goods_name)
    if not any(signature):
        return []
    return db.execute(
        select(AqcGoodsItem)
        .where(
            AqcGoodsItem.brand == signature[0],
            AqcGoodsItem.series_name == signature[1],
            AqcGoodsItem.model_name == signature[2],
            AqcGoodsItem.model_attribute == "-",
        )
        .order_by(AqcGoodsItem.id.asc())
    ).scalars().all()


def _get_shop_map(db: Session) -> dict[int, AqcShop]:
    rows = db.execute(select(AqcShop)).scalars().all()
    return {int(item.id): item for item in rows}


def _get_user_map(db: Session) -> dict[int, AqcUser]:
    rows = db.execute(select(AqcUser).where(AqcUser.is_active.is_(True))).scalars().all()
    return {int(item.id): item for item in rows}


def _is_store_salesperson_eligible(user: AqcUser) -> bool:
    return bool(user and user.is_active) and get_aqc_role_key(user) in {"aqc_admin", "aqc_manager", "aqc_sales"}


def _is_repair_salesperson_eligible(user: AqcUser) -> bool:
    return bool(user and user.is_active) and get_aqc_role_key(user) in {"aqc_admin", "aqc_engineer"}


def _build_shop_member_map(db: Session, shop_ids: list[int]) -> dict[int, list[AqcUser]]:
    normalized_shop_ids = sorted({int(shop_id) for shop_id in shop_ids if int(shop_id) > 0})
    result = {shop_id: [] for shop_id in normalized_shop_ids}
    if not normalized_shop_ids:
        return result
    users = db.execute(select(AqcUser).where(AqcUser.is_active.is_(True))).scalars().all()
    for user in users:
        for shop_id in user_shop_ids(user):
            if shop_id in result:
                result[shop_id].append(user)
    return result


def _sorted_shop_salespeople(item: AqcShop, member_users: list[AqcUser] | None = None) -> list[AqcUser]:
    manager_user_id = int(item.manager_user_id or 0)
    raw_users = member_users if member_users is not None else item.assigned_users
    eligible = _is_repair_salesperson_eligible if int(item.shop_type or 0) == SHOP_TYPE_REPAIR else _is_store_salesperson_eligible
    return sorted(
        [user for user in (raw_users or []) if eligible(user)],
        key=lambda user: (
            0 if int(user.id or 0) == manager_user_id else 1,
            0 if get_aqc_role_key(user) == "aqc_manager" else 1,
            0 if get_aqc_role_key(user) == "aqc_admin" else 1,
            _display_name(user),
            int(user.id or 0),
        ),
    )


def _to_shop_option(item: AqcShop, member_users: list[AqcUser] | None = None) -> WorkOrderShopOptionOut:
    return WorkOrderShopOptionOut(
        id=int(item.id),
        name=_clean_text(item.name, 255),
        shortName=simplify_shop_name(item.name),
        shopType=int(item.shop_type or 0),
        salespersonIds=[int(user.id) for user in _sorted_shop_salespeople(item, member_users)],
    )


def _build_order_metric_map(db: Session, order_ids: list[int]) -> dict[int, tuple[int, int, float]]:
    normalized_ids = [int(item) for item in order_ids if int(item or 0) > 0]
    if not normalized_ids:
        return {}
    rows = db.execute(
        select(
            AqcWorkOrderItem.work_order_id,
            func.count(AqcWorkOrderItem.id),
            func.coalesce(func.sum(AqcWorkOrderItem.quantity), 0),
            func.coalesce(func.sum(AqcWorkOrderItem.total_amount), 0),
        )
        .where(AqcWorkOrderItem.work_order_id.in_(normalized_ids))
        .group_by(AqcWorkOrderItem.work_order_id)
    ).all()
    return {
        int(order_id): (
            int(item_count or 0),
            int(total_quantity or 0),
            round(float(total_amount or 0), 2),
        )
        for order_id, item_count, total_quantity, total_amount in rows
    }


def _to_order_summary(
    order: AqcWorkOrder,
    *,
    metrics: tuple[int, int, float] | None = None,
) -> WorkOrderSummaryOut:
    if metrics is None:
        item_count = len(order.items or [])
        total_quantity = sum(int(item.quantity or 0) for item in order.items or [])
        total_amount = round(sum(float(item.total_amount or 0) for item in order.items or []), 2)
    else:
        item_count, total_quantity, total_amount = metrics
    return WorkOrderSummaryOut(
        id=int(order.id),
        orderNum=_clean_text(order.order_num, 32),
        orderCategory=_work_order_category(order.order_type),
        orderCategoryLabel=_work_order_category_label(order.order_type),
        orderType=_clean_text(order.order_type, 20),
        orderTypeLabel=_work_order_type_label(order.order_type),
        reason=_clean_text(order.reason, 255),
        status=_clean_text(order.status, 20),
        statusLabel=_work_order_status_label(order.status),
        formDate=to_local_iso(order.form_date) or "",
        applicantId=int(order.applicant_id),
        applicantName=_clean_text(order.applicant_name, 80),
        approverId=int(order.approver_id) if order.approver_id is not None else None,
        approverName=_clean_text(order.approver_name, 80),
        groupId=int(order.shared_group_id) if order.shared_group_id is not None else None,
        groupName=_clean_text(order.shared_group_name, 80),
        sharedById=int(order.shared_by_id) if order.shared_by_id is not None else None,
        sharedByName=_clean_text(order.shared_by_name, 80),
        itemCount=item_count,
        totalQuantity=total_quantity,
        totalAmount=total_amount,
        createdAt=to_iso(order.created_at) or "",
        updatedAt=to_iso(order.updated_at) or "",
    )


def _to_order_item_out(item: AqcWorkOrderItem) -> WorkOrderItemOut:
    return _to_order_item_out_with_stock(item, source_stock=0, target_stock=0)


def _to_order_item_out_with_stock(
    item: AqcWorkOrderItem,
    *,
    source_stock: int = 0,
    target_stock: int = 0,
) -> WorkOrderItemOut:
    return WorkOrderItemOut(
        id=int(item.id),
        sortIndex=int(item.sort_index or 0),
        goodsId=int(item.goods_id) if item.goods_id is not None else None,
        saleRecordId=int(item.sale_record_id) if item.sale_record_id is not None else None,
        lineType=_clean_text(item.line_type, 20) or "default",
        orderNum=_clean_text(item.source_order_num, 64),
        salesperson=_clean_text(item.salesperson, 80),
        saleShopId=int(item.sale_shop_id) if item.sale_shop_id is not None else None,
        saleShopName=_clean_text(item.sale_shop_name, 255),
        receiveShopId=int(item.receive_shop_id) if item.receive_shop_id is not None else None,
        receiveShopName=_clean_text(item.receive_shop_name, 255),
        shipShopId=int(item.ship_shop_id) if item.ship_shop_id is not None else None,
        shipShopName=_clean_text(item.ship_shop_name, 255),
        goodsName=_clean_text(item.goods_name, 191),
        productCode=_clean_text(item.product_code, 64),
        brand=_clean_text(item.brand, 120),
        series=_clean_text(item.series_name, 120),
        barcode=_clean_text(item.barcode, 64),
        unitPrice=float(item.unit_price or 0),
        receivedAmount=float(item.received_amount or 0),
        receivableAmount=float(item.receivable_amount or 0),
        couponAmount=float(item.coupon_amount or 0),
        discountRate=float(item.discount_rate or 10),
        quantity=int(item.quantity or 0),
        totalAmount=float(item.total_amount or 0),
        channel=_clean_text(item.channel, 50),
        customerName=_clean_text(item.customer_name, 120),
        remark=_clean_text(item.remark, 255),
        sourceStock=int(source_stock or 0),
        targetStock=int(target_stock or 0),
        isNewGoods=bool(item.is_new_goods),
    )


def _to_action_out(item: AqcWorkOrderAction) -> WorkOrderActionOut:
    return WorkOrderActionOut(
        id=int(item.id),
        actionType=_clean_text(item.action_type, 20),
        actionLabel=WORK_ORDER_ACTIONS.get(item.action_type, item.action_type or ""),
        statusFrom=_clean_text(item.status_from, 20),
        statusFromLabel=_work_order_status_label(item.status_from),
        statusTo=_clean_text(item.status_to, 20),
        statusToLabel=_work_order_status_label(item.status_to),
        comment=_clean_text(item.comment, 1000),
        actorId=int(item.actor_id) if item.actor_id is not None else None,
        actorName=_clean_text(item.actor_name, 80),
        createdAt=to_iso(item.created_at) or "",
    )


def _to_work_order_log_out(action: AqcWorkOrderAction, order: AqcWorkOrder) -> WorkOrderLogOut:
    return WorkOrderLogOut(
        id=int(action.id),
        workOrderId=int(order.id),
        orderNum=_clean_text(order.order_num, 32),
        orderCategory=_work_order_category(order.order_type),
        orderCategoryLabel=_work_order_category_label(order.order_type),
        orderType=_clean_text(order.order_type, 20),
        orderTypeLabel=_work_order_type_label(order.order_type),
        reason=_clean_text(order.reason, 255),
        applicantName=_clean_text(order.applicant_name, 80),
        approverName=_clean_text(order.approver_name, 80),
        actionType=_clean_text(action.action_type, 20),
        actionLabel=WORK_ORDER_ACTIONS.get(action.action_type, action.action_type or ""),
        statusFrom=_clean_text(action.status_from, 20),
        statusFromLabel=_work_order_status_label(action.status_from),
        statusTo=_clean_text(action.status_to, 20),
        statusToLabel=_work_order_status_label(action.status_to),
        actorId=int(action.actor_id) if action.actor_id is not None else None,
        actorName=_clean_text(action.actor_name, 80),
        comment=_clean_text(action.comment, 1000),
        createdAt=to_iso(action.created_at) or "",
    )


def _inventory_quantity_map_for_goods(
    db: Session,
    goods_ids: list[int],
    shop_id: int | None,
) -> dict[int, int]:
    normalized_ids = sorted({int(item) for item in goods_ids if int(item) > 0})
    if not normalized_ids or shop_id is None or int(shop_id) <= 0:
        return {}
    rows = db.execute(
        select(AqcGoodsInventory.goods_item_id, AqcGoodsInventory.quantity)
        .where(
            AqcGoodsInventory.shop_id == int(shop_id),
            AqcGoodsInventory.goods_item_id.in_(normalized_ids),
        )
    ).all()
    return {int(row[0]): int(row[1] or 0) for row in rows if row[0] is not None}


def _inventory_quantity_for_goods_shop(
    db: Session,
    goods_id: int | None,
    shop_id: int | None,
) -> int:
    normalized_goods_id = int(goods_id or 0)
    normalized_shop_id = int(shop_id or 0)
    if normalized_goods_id <= 0 or normalized_shop_id <= 0:
        return 0
    row = db.execute(
        select(AqcGoodsInventory.quantity)
        .where(
            AqcGoodsInventory.goods_item_id == normalized_goods_id,
            AqcGoodsInventory.shop_id == normalized_shop_id,
        )
        .limit(1)
    ).first()
    return int(row[0] or 0) if row is not None else 0


def _to_order_detail(db: Session, order: AqcWorkOrder, user: AqcUser) -> WorkOrderDetailOut:
    summary = _to_order_summary(order)
    ordered_items = sorted(order.items or [], key=lambda row: (int(row.sort_index or 0), int(row.id or 0)))
    goods_ids = [int(item.goods_id) for item in ordered_items if item.goods_id is not None]
    source_stock_map = _inventory_quantity_map_for_goods(
        db,
        goods_ids,
        None if (order.order_type == "sale" and bool(order.sale_affects_inventory)) else order.source_shop_id,
    )
    target_stock_map = _inventory_quantity_map_for_goods(db, goods_ids, order.target_shop_id)
    return WorkOrderDetailOut(
        **summary.model_dump(),
        sourceShopId=int(order.source_shop_id) if order.source_shop_id is not None else None,
        sourceShopName=_clean_text(order.source_shop_name, 255),
        targetShopId=int(order.target_shop_id) if order.target_shop_id is not None else None,
        targetShopName=_clean_text(order.target_shop_name, 255),
        supplierName=_clean_text(order.supplier_name, 255),
        partnerName=_clean_text(order.partner_name, 255),
        saleAffectsInventory=bool(order.sale_affects_inventory),
        submittedAt=to_local_iso(order.submitted_at),
        approvedAt=to_local_iso(order.approved_at),
        approvalComment=_clean_text(order.approval_comment, 1000),
        stockApplied=bool(order.stock_applied),
        canEdit=_can_edit_order(db, user, order),
        canReview=_can_review_order(user, order),
        canResubmit=_can_edit_order(db, user, order) and order.status == "rejected",
        items=[
            _to_order_item_out_with_stock(
                item,
                source_stock=(
                    _inventory_quantity_for_goods_shop(db, item.goods_id, item.ship_shop_id)
                    if (order.order_type == "sale" and bool(order.sale_affects_inventory))
                    else source_stock_map.get(int(item.goods_id), 0)
                ) if item.goods_id is not None else 0,
                target_stock=target_stock_map.get(int(item.goods_id), 0) if item.goods_id is not None else 0,
            )
            for item in ordered_items
        ],
        actions=[_to_action_out(item) for item in sorted(order.actions or [], key=lambda row: (row.created_at, int(row.id or 0)))],
    )


def _append_action(
    db: Session,
    *,
    order: AqcWorkOrder,
    actor: AqcUser,
    action_type: str,
    status_from: str,
    status_to: str,
    comment: str = "",
) -> None:
    db.add(
        AqcWorkOrderAction(
            work_order_id=order.id,
            action_type=_clean_text(action_type, 20),
            status_from=_clean_text(status_from, 20),
            status_to=_clean_text(status_to, 20),
            comment=_clean_text(comment, 1000),
            actor_id=actor.id,
            actor_name=_display_name(actor),
        )
    )


def _query_scope_filter(user: AqcUser, scope: str):
    clean_scope = _clean_text(scope, 20) or "mine"
    if clean_scope == "draft":
        return AqcWorkOrder.status.in_(sorted(DRAFT_STATUSES))
    if clean_scope == "pending":
        return AqcWorkOrder.applicant_id == user.id, AqcWorkOrder.status == "pending"
    if clean_scope == "approver":
        return AqcWorkOrder.approver_id == user.id, AqcWorkOrder.status == "pending"
    if clean_scope == "all" and _is_admin(user):
        return None
    if clean_scope == "all":
        return or_(AqcWorkOrder.applicant_id == user.id, AqcWorkOrder.approver_id == user.id)
    return AqcWorkOrder.applicant_id == user.id


def _scope_extra_conditions(db: Session, user: AqcUser, scope: str):
    clean_scope = _clean_text(scope, 20) or "mine"
    group_ids = _group_ids_for_user(db, int(user.id or 0))
    shared_draft_condition = (
        AqcWorkOrder.shared_group_id.in_(group_ids)
        if group_ids
        else AqcWorkOrder.shared_group_id == -1
    )
    if clean_scope == "draft":
        return or_(AqcWorkOrder.applicant_id == user.id, shared_draft_condition)
    return None


def _get_accessible_groups(db: Session, user: AqcUser) -> list[WorkOrderGroupOptionOut]:
    rows = db.execute(
        select(AqcGroupMember, AqcGroup)
        .join(AqcGroup, AqcGroup.id == AqcGroupMember.group_id)
        .where(AqcGroupMember.user_id == int(user.id), AqcGroup.is_active.is_(True))
        .order_by(AqcGroup.updated_at.desc(), AqcGroup.id.desc())
    ).all()
    group_ids = [int(group.id) for _, group in rows]
    member_counts = {}
    if group_ids:
        count_rows = db.execute(
            select(AqcGroupMember.group_id, func.count(AqcGroupMember.id))
            .where(AqcGroupMember.group_id.in_(group_ids))
            .group_by(AqcGroupMember.group_id)
        ).all()
        member_counts = {int(group_id): int(count or 0) for group_id, count in count_rows}
    return [
        WorkOrderGroupOptionOut(
            id=int(group.id),
            name=_clean_text(group.name, 80),
            description=_clean_text(group.description, 2000),
            memberRole=_clean_text(member.member_role, 20),
            memberCount=member_counts.get(int(group.id), 0),
            isDefault=bool(member.is_default),
        )
        for member, group in rows
    ]


def _validate_approver(db: Session, applicant: AqcUser, approver_id: int | None) -> AqcUser | None:
    if approver_id is None:
        raise ValueError("请选择负责人")
    approver = db.execute(select(AqcUser).where(AqcUser.id == approver_id, AqcUser.is_active.is_(True)).limit(1)).scalars().first()
    if approver is None:
        raise ValueError("负责人不存在或已停用")
    if int(approver.id) == int(applicant.id) and not _is_admin(applicant):
        raise ValueError("负责人不能选择本人")
    if get_aqc_role_key(approver) != "aqc_admin":
        raise ValueError("负责人必须为管理员账号")
    return approver


def _validate_shop_for_type(order_type: str, source_shop: AqcShop | None, target_shop: AqcShop | None) -> None:
    if order_type == "transfer":
        if source_shop is None or target_shop is None:
            raise ValueError("调拨单必须选择发货店铺/仓库和收货店铺/仓库")
        if int(source_shop.id) == int(target_shop.id):
            raise ValueError("发货店铺/仓库和收货店铺/仓库不能相同")
        return
    if order_type == "purchase":
        if target_shop is None:
            raise ValueError("进货单必须选择收货店铺/仓库")
        return
    if order_type in {"return", "damage"}:
        if source_shop is None:
            raise ValueError("当前工单必须选择发货店铺/仓库")
        return
    if order_type in SALES_ORDER_TYPES:
        if source_shop is None:
            raise ValueError("销售类工单必须选择销售店铺")
        if int(source_shop.shop_type or 0) != SHOP_TYPE_STORE:
            raise ValueError("销售类工单只能选择销售店铺")


def _default_reason(
    order_type: str,
    form_date: datetime,
    source_shop: AqcShop | None,
    target_shop: AqcShop | None,
) -> str:
    date_text = f"{form_date.year}年{form_date.month}月{form_date.day}日"
    source_name = _clean_text(source_shop.name if source_shop else "", 255) or (
        "未选择销售店铺" if order_type in SALES_ORDER_TYPES else "未选择发货店铺/仓库"
    )
    target_name = _clean_text(target_shop.name if target_shop else "", 255) or "未选择收货店铺/仓库"
    if order_type == "transfer":
        return f"{date_text}-{source_name}-调往-{target_name}-调拨单"
    if order_type == "purchase":
        return f"{date_text}-{target_name}-进货单"
    if order_type == "return":
        return f"{date_text}-{source_name}-退货单"
    if order_type == "damage":
        return f"{date_text}-{source_name}-报损单"
    if order_type == "sale":
        return f"{date_text}-销售单"
    if order_type == "sale_return":
        return f"{date_text}-销售退货单"
    if order_type == "sale_exchange":
        return f"{date_text}-销售换货单"
    return f"{date_text}-工单"


def _prepare_items_for_save(
    db: Session,
    order_type: str,
    payload_items: list[WorkOrderItemInput],
    *,
    strict: bool,
    sale_affects_inventory: bool = False,
) -> list[dict]:
    prepared: list[dict] = []
    is_sales_type = order_type in SALES_ORDER_TYPES
    is_exchange_type = order_type == "sale_exchange"
    is_inventory_sale_type = order_type == "sale" and bool(sale_affects_inventory)
    for index, row in enumerate(payload_items):
        line_type = _clean_text(row.lineType, 20) or ("incoming" if is_exchange_type else "default")
        goods_id = int(row.goodsId) if row.goodsId is not None else None
        goods = None
        if goods_id is not None:
            goods = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == goods_id).limit(1)).scalars().first()
            if goods is None and strict:
                raise ValueError(f"第 {index + 1} 行选择的商品不存在")

        goods_name = _clean_text(goods.model_name if goods else row.goodsName, 191)
        if not goods_name:
            goods_name, _ = split_model_attribute(row.goodsName or "")
        source_order_num = _clean_text(row.orderNum, 64)
        salesperson = _clean_text(row.salesperson, 80)
        sale_record_id = int(row.saleRecordId) if row.saleRecordId is not None else None
        sale_shop_id = int(row.saleShopId) if row.saleShopId is not None else None
        sale_shop_name = _clean_text(row.saleShopName, 255)
        receive_shop_id = int(row.receiveShopId) if row.receiveShopId is not None else None
        receive_shop_name = _clean_text(row.receiveShopName, 255)
        ship_shop_id = int(row.shipShopId) if row.shipShopId is not None else None
        ship_shop_name = _clean_text(row.shipShopName, 255)
        product_code = ""
        brand = _clean_text(goods.brand if goods else row.brand, 120)
        series_name = _clean_text(goods.series_name if goods else row.series, 120)
        barcode = _clean_text(goods.barcode if goods else row.barcode, 64)
        unit_price = _to_amount(row.unitPrice if row.unitPrice not in (None, 0) else (goods.price if goods else 0))
        received_amount = _to_amount(row.receivedAmount)
        receivable_amount = _to_amount(row.receivableAmount)
        coupon_amount = _to_amount(row.couponAmount)
        discount_rate = _to_amount(row.discountRate if row.discountRate is not None else 10)
        quantity = int(row.quantity or 0)
        channel = _clean_text(row.channel, 50)
        customer_name = _clean_text(row.customerName, 120)
        remark = _clean_text(row.remark, 255)
        is_new_goods = False

        if not any([
            line_type,
            goods_id,
            goods_name,
            product_code,
            brand,
            series_name,
            barcode,
            quantity,
            remark,
            source_order_num,
            salesperson,
            sale_record_id,
            sale_shop_id,
            sale_shop_name,
            receive_shop_id,
            receive_shop_name,
            ship_shop_id,
            ship_shop_name,
            received_amount,
            receivable_amount,
            coupon_amount,
            channel,
            customer_name,
        ]):
            continue

        if strict:
            if goods is None:
                if order_type != "purchase":
                    raise ValueError(f"第 {index + 1} 行必须选择已有商品")
                if not goods_name:
                    raise ValueError(f"第 {index + 1} 行请填写商品型号")
                is_new_goods = True
            if quantity <= 0:
                raise ValueError(f"第 {index + 1} 行数量必须大于 0")
            if is_sales_type:
                if order_type in SALES_RETURN_LIKE_TYPES and line_type != "outgoing":
                    if sale_record_id is None:
                        raise ValueError(f"第 {index + 1} 行必须绑定销售记录")
                    if not source_order_num:
                        raise ValueError(f"第 {index + 1} 行必须选择销售订单")
                    if not salesperson:
                        raise ValueError(f"第 {index + 1} 行必须填写销售员")
                    if receivable_amount <= Decimal("0.00"):
                        raise ValueError(f"第 {index + 1} 行应付金额必须大于 0")
                    sale_record = db.execute(
                        select(AqcSaleRecord).where(AqcSaleRecord.id == sale_record_id).limit(1)
                    ).scalars().first()
                    if sale_record is None:
                        raise ValueError(f"第 {index + 1} 行绑定的销售记录不存在")
                    if _clean_text(sale_record.sale_status, 20) != "normal":
                        raise ValueError(f"第 {index + 1} 行销售记录已处理退货，不能重复提交")
                    if sale_shop_id is None and sale_record.shop_id is not None:
                        sale_shop_id = int(sale_record.shop_id)
                    if not sale_shop_name:
                        sale_shop_name = _clean_text(sale_record.shop_name, 255)
                    if receive_shop_id is None:
                        receive_shop_id = sale_shop_id
                    if receive_shop_id is not None:
                        receive_shop = db.execute(select(AqcShop).where(AqcShop.id == receive_shop_id).limit(1)).scalars().first()
                        if receive_shop is None:
                            raise ValueError(f"第 {index + 1} 行收货店铺/仓库不存在")
                        if not receive_shop_name:
                            receive_shop_name = _clean_text(receive_shop.name, 255)
                else:
                    if not salesperson:
                        raise ValueError(f"第 {index + 1} 行必须填写销售员")
                    if receivable_amount <= Decimal("0.00"):
                        raise ValueError(f"第 {index + 1} 行应付金额必须大于 0")
                    if received_amount <= Decimal("0.00"):
                        raise ValueError(f"第 {index + 1} 行实付金额必须大于 0")
                    if sale_shop_id is None:
                        raise ValueError(f"第 {index + 1} 行必须选择销售店铺")
                    sale_shop = db.execute(select(AqcShop).where(AqcShop.id == sale_shop_id).limit(1)).scalars().first()
                    if sale_shop is None or int(sale_shop.shop_type or 0) != SHOP_TYPE_STORE:
                        raise ValueError(f"第 {index + 1} 行销售店铺不存在或不是店铺")
                    if not sale_shop_name:
                        sale_shop_name = _clean_text(sale_shop.name, 255)
                    if ship_shop_id is None:
                        raise ValueError(f"第 {index + 1} 行必须选择发货店铺/仓库")
                    ship_shop = db.execute(select(AqcShop).where(AqcShop.id == ship_shop_id).limit(1)).scalars().first()
                    if ship_shop is None:
                        raise ValueError(f"第 {index + 1} 行发货店铺/仓库不存在")
                    if not ship_shop_name:
                        ship_shop_name = _clean_text(ship_shop.name, 255)
                    if not channel:
                        channel = "门店"
                    if is_inventory_sale_type and not goods_name:
                        raise ValueError(f"第 {index + 1} 行必须填写商品名称")

        quantity = max(quantity, 1 if strict else quantity)
        total_amount = _to_amount(
            row.totalAmount
            if row.totalAmount not in (None, 0)
            else (
                receivable_amount
                if is_sales_type and receivable_amount > Decimal("0.00")
                else (unit_price * quantity if quantity > 0 else 0)
            )
        )
        if is_sales_type and receivable_amount <= Decimal("0.00"):
            receivable_amount = total_amount
        prepared.append(
            {
                "sort_index": index,
                "line_type": line_type,
                "goods_id": goods.id if goods is not None else None,
                "sale_record_id": sale_record_id,
                "source_order_num": source_order_num,
                "salesperson": salesperson,
                "sale_shop_id": sale_shop_id,
                "sale_shop_name": sale_shop_name,
                "receive_shop_id": receive_shop_id,
                "receive_shop_name": receive_shop_name,
                "ship_shop_id": ship_shop_id,
                "ship_shop_name": ship_shop_name,
                "goods_name": goods_name,
                "product_code": product_code,
                "brand": brand,
                "series_name": series_name,
                "barcode": barcode,
                "unit_price": unit_price,
                "received_amount": received_amount,
                "receivable_amount": receivable_amount,
                "coupon_amount": coupon_amount,
                "discount_rate": discount_rate,
                "quantity": quantity,
                "total_amount": total_amount,
                "channel": channel,
                "customer_name": customer_name,
                "remark": remark,
                "is_new_goods": bool(is_new_goods and goods is None),
            }
        )

    if strict and not prepared:
        raise ValueError("请至少填写一条工单明细")
    if strict and is_exchange_type:
        if not any(_clean_text(item["line_type"], 20) == "incoming" for item in prepared):
            raise ValueError("销售换货单至少需要一条换入明细")
        if not any(_clean_text(item["line_type"], 20) == "outgoing" for item in prepared):
            raise ValueError("销售换货单至少需要一条换出明细")
    return prepared


def _sync_order_items(order: AqcWorkOrder, items: list[dict]) -> None:
    existing_items = list(order.items or [])
    next_items: list[AqcWorkOrderItem] = []
    for index, row in enumerate(items):
        item = existing_items[index] if index < len(existing_items) else AqcWorkOrderItem()
        item.sort_index = int(row["sort_index"])
        item.goods_id = row["goods_id"]
        item.sale_record_id = row["sale_record_id"]
        item.line_type = row["line_type"]
        item.source_order_num = row["source_order_num"]
        item.salesperson = row["salesperson"]
        item.sale_shop_id = row["sale_shop_id"]
        item.sale_shop_name = row["sale_shop_name"]
        item.receive_shop_id = row["receive_shop_id"]
        item.receive_shop_name = row["receive_shop_name"]
        item.ship_shop_id = row["ship_shop_id"]
        item.ship_shop_name = row["ship_shop_name"]
        item.goods_name = row["goods_name"]
        item.product_code = row["product_code"]
        item.brand = row["brand"]
        item.series_name = row["series_name"]
        item.barcode = row["barcode"]
        item.unit_price = row["unit_price"]
        item.received_amount = row["received_amount"]
        item.receivable_amount = row["receivable_amount"]
        item.coupon_amount = row["coupon_amount"]
        item.discount_rate = row["discount_rate"]
        item.quantity = int(row["quantity"])
        item.total_amount = row["total_amount"]
        item.channel = row["channel"]
        item.customer_name = row["customer_name"]
        item.remark = row["remark"]
        item.is_new_goods = bool(row["is_new_goods"])
        next_items.append(item)
    order.items[:] = next_items


def _find_or_create_goods_for_item(
    db: Session,
    item: AqcWorkOrderItem,
    creator_id: int,
    *,
    allow_create: bool = False,
) -> AqcGoodsItem:
    if item.goods_id is not None:
        goods = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == item.goods_id).limit(1)).scalars().first()
        if goods is None:
            raise ValueError(f"商品 {item.goods_name or item.id} 不存在，无法执行库存变更")
        return goods
    if not allow_create:
        raise ValueError(f"商品 {item.goods_name or item.id} 未匹配到现有商品，不能执行库存变更")

    goods_name = _clean_text(item.goods_name, 191)
    if not goods_name:
        raise ValueError("进货单存在未填写商品型号的新商品，不能执行库存变更")
    brand = _clean_text(item.brand, 120)
    series_name = _clean_text(item.series_name, 120)
    clean_barcode = _clean_text(item.barcode, 64)
    if clean_barcode:
        matched_goods = db.execute(
            select(AqcGoodsItem).where(AqcGoodsItem.barcode == clean_barcode).order_by(AqcGoodsItem.id.desc()).limit(1)
        ).scalars().first()
        if matched_goods is not None:
            item.goods_id = int(matched_goods.id)
            item.goods_name = _clean_text(matched_goods.model_name, 191)
            item.product_code = ""
            item.brand = _clean_text(matched_goods.brand, 120)
            item.series_name = _clean_text(matched_goods.series_name, 120)
            item.barcode = _clean_text(matched_goods.barcode, 64)
            item.unit_price = _to_amount(item.unit_price or matched_goods.price or 0)
            item.is_new_goods = False
            return matched_goods
    else:
        signature_matches = _find_goods_by_signature(
            db,
            brand=brand,
            series=series_name,
            goods_name=goods_name,
        )
        if len(signature_matches) == 1:
            matched_goods = signature_matches[0]
            item.goods_id = int(matched_goods.id)
            item.goods_name = _clean_text(matched_goods.model_name, 191)
            item.product_code = ""
            item.brand = _clean_text(matched_goods.brand, 120)
            item.series_name = _clean_text(matched_goods.series_name, 120)
            item.barcode = _clean_text(matched_goods.barcode, 64)
            item.unit_price = _to_amount(item.unit_price or matched_goods.price or 0)
            item.is_new_goods = False
            return matched_goods
        if len(signature_matches) > 1:
            raise ValueError(f"商品 {goods_name} 存在同名但不同条码的记录，请补充条码或手动匹配后再审批")

    display_name = compose_goods_name(brand, series_name, goods_name, goods_name)
    goods = AqcGoodsItem(
        name=display_name,
        product_code="",
        brand=brand,
        series_name=series_name,
        model_name=goods_name,
        model_attribute="-",
        barcode=clean_barcode,
        index_key=_normalize_index_key(goods_name, brand, series_name),
        price=_to_amount(item.unit_price or 0),
        original_price=_to_amount(item.unit_price or 0),
        sale_price=_to_amount(item.unit_price or 0),
        stock=0,
        sale_num=0,
        sort=0,
        putaway=1,
        status=3,
        goods_type=0,
        remark="进货单自动新增商品",
        created_by=creator_id,
    )
    db.add(goods)
    db.flush()
    item.goods_id = int(goods.id)
    item.goods_name = _clean_text(goods.model_name, 191)
    item.product_code = ""
    item.brand = _clean_text(goods.brand, 120)
    item.series_name = _clean_text(goods.series_name, 120)
    item.barcode = _clean_text(goods.barcode, 64)
    item.is_new_goods = True
    return goods


def _order_type_affects_inventory(order_type: str) -> bool:
    return order_type in {"transfer", "purchase", "return", "damage", "sale_return", "sale_exchange"}


def _apply_work_order_inventory(db: Session, order: AqcWorkOrder, *, actor: AqcUser | None = None) -> None:
    if not _order_type_affects_inventory(order.order_type):
        return
    touched_goods_ids: set[int] = set()
    shop_map = _get_shop_map(db)
    for item in order.items or []:
        goods = _find_or_create_goods_for_item(
            db,
            item,
            order.applicant_id,
            allow_create=order.order_type == "purchase",
        )
        goods_id = int(goods.id)
        quantity = int(item.quantity or 0)
        if quantity <= 0:
            continue

        if order.order_type == "transfer":
            if order.source_shop_id is None or order.target_shop_id is None:
                raise ValueError("调拨单缺少发货或收货店铺/仓库")
            source_shop = shop_map.get(int(order.source_shop_id))
            target_shop = shop_map.get(int(order.target_shop_id))
            if source_shop is None or target_shop is None:
                raise ValueError("调拨单的发货或收货店铺/仓库不存在")
            apply_inventory_delta(
                db,
                goods_item=goods,
                shop=source_shop,
                delta=-quantity,
                change_content=f"工单审批通过：{_work_order_type_label(order.order_type)} {order.order_num}",
                operator_id=actor.id if actor is not None else None,
                operator_name=_display_name(actor),
                related_type="work_order",
                related_id=int(order.id),
            )
            apply_inventory_delta(
                db,
                goods_item=goods,
                shop=target_shop,
                delta=quantity,
                change_content=f"工单审批通过：{_work_order_type_label(order.order_type)} {order.order_num}",
                operator_id=actor.id if actor is not None else None,
                operator_name=_display_name(actor),
                related_type="work_order",
                related_id=int(order.id),
            )
        elif order.order_type == "purchase":
            if order.target_shop_id is None:
                raise ValueError("进货单缺少收货仓库/店铺")
            target_shop = shop_map.get(int(order.target_shop_id))
            if target_shop is None:
                raise ValueError("进货单的收货仓库/店铺不存在")
            apply_inventory_delta(
                db,
                goods_item=goods,
                shop=target_shop,
                delta=quantity,
                change_content=f"工单审批通过：{_work_order_type_label(order.order_type)} {order.order_num}",
                operator_id=actor.id if actor is not None else None,
                operator_name=_display_name(actor),
                related_type="work_order",
                related_id=int(order.id),
            )
        elif order.order_type in {"return", "damage"}:
            if order.source_shop_id is None:
                raise ValueError("工单缺少发货仓库/店铺")
            source_shop = shop_map.get(int(order.source_shop_id))
            if source_shop is None:
                raise ValueError("工单的发货仓库/店铺不存在")
            apply_inventory_delta(
                db,
                goods_item=goods,
                shop=source_shop,
                delta=-quantity,
                change_content=f"工单审批通过：{_work_order_type_label(order.order_type)} {order.order_num}",
                operator_id=actor.id if actor is not None else None,
                operator_name=_display_name(actor),
                related_type="work_order",
                related_id=int(order.id),
            )
        touched_goods_ids.add(goods_id)

    db.flush()
    if touched_goods_ids:
        recalculate_goods_stock(db, sorted(touched_goods_ids))


def _resolve_sale_record_shop(db: Session, record: AqcSaleRecord) -> AqcShop | None:
    target_shop_id = int(record.ship_shop_id or record.shop_id or 0)
    if target_shop_id <= 0:
        return None
    return db.execute(select(AqcShop).where(AqcShop.id == target_shop_id).limit(1)).scalars().first()


def _resolve_sale_return_receive_shop(db: Session, item: AqcWorkOrderItem, record: AqcSaleRecord) -> AqcShop | None:
    target_shop_id = int(item.receive_shop_id or 0)
    if target_shop_id > 0:
        return db.execute(select(AqcShop).where(AqcShop.id == target_shop_id).limit(1)).scalars().first()
    return _resolve_sale_record_shop(db, record)


def _compute_sale_ratio(quantity: int, base_quantity: int) -> Decimal:
    safe_base = max(int(base_quantity or 0), 1)
    safe_quantity = max(int(quantity or 0), 1)
    return (Decimal(str(safe_quantity)) / Decimal(str(safe_base))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _build_sale_return_note(order: AqcWorkOrder, source_record: AqcSaleRecord) -> str:
    source_order_num = _clean_text(source_record.order_num, 32) or f"记录{int(source_record.id or 0)}"
    return f"销售退货单 {order.order_num}；原订单 {source_order_num}"[:5000]


def _apply_sale_return_item(
    db: Session,
    order: AqcWorkOrder,
    item: AqcWorkOrderItem,
    *,
    actor: AqcUser | None = None,
    note_builder=None,
) -> int | None:
    source_sale_id = int(item.sale_record_id or 0)
    if source_sale_id <= 0:
        raise ValueError("销售退货明细存在未绑定销售记录的行，不能审批")
    source_record = db.execute(
        select(AqcSaleRecord).where(AqcSaleRecord.id == source_sale_id).limit(1)
    ).scalars().first()
    if source_record is None:
        raise ValueError(f"销售记录 {source_sale_id} 不存在，不能执行退货")
    if _clean_text(source_record.sale_status, 20) != "normal":
        raise ValueError(f"订单 {source_record.order_num or source_sale_id} 已处理退货，不能重复审批")

    goods = _find_or_create_goods_for_item(db, item, order.applicant_id)
    shop = _resolve_sale_return_receive_shop(db, item, source_record)
    if shop is None:
        raise ValueError(f"订单 {source_record.order_num or source_sale_id} 缺少归属店铺/仓库，不能执行退货")

    now = _now_shanghai()
    return_quantity = max(int(item.quantity or 0), 1)
    apply_inventory_delta(
        db,
        goods_item=goods,
        shop=shop,
        delta=return_quantity,
        change_content=f"工单审批通过：{_work_order_type_label(order.order_type)} {order.order_num}",
        operator_id=actor.id if actor is not None else None,
        operator_name=_display_name(actor),
        related_type="work_order",
        related_id=int(order.id),
    )

    ratio = _compute_sale_ratio(return_quantity, int(source_record.quantity or 0))
    source_received = _to_amount(source_record.amount or 0)
    source_receivable = _to_amount(source_record.receivable_amount or 0)
    source_coupon = _to_amount(source_record.coupon_amount or 0)
    return_received = (source_received * ratio).copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return_receivable = (source_receivable * ratio).copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return_coupon = (source_coupon * ratio).copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if return_receivable <= Decimal("0.00"):
        return_receivable = _to_amount(item.receivable_amount or item.total_amount or 0).copy_abs()
    if return_received <= Decimal("0.00"):
        return_received = _to_amount(item.received_amount or return_receivable).copy_abs()

    if return_receivable <= Decimal("0.00") or return_received >= return_receivable:
        discount_rate = Decimal("10.00")
    else:
        discount_rate = (return_received / return_receivable * Decimal("10")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    negative_record = AqcSaleRecord(
        sold_at=order.form_date,
        order_num=_generate_sale_order_num(db, order.form_date),
        goods_id=goods.id,
        goods_code=_clean_text(source_record.goods_code or item.product_code, 64),
        goods_brand=_clean_text(source_record.goods_brand or item.brand, 120),
        goods_series=_clean_text(source_record.goods_series or item.series_name, 120),
        goods_model=_clean_text(source_record.goods_model or item.goods_name, 191),
        goods_barcode=_clean_text(source_record.goods_barcode or item.barcode, 64),
        unit_price=_to_amount(item.unit_price or source_record.unit_price or 0),
        receivable_amount=-return_receivable,
        amount=-return_received,
        coupon_amount=return_coupon,
        discount_rate=discount_rate,
        quantity=-return_quantity,
        channel=_clean_text(source_record.channel, 50),
        shop_id=source_record.shop_id,
        shop_name=_clean_text(source_record.shop_name, 255),
        ship_shop_id=shop.id,
        ship_shop_name=_clean_text(shop.name, 255),
        salesperson=_clean_text(source_record.salesperson or item.salesperson, 80),
        index_key=_clean_text(source_record.index_key, 8),
        sale_status="return_entry",
        source_sale_record_id=int(source_record.id),
        related_work_order_id=int(order.id),
        returned_at=now,
        customer_name=_clean_text(source_record.customer_name, 120),
        note=(note_builder(source_record) if callable(note_builder) else _build_sale_return_note(order, source_record)),
        created_by=actor.id if actor is not None else order.applicant_id,
    )
    db.add(negative_record)

    source_record.sale_status = "returned"
    source_record.related_work_order_id = int(order.id)
    source_record.returned_at = now
    return int(goods.id)


def _apply_sale_return_order(db: Session, order: AqcWorkOrder, *, actor: AqcUser | None = None) -> None:
    touched_goods_ids: set[int] = set()
    for item in order.items or []:
        goods_id = _apply_sale_return_item(db, order, item, actor=actor)
        if goods_id:
            touched_goods_ids.add(goods_id)
    db.flush()
    if touched_goods_ids:
        recalculate_goods_stock(db, sorted(touched_goods_ids))


def _build_sale_exchange_return_note(order: AqcWorkOrder, source_record: AqcSaleRecord) -> str:
    source_order_num = _clean_text(source_record.order_num, 32) or f"记录{int(source_record.id or 0)}"
    return f"销售换货单 {order.order_num}；退回原订单 {source_order_num}"[:5000]


def _build_sale_exchange_sale_note(order: AqcWorkOrder, item: AqcWorkOrderItem) -> str:
    goods_name = _clean_text(item.goods_name, 191) or _clean_text(item.barcode, 64) or "商品"
    return f"销售换货单 {order.order_num}；换出新订单 {goods_name}"[:5000]


def _build_sale_order_note(order: AqcWorkOrder, item: AqcWorkOrderItem, sale_order_num: str) -> str:
    goods_name = _clean_text(item.goods_name, 191) or _clean_text(item.barcode, 64) or "商品"
    return f"销售单 {order.order_num}；生成订单 {sale_order_num}；{goods_name}"[:5000]


def _apply_sale_outgoing_items(
    db: Session,
    order: AqcWorkOrder,
    items: list[AqcWorkOrderItem],
    *,
    actor: AqcUser | None = None,
    shared_order_num: str | None = None,
    note_builder=None,
) -> None:
    touched_goods_ids: set[int] = set()
    shop_map = _get_shop_map(db)
    for item in items:
        goods = _find_or_create_goods_for_item(db, item, order.applicant_id)
        sale_shop_id = int(item.sale_shop_id or order.source_shop_id or 0)
        if sale_shop_id <= 0:
            raise ValueError("销售单明细缺少销售店铺")
        sale_shop = shop_map.get(sale_shop_id)
        if sale_shop is None or int(sale_shop.shop_type or 0) != SHOP_TYPE_STORE:
            raise ValueError("销售单明细的销售店铺不存在")
        ship_shop_id = int(item.ship_shop_id or sale_shop_id)
        ship_shop = shop_map.get(ship_shop_id)
        if ship_shop is None:
            raise ValueError("销售单明细的发货店铺/仓库不存在")
        quantity = max(int(item.quantity or 0), 1)
        apply_inventory_delta(
            db,
            goods_item=goods,
            shop=ship_shop,
            delta=-quantity,
            change_content=f"工单审批通过：{_work_order_type_label(order.order_type)} {order.order_num}",
            operator_id=actor.id if actor is not None else None,
            operator_name=_display_name(actor),
            related_type="work_order",
            related_id=int(order.id),
        )
        touched_goods_ids.add(int(goods.id))
        receivable_amount = _to_amount(item.receivable_amount or item.total_amount or (item.unit_price or 0) * quantity)
        received_amount = _to_amount(item.received_amount or receivable_amount)
        coupon_amount = _to_amount(item.coupon_amount or 0)
        discount_rate = _to_amount(item.discount_rate or 10)
        sale_order_num = _clean_text(shared_order_num, 32) or _generate_sale_order_num(db, order.form_date)
        db.add(
            AqcSaleRecord(
                sold_at=order.form_date,
                order_num=sale_order_num,
                goods_id=goods.id,
                goods_code=_clean_text(item.product_code or goods.product_code, 64),
                goods_brand=_clean_text(item.brand or goods.brand, 120),
                goods_series=_clean_text(item.series_name or goods.series_name, 120),
                goods_model=_clean_text(item.goods_name or goods.model_name, 191),
                goods_barcode=_clean_text(item.barcode or goods.barcode, 64),
                unit_price=_to_amount(item.unit_price or goods.price or 0),
                receivable_amount=receivable_amount,
                amount=received_amount,
                coupon_amount=coupon_amount,
                discount_rate=discount_rate,
                quantity=quantity,
                channel=_clean_text(item.channel, 50) or "门店",
                shop_id=sale_shop.id,
                shop_name=_clean_text(sale_shop.name, 255),
                ship_shop_id=ship_shop.id,
                ship_shop_name=_clean_text(ship_shop.name, 255),
                salesperson=_clean_text(item.salesperson, 80),
                index_key=_clean_text(goods.index_key, 8),
                sale_status="normal",
                related_work_order_id=int(order.id),
                customer_name=_clean_text(item.customer_name, 120),
                note=(note_builder(item, sale_order_num) if callable(note_builder) else _build_sale_order_note(order, item, sale_order_num)),
                created_by=actor.id if actor is not None else order.applicant_id,
            )
        )
    db.flush()
    if touched_goods_ids:
        recalculate_goods_stock(db, sorted(touched_goods_ids))


def _apply_sale_exchange_order(db: Session, order: AqcWorkOrder, *, actor: AqcUser | None = None) -> None:
    touched_goods_ids: set[int] = set()
    ordered_items = sorted(order.items or [], key=lambda row: (int(row.sort_index or 0), int(row.id or 0)))
    incoming_items = [item for item in ordered_items if _clean_text(item.line_type, 20) != "outgoing"]
    outgoing_items = [item for item in ordered_items if _clean_text(item.line_type, 20) == "outgoing"]

    for item in incoming_items:
        goods_id = _apply_sale_return_item(
            db,
            order,
            item,
            actor=actor,
            note_builder=lambda source_record: _build_sale_exchange_return_note(order, source_record),
        )
        if goods_id:
            touched_goods_ids.add(goods_id)

    default_salesperson = _clean_text(incoming_items[0].salesperson if incoming_items else "", 80)
    for item in outgoing_items:
        if not _clean_text(item.salesperson, 80):
            item.salesperson = default_salesperson
    _apply_sale_outgoing_items(
        db,
        order,
        outgoing_items,
        actor=actor,
        note_builder=lambda item, _sale_order_num: _build_sale_exchange_sale_note(order, item),
    )


def _apply_sale_order_with_inventory(db: Session, order: AqcWorkOrder, *, actor: AqcUser | None = None) -> None:
    ordered_items = sorted(order.items or [], key=lambda row: (int(row.sort_index or 0), int(row.id or 0)))
    if not ordered_items:
        return
    shared_order_num = _generate_sale_order_num(db, order.form_date)
    _apply_sale_outgoing_items(
        db,
        order,
        ordered_items,
        actor=actor,
        shared_order_num=shared_order_num,
        note_builder=lambda item, sale_order_num: _build_sale_order_note(order, item, sale_order_num),
    )


def _loads(value: str | None) -> list:
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _schedule_period_label(period_key: str) -> str:
    return WORK_ORDER_SCHEDULE_PERIODS.get(_clean_text(period_key, 20), "按日")


def _to_schedule_out(item: AqcWorkOrderSchedule) -> WorkOrderScheduleOut:
    shop_ids = [int(shop_id) for shop_id in _loads(item.shop_ids_json) if int(shop_id) > 0]
    shop_names = [_clean_text(name, 255) for name in _loads(item.shop_names_json) if _clean_text(name, 255)]
    return WorkOrderScheduleOut(
        id=int(item.id),
        orderType=_clean_text(item.order_type, 20),
        orderTypeLabel=_work_order_type_label(item.order_type),
        periodKey=_clean_text(item.period_key, 20),
        periodLabel=_schedule_period_label(item.period_key),
        shopIds=shop_ids,
        shopNames=shop_names,
        applicantId=int(item.applicant_id),
        applicantName=_clean_text(item.applicant_name, 80),
        approverId=int(item.approver_id) if item.approver_id is not None else None,
        approverName=_clean_text(item.approver_name, 80),
        groupId=int(item.shared_group_id) if item.shared_group_id is not None else None,
        groupName=_clean_text(item.shared_group_name, 80),
        enabled=bool(item.enabled),
        lastPeriodKey=_clean_text(item.last_period_key, 32),
        lastRunAt=to_local_iso(item.last_run_at),
        createdAt=to_iso(item.created_at) or "",
        updatedAt=to_iso(item.updated_at) or "",
    )


def _schedule_period_window(now: datetime, period_key: str) -> tuple[str, datetime, datetime] | None:
    period = _clean_text(period_key, 20) or "day"
    current_day_start = datetime(now.year, now.month, now.day)
    run_threshold = current_day_start + timedelta(minutes=5)
    if period == "day":
        if now < run_threshold:
            return None
        target_day = current_day_start - timedelta(days=1)
        start = target_day
        end = target_day + timedelta(days=1) - timedelta(microseconds=1)
        return target_day.strftime("%Y-%m-%d"), start, end
    if period == "week":
        if now.weekday() != 0 or now < run_threshold:
            return None
        current_week_start = current_day_start - timedelta(days=current_day_start.weekday())
        target_start = current_week_start - timedelta(days=7)
        target_end = current_week_start - timedelta(microseconds=1)
        return target_start.strftime("%Y-%m-%d"), target_start, target_end
    if period == "month":
        if now.day != 1 or now < run_threshold:
            return None
        target_end = current_day_start - timedelta(microseconds=1)
        target_start = datetime(target_end.year, target_end.month, 1)
        return target_start.strftime("%Y-%m"), target_start, target_end
    return None


def _create_schedule_sale_order(
    db: Session,
    *,
    schedule: AqcWorkOrderSchedule,
    shop: AqcShop,
    records: list[AqcSaleRecord],
    form_date: datetime,
) -> None:
    if not records:
        return
    order = AqcWorkOrder(
        order_num=_generate_order_num(db, "sale"),
        order_type="sale",
        status="pending",
        reason=_default_reason("sale", form_date, shop, None),
        form_date=form_date,
        source_shop_id=int(shop.id),
        source_shop_name=_clean_text(shop.name, 255),
        applicant_id=int(schedule.applicant_id),
        applicant_name=_clean_text(schedule.applicant_name, 80),
        approver_id=int(schedule.approver_id) if schedule.approver_id is not None else None,
        approver_name=_clean_text(schedule.approver_name, 80),
        shared_group_id=int(schedule.shared_group_id) if schedule.shared_group_id is not None else None,
        shared_group_name=_clean_text(schedule.shared_group_name, 80),
        shared_by_id=None,
        shared_by_name="",
        submitted_at=form_date,
        stock_applied=False,
    )
    db.add(order)
    db.flush()
    for index, record in enumerate(records):
        receivable_amount = _to_amount(record.receivable_amount or record.amount or 0)
        received_amount = _to_amount(record.amount or 0)
        quantity = max(int(record.quantity or 0), 1)
        order.items.append(
            AqcWorkOrderItem(
                sort_index=index,
                goods_id=record.goods_id,
                sale_record_id=int(record.id),
                source_order_num=_clean_text(record.order_num, 64),
                salesperson=_clean_text(record.salesperson, 80),
                sale_shop_id=int(record.shop_id) if record.shop_id is not None else None,
                sale_shop_name=_clean_text(record.shop_name, 255),
                goods_name=_clean_text(record.goods_model, 191),
                product_code=_clean_text(record.goods_code, 64),
                brand=_clean_text(record.goods_brand, 120),
                series_name=_clean_text(record.goods_series, 120),
                barcode=_clean_text(record.goods_barcode, 64),
                unit_price=_to_amount(record.unit_price or 0),
                received_amount=received_amount.copy_abs(),
                receivable_amount=receivable_amount.copy_abs(),
                quantity=quantity,
                total_amount=receivable_amount.copy_abs(),
                remark="定时开单自动生成",
                is_new_goods=False,
            )
        )
    db.add(
        AqcWorkOrderAction(
            work_order_id=int(order.id),
            action_type="submitted",
            status_from="",
            status_to="pending",
            comment=f"定时开单自动生成（{_schedule_period_label(schedule.period_key)}）",
            actor_id=int(schedule.applicant_id),
            actor_name=_clean_text(schedule.applicant_name, 80),
        )
    )


def run_due_work_order_schedules_once() -> None:
    db = SessionLocal()
    try:
        now = _now_shanghai()
        schedules = db.execute(
            select(AqcWorkOrderSchedule)
            .where(AqcWorkOrderSchedule.enabled.is_(True))
            .order_by(AqcWorkOrderSchedule.updated_at.asc(), AqcWorkOrderSchedule.id.asc())
        ).scalars().all()
        if not schedules:
            return
        shop_map = _get_shop_map(db)
        for schedule in schedules:
            if _clean_text(schedule.order_type, 20) != "sale":
                continue
            period_window = _schedule_period_window(now, schedule.period_key)
            if period_window is None:
                continue
            period_key, start_at, end_at = period_window
            if _clean_text(schedule.last_period_key, 32) == period_key:
                continue
            schedule_shop_ids = [int(shop_id) for shop_id in _loads(schedule.shop_ids_json) if int(shop_id) > 0]
            generated = False
            for shop_id in schedule_shop_ids:
                shop = shop_map.get(int(shop_id))
                if shop is None:
                    continue
                records = db.execute(
                    select(AqcSaleRecord)
                    .where(
                        AqcSaleRecord.shop_id == int(shop.id),
                        AqcSaleRecord.sold_at >= start_at,
                        AqcSaleRecord.sold_at <= end_at,
                        AqcSaleRecord.sale_status != "return_entry",
                    )
                    .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
                ).scalars().all()
                if not records:
                    continue
                _create_schedule_sale_order(db, schedule=schedule, shop=shop, records=records, form_date=now)
                generated = True
            schedule.last_period_key = period_key
            schedule.last_run_at = now
            if generated:
                db.flush()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _schedule_runner_loop() -> None:
    while not SCHEDULE_RUNNER_STOP.wait(90):
        run_due_work_order_schedules_once()


def start_work_order_schedule_runner() -> None:
    global SCHEDULE_RUNNER_STARTED
    if SCHEDULE_RUNNER_STARTED:
        return
    SCHEDULE_RUNNER_STOP.clear()
    SCHEDULE_RUNNER_STARTED = True
    run_due_work_order_schedules_once()
    runner = Thread(target=_schedule_runner_loop, name="aqc-work-order-scheduler", daemon=True)
    runner.start()


def stop_work_order_schedule_runner() -> None:
    global SCHEDULE_RUNNER_STARTED
    SCHEDULE_RUNNER_STOP.set()
    SCHEDULE_RUNNER_STARTED = False


def _load_order_for_detail(db: Session, order_id: int) -> AqcWorkOrder | None:
    return (
        db.execute(
            select(AqcWorkOrder)
            .options(
                selectinload(AqcWorkOrder.items),
                selectinload(AqcWorkOrder.actions),
                selectinload(AqcWorkOrder.applicant),
                selectinload(AqcWorkOrder.approver),
            )
            .where(AqcWorkOrder.id == order_id)
            .limit(1)
        )
        .scalars()
        .first()
    )


def _allocation_source_shop_id(order: AqcWorkOrder) -> int | None:
    if _clean_text(order.order_type, 20) not in {"purchase", "transfer"}:
        return None
    source_shop_id = int(order.target_shop_id or 0)
    return source_shop_id if source_shop_id > 0 else None


def _can_allocate_order(db: Session, user: AqcUser, order: AqcWorkOrder) -> bool:
    return (
        _clean_text(order.status, 20) == "approved"
        and _clean_text(order.order_type, 20) in {"purchase", "transfer"}
        and bool(order.stock_applied)
        and _can_view_order(db, user, order)
    )


def _load_allocation_draft_rows(value: str | None) -> dict[int, dict[int, int]]:
    result: dict[int, dict[int, int]] = {}
    for raw_row in _loads(value):
        if not isinstance(raw_row, dict):
            continue
        item_id = int(raw_row.get("workOrderItemId") or 0)
        if item_id <= 0:
            continue
        target_map: dict[int, int] = {}
        for raw_target in raw_row.get("targets") or []:
            if not isinstance(raw_target, dict):
                continue
            shop_id = int(raw_target.get("shopId") or 0)
            quantity = int(raw_target.get("quantity") or 0)
            if shop_id <= 0 or quantity < 0:
                continue
            target_map[shop_id] = quantity
        result[item_id] = target_map
    return result


def _serialize_allocation_rows(payload_rows: list[dict]) -> str:
    return json.dumps(payload_rows, ensure_ascii=False)


def _inventory_quantity_matrix(
    db: Session,
    goods_ids: list[int],
    shop_ids: list[int],
) -> dict[tuple[int, int], int]:
    normalized_goods_ids = sorted({int(goods_id) for goods_id in goods_ids if int(goods_id or 0) > 0})
    normalized_shop_ids = sorted({int(shop_id) for shop_id in shop_ids if int(shop_id or 0) > 0})
    if not normalized_goods_ids or not normalized_shop_ids:
        return {}
    rows = db.execute(
        select(AqcGoodsInventory.goods_item_id, AqcGoodsInventory.shop_id, AqcGoodsInventory.quantity)
        .where(
            AqcGoodsInventory.goods_item_id.in_(normalized_goods_ids),
            AqcGoodsInventory.shop_id.in_(normalized_shop_ids),
        )
    ).all()
    return {
        (int(goods_id), int(shop_id)): int(quantity or 0)
        for goods_id, shop_id, quantity in rows
        if goods_id is not None and shop_id is not None
    }


def _available_allocation_target_options(
    db: Session,
    *,
    source_shop_id: int | None,
) -> list[WorkOrderShopOptionOut]:
    rows = (
        db.execute(
            select(AqcShop)
            .options(
                selectinload(AqcShop.assigned_users).load_only(
                    AqcUser.id,
                    AqcUser.username,
                    AqcUser.display_name,
                    AqcUser.is_active,
                    AqcUser.aqc_role_key,
                    AqcUser.role,
                )
            )
            .where(AqcShop.is_enabled.is_(True))
            .order_by(AqcShop.shop_type.asc(), AqcShop.id.asc())
        )
        .scalars()
        .all()
    )
    target_rows = [item for item in rows if int(item.id or 0) > 0 and int(item.id or 0) != int(source_shop_id or 0)]
    shop_member_map = _build_shop_member_map(db, [int(item.id) for item in target_rows if item.id is not None])
    return [_to_shop_option(item, shop_member_map.get(int(item.id), [])) for item in target_rows]


def _build_allocation_draft_out(
    db: Session,
    *,
    order: AqcWorkOrder,
    draft: AqcWorkOrderAllocationDraft | None,
) -> WorkOrderAllocationDraftOut:
    source_shop_id = _allocation_source_shop_id(order)
    if source_shop_id is None:
        raise ValueError("当前工单缺少可分配的发货仓库")
    source_shop = db.execute(select(AqcShop).where(AqcShop.id == int(source_shop_id)).limit(1)).scalars().first()
    if source_shop is None:
        raise ValueError("当前工单的分配发货仓库不存在")

    target_shop_ids = [int(shop_id) for shop_id in _loads(draft.target_shop_ids_json if draft else "[]") if int(shop_id) > 0]
    allocation_map = _load_allocation_draft_rows(draft.allocations_json if draft else "[]")
    shop_map = _get_shop_map(db)
    ordered_items = sorted(order.items or [], key=lambda row: (int(row.sort_index or 0), int(row.id or 0)))
    goods_ids = [int(item.goods_id) for item in ordered_items if item.goods_id is not None]
    inventory_matrix = _inventory_quantity_matrix(db, goods_ids, [source_shop_id, *target_shop_ids])

    rows: list[WorkOrderAllocationRowOut] = []
    for item in ordered_items:
        source_stock = inventory_matrix.get((int(item.goods_id or 0), int(source_shop_id)), 0) if item.goods_id is not None else 0
        saved_target_map = allocation_map.get(int(item.id or 0), {})
        targets: list[WorkOrderAllocationTargetOut] = []
        allocated_quantity = 0
        for target_shop_id in target_shop_ids:
            target_shop = shop_map.get(int(target_shop_id))
            if target_shop is None:
                continue
            quantity = int(saved_target_map.get(int(target_shop_id), 0) or 0)
            allocated_quantity += quantity
            targets.append(
                WorkOrderAllocationTargetOut(
                    shopId=int(target_shop.id),
                    shopName=_clean_text(target_shop.name, 255),
                    shortName=simplify_shop_name(target_shop.name),
                    shopType=int(target_shop.shop_type or 0),
                    currentStock=inventory_matrix.get((int(item.goods_id or 0), int(target_shop_id)), 0) if item.goods_id is not None else 0,
                    quantity=quantity,
                )
            )
        rows.append(
            WorkOrderAllocationRowOut(
                workOrderItemId=int(item.id),
                goodsId=int(item.goods_id) if item.goods_id is not None else None,
                goodsName=_clean_text(item.goods_name, 191),
                productCode=_clean_text(item.product_code, 64),
                brand=_clean_text(item.brand, 120),
                series=_clean_text(item.series_name, 120),
                barcode=_clean_text(item.barcode, 64),
                plannedQuantity=int(item.quantity or 0),
                sourceStock=source_stock,
                unitPrice=float(item.unit_price or 0),
                lineAmount=float(item.total_amount or 0),
                allocatedQuantity=allocated_quantity,
                targets=targets,
            )
        )

    return WorkOrderAllocationDraftOut(
        orderId=int(order.id),
        orderNum=_clean_text(order.order_num, 32),
        orderType=_clean_text(order.order_type, 20),
        sourceShopId=int(source_shop.id),
        sourceShopName=_clean_text(source_shop.name, 255),
        approverId=int(draft.approver_id) if draft and draft.approver_id is not None else (int(order.approver_id) if order.approver_id is not None else None),
        approverName=(
            _clean_text(draft.approver_name, 80)
            if draft is not None else _clean_text(order.approver_name, 80)
        ),
        groupId=int(order.shared_group_id) if order.shared_group_id is not None else None,
        groupName=_clean_text(order.shared_group_name, 80),
        targetShopIds=target_shop_ids,
        itemCount=len(rows),
        rows=rows,
        updatedAt=to_iso(draft.updated_at) if draft is not None else None,
    )


def _create_or_update_allocation_draft(
    db: Session,
    *,
    order: AqcWorkOrder,
    actor: AqcUser,
    payload: WorkOrderAllocationDraftSaveRequest,
) -> AqcWorkOrderAllocationDraft:
    source_shop_id = _allocation_source_shop_id(order)
    if source_shop_id is None:
        raise ValueError("当前工单不支持分配")
    source_shop = db.execute(select(AqcShop).where(AqcShop.id == int(source_shop_id)).limit(1)).scalars().first()
    if source_shop is None:
        raise ValueError("分配发货仓库不存在")

    approver = _validate_approver(db, actor, payload.approverId)
    available_targets = {
        int(item.id): item
        for item in _available_allocation_target_options(db, source_shop_id=source_shop_id)
    }
    target_shop_ids = []
    seen_target_ids: set[int] = set()
    for shop_id in payload.targetShopIds:
        normalized_id = int(shop_id or 0)
        if normalized_id <= 0 or normalized_id in seen_target_ids:
            continue
        if normalized_id not in available_targets:
            raise ValueError("所选分配店铺/仓库不存在或不可用")
        seen_target_ids.add(normalized_id)
        target_shop_ids.append(normalized_id)
    if not target_shop_ids:
        raise ValueError("请至少选择一个分配店铺/仓库")

    ordered_items = sorted(order.items or [], key=lambda row: (int(row.sort_index or 0), int(row.id or 0)))
    valid_item_ids = {int(item.id) for item in ordered_items if item.id is not None}
    serialized_rows: list[dict] = []
    for row in payload.rows:
        item_id = int(row.workOrderItemId or 0)
        if item_id <= 0 or item_id not in valid_item_ids:
            continue
        target_rows: list[dict] = []
        seen_item_target_ids: set[int] = set()
        for target in row.targets:
            shop_id = int(target.shopId or 0)
            if shop_id <= 0 or shop_id in seen_item_target_ids:
                continue
            if shop_id not in seen_target_ids:
                continue
            seen_item_target_ids.add(shop_id)
            target_rows.append(
                {
                    "shopId": shop_id,
                    "quantity": max(int(target.quantity or 0), 0),
                }
            )
        serialized_rows.append(
            {
                "workOrderItemId": item_id,
                "targets": target_rows,
            }
        )

    draft = order.allocation_draft
    if draft is None:
        draft = AqcWorkOrderAllocationDraft(
            work_order_id=int(order.id),
            created_by=int(actor.id),
            created_by_name=_display_name(actor),
        )
        db.add(draft)
        order.allocation_draft = draft
    draft.source_shop_id = int(source_shop.id)
    draft.source_shop_name = _clean_text(source_shop.name, 255)
    draft.approver_id = int(approver.id) if approver is not None else None
    draft.approver_name = _display_name(approver)
    draft.shared_group_id = int(order.shared_group_id) if order.shared_group_id is not None else None
    draft.shared_group_name = _clean_text(order.shared_group_name, 80)
    draft.target_shop_ids_json = json.dumps(target_shop_ids, ensure_ascii=False)
    draft.allocations_json = _serialize_allocation_rows(serialized_rows)
    draft.updated_by = int(actor.id)
    draft.updated_by_name = _display_name(actor)
    db.flush()
    return draft


def _build_generated_transfer_reason(
    source_order: AqcWorkOrder,
    *,
    source_shop: AqcShop,
    target_shop: AqcShop,
) -> str:
    default_reason = _default_reason("transfer", _now_shanghai(), source_shop, target_shop)
    suffix = f"（由{_work_order_type_label(source_order.order_type)} {source_order.order_num} 分配生成）"
    return _clean_text(f"{default_reason}{suffix}", 255)


def _create_transfer_order_from_allocation(
    db: Session,
    *,
    source_order: AqcWorkOrder,
    draft: AqcWorkOrderAllocationDraft,
    actor: AqcUser,
    source_shop: AqcShop,
    target_shop: AqcShop,
    target_items: list[tuple[AqcWorkOrderItem, int]],
) -> AqcWorkOrder:
    approver = None
    if draft.approver_id is not None:
        approver = db.execute(
            select(AqcUser).where(AqcUser.id == int(draft.approver_id), AqcUser.is_active.is_(True)).limit(1)
        ).scalars().first()
    order = AqcWorkOrder(
        order_num=_generate_order_num(db, "transfer"),
        order_type="transfer",
        status="draft",
        reason=_build_generated_transfer_reason(source_order, source_shop=source_shop, target_shop=target_shop),
        form_date=_now_shanghai(),
        source_shop_id=int(source_shop.id),
        source_shop_name=_clean_text(source_shop.name, 255),
        target_shop_id=int(target_shop.id),
        target_shop_name=_clean_text(target_shop.name, 255),
        applicant_id=int(actor.id),
        applicant_name=_display_name(actor),
        approver_id=int(approver.id) if approver is not None else None,
        approver_name=_display_name(approver),
        shared_group_id=int(draft.shared_group_id) if draft.shared_group_id is not None else None,
        shared_group_name=_clean_text(draft.shared_group_name, 80),
        shared_by_id=int(actor.id) if draft.shared_group_id is not None else None,
        shared_by_name=_display_name(actor) if draft.shared_group_id is not None else "",
        stock_applied=False,
    )
    db.add(order)
    db.flush()

    for index, (source_item, quantity) in enumerate(target_items):
        total_amount = _to_amount(source_item.unit_price or 0) * max(int(quantity or 0), 0)
        order.items.append(
            AqcWorkOrderItem(
                sort_index=index,
                goods_id=source_item.goods_id,
                source_order_num=_clean_text(source_order.order_num, 64),
                goods_name=_clean_text(source_item.goods_name, 191),
                product_code=_clean_text(source_item.product_code, 64),
                brand=_clean_text(source_item.brand, 120),
                series_name=_clean_text(source_item.series_name, 120),
                barcode=_clean_text(source_item.barcode, 64),
                unit_price=_to_amount(source_item.unit_price or 0),
                quantity=max(int(quantity or 0), 0),
                total_amount=total_amount,
                remark=_clean_text(source_item.remark, 255),
                is_new_goods=False,
            )
        )

    _append_action(
        db,
        order=order,
        actor=actor,
        action_type="saved",
        status_from="",
        status_to="draft",
        comment=f"由分配功能自动生成，来源工单 {source_order.order_num}",
    )
    db.flush()
    return order


@router.get("/meta", response_model=WorkOrderMetaResponse)
def work_order_meta(
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    _backfill_shared_drafts_for_accessible_groups(db, user)
    shops = (
        db.execute(
            select(AqcShop)
            .options(
                selectinload(AqcShop.assigned_users).load_only(
                    AqcUser.id,
                    AqcUser.username,
                    AqcUser.display_name,
                    AqcUser.is_active,
                    AqcUser.aqc_role_key,
                    AqcUser.role,
                )
            )
            .where(AqcShop.is_enabled.is_(True))
            .order_by(AqcShop.id.asc())
        )
        .scalars()
        .all()
    )
    shop_member_map = _build_shop_member_map(db, [int(item.id) for item in shops if item.id is not None])
    users = db.execute(select(AqcUser).where(AqcUser.is_active.is_(True)).order_by(AqcUser.updated_at.desc(), AqcUser.id.desc())).scalars().all()
    setting_map = _load_work_order_setting_map(db)
    approver_options = [
        WorkOrderApproverOptionOut(
            id=int(item.id),
            username=_clean_text(item.username, 50),
            displayName=_display_name(item),
            aqcRoleKey=get_aqc_role_key(item),
        )
        for item in users
        if (int(item.id) != int(user.id) or _is_admin(user)) and get_aqc_role_key(item) == "aqc_admin"
    ]
    applicant_options = [
        WorkOrderUserOptionOut(
            id=int(item.id),
            username=_clean_text(item.username, 50),
            displayName=_display_name(item),
            aqcRoleKey=get_aqc_role_key(item),
        )
        for item in users
    ]
    shop_options = [_to_shop_option(item, shop_member_map.get(int(item.id), [])) for item in shops]
    return {
        "success": True,
        "categories": [
            WorkOrderCategoryOptionOut(value=key, label=label)
            for key, label in WORK_ORDER_CATEGORIES.items()
        ],
        "types": [
            WorkOrderTypeOptionOut(
                value=key,
                label=value["label"],
                prefix=value["prefix"],
                category=_clean_text(value.get("category"), 20) or "goods",
                categoryLabel=WORK_ORDER_CATEGORIES.get(_clean_text(value.get("category"), 20) or "goods", WORK_ORDER_CATEGORIES["goods"]),
            )
            for key, value in WORK_ORDER_TYPES.items()
        ],
        "defaultApproverSettings": [
            _to_work_order_setting_out(key, setting_map.get(key))
            for key in WORK_ORDER_TYPES.keys()
        ],
        "statuses": [
            WorkOrderStatusOptionOut(value=key, label=label)
            for key, label in WORK_ORDER_STATUSES.items()
        ],
        "shopOptions": shop_options,
        "storeOptions": [item for item in shop_options if int(item.shopType) == SHOP_TYPE_STORE],
        "warehouseOptions": [item for item in shop_options if int(item.shopType) == SHOP_TYPE_WAREHOUSE],
        "otherWarehouseOptions": [item for item in shop_options if int(item.shopType) == SHOP_TYPE_OTHER_WAREHOUSE],
        "applicantOptions": applicant_options,
        "approverOptions": approver_options,
        "groups": sorted(
            _get_accessible_groups(db, user),
            key=lambda item: (0 if item.isDefault else 1, -int(item.memberCount or 0), item.name),
        ),
        "nextProductCode": "",
        "canApprove": bool(_is_admin(user)),
    }


@router.get("/dashboard", response_model=WorkOrderDashboardResponse)
def work_order_dashboard(
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    _backfill_shared_drafts_for_accessible_groups(db, user)
    group_ids = _group_ids_for_user(db, int(user.id or 0))
    shared_draft_condition = (
        AqcWorkOrder.shared_group_id.in_(group_ids)
        if group_ids
        else AqcWorkOrder.shared_group_id == -1
    )
    draft_count = int(
        db.execute(
            select(func.count(AqcWorkOrder.id)).where(
                AqcWorkOrder.status.in_(sorted(DRAFT_STATUSES)),
                or_(AqcWorkOrder.applicant_id == user.id, shared_draft_condition),
            )
        ).scalar()
        or 0
    )
    pending_count = int(
        db.execute(
            select(func.count(AqcWorkOrder.id)).where(
                AqcWorkOrder.applicant_id == user.id,
                AqcWorkOrder.status == "pending",
            )
        ).scalar()
        or 0
    )
    approval_count = int(
        db.execute(
            select(func.count(AqcWorkOrder.id)).where(
                AqcWorkOrder.approver_id == user.id,
                AqcWorkOrder.status == "pending",
            )
        ).scalar()
        or 0
    )
    recent_mine = (
        db.execute(
            select(AqcWorkOrder)
            .where(AqcWorkOrder.applicant_id == user.id)
            .order_by(AqcWorkOrder.updated_at.desc(), AqcWorkOrder.id.desc())
            .limit(6)
        )
        .scalars()
        .all()
    )
    pending_approvals = []
    if _is_admin(user):
        pending_approvals = (
            db.execute(
                select(AqcWorkOrder)
                .where(AqcWorkOrder.approver_id == user.id, AqcWorkOrder.status == "pending")
                .order_by(AqcWorkOrder.form_date.desc(), AqcWorkOrder.id.desc())
                .limit(6)
            )
            .scalars()
            .all()
        )
    recent_metric_map = _build_order_metric_map(db, [int(item.id) for item in recent_mine])
    pending_metric_map = _build_order_metric_map(db, [int(item.id) for item in pending_approvals])
    return {
        "success": True,
        "draftCount": draft_count,
        "pendingCount": pending_count,
        "approvalCount": approval_count,
        "recentMine": [
            _to_order_summary(item, metrics=recent_metric_map.get(int(item.id), (0, 0, 0.0)))
            for item in recent_mine
        ],
        "pendingApprovals": [
            _to_order_summary(item, metrics=pending_metric_map.get(int(item.id), (0, 0, 0.0)))
            for item in pending_approvals
        ],
    }


@router.get("/settings", response_model=WorkOrderSettingsResponse)
def list_work_order_settings(
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    if not _is_admin(user):
        return {"success": True, "settings": []}
    setting_map = _load_work_order_setting_map(db)
    return {
        "success": True,
        "settings": [
            _to_work_order_setting_out(order_type, setting_map.get(order_type))
            for order_type in WORK_ORDER_TYPES.keys()
        ],
    }


@router.put("/settings", response_model=MessageResponse)
def save_work_order_settings(
    payload: WorkOrderSettingsSaveRequest,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    if not _is_admin(user):
        return {"success": False, "message": "当前账号没有管理工单设置权限"}
    normalized_items = {
        _clean_text(item.orderType, 20): item
        for item in (payload.settings or [])
        if _clean_text(item.orderType, 20) in WORK_ORDER_TYPES
    }
    existing_map = _load_work_order_setting_map(db)
    for order_type in WORK_ORDER_TYPES.keys():
        item = normalized_items.get(order_type)
        approver = _validate_setting_approver(db, int(item.approverId) if item and item.approverId is not None else None)
        setting = existing_map.get(order_type)
        if setting is None:
            setting = AqcWorkOrderSetting(order_type=order_type)
            db.add(setting)
            existing_map[order_type] = setting
        setting.approver_id = int(approver.id) if approver is not None else None
        setting.approver_name = _display_name(approver)
        setting.updated_by = int(user.id) if user.id is not None else None
        setting.updated_by_name = _display_name(user)
    db.commit()
    return {"success": True, "message": "工单设置已保存"}


@router.get("/schedules", response_model=WorkOrderScheduleListResponse)
def list_work_order_schedules(
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcWorkOrderSchedule).order_by(AqcWorkOrderSchedule.updated_at.desc(), AqcWorkOrderSchedule.id.desc())
    if not _is_admin(user):
        stmt = stmt.where(
            or_(
                AqcWorkOrderSchedule.applicant_id == int(user.id),
                AqcWorkOrderSchedule.created_by == int(user.id),
            )
        )
    rows = db.execute(stmt).scalars().all()
    return {"success": True, "schedules": [_to_schedule_out(item) for item in rows]}


@router.post("/schedules", response_model=MessageResponse)
def save_work_order_schedule(
    payload: WorkOrderScheduleSaveRequest,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    if payload.orderType != "sale":
        return {"success": False, "message": "当前仅支持销售单定时开单"}
    shop_map = _get_shop_map(db)
    selected_shops = [shop_map.get(int(shop_id)) for shop_id in payload.shopIds]
    selected_shops = [shop for shop in selected_shops if shop is not None]
    selected_shops = [shop for shop in selected_shops if int(shop.shop_type or 0) == SHOP_TYPE_STORE]
    if not selected_shops:
        return {"success": False, "message": "请至少选择一个有效销售店铺"}

    applicant = db.execute(
        select(AqcUser).where(AqcUser.id == int(payload.applicantId), AqcUser.is_active.is_(True)).limit(1)
    ).scalars().first()
    if applicant is None:
        return {"success": False, "message": "申请人不存在或已停用"}
    approver = _validate_approver(db, applicant, payload.approverId)
    if approver is None:
        return {"success": False, "message": "请选择负责人"}

    shared_group = None
    if payload.groupId is not None:
        shared_group = db.execute(
            select(AqcGroup).where(AqcGroup.id == int(payload.groupId), AqcGroup.is_active.is_(True)).limit(1)
        ).scalars().first()
        if shared_group is None:
            return {"success": False, "message": "共享群组不存在或已停用"}
        if not _is_group_member(db, int(shared_group.id), int(user.id or 0)):
            return {"success": False, "message": "当前账号不在所选群组中"}
    else:
        shared_group = _default_group_for_user(db, int(user.id or 0))

    schedule = AqcWorkOrderSchedule(
        order_type="sale",
        period_key=_clean_text(payload.periodKey, 20) or "day",
        shop_ids_json=json.dumps([int(shop.id) for shop in selected_shops], ensure_ascii=False),
        shop_names_json=json.dumps([_clean_text(shop.name, 255) for shop in selected_shops], ensure_ascii=False),
        applicant_id=int(applicant.id),
        applicant_name=_display_name(applicant),
        approver_id=int(approver.id),
        approver_name=_display_name(approver),
        shared_group_id=int(shared_group.id) if shared_group is not None else None,
        shared_group_name=_clean_text(shared_group.name if shared_group else "", 80),
        enabled=bool(payload.enabled),
        created_by=int(user.id),
    )
    db.add(schedule)
    db.commit()
    return {"success": True, "message": "定时开单已创建"}


@router.delete("/schedules/{schedule_id}", response_model=MessageResponse)
def delete_work_order_schedule(
    schedule_id: int,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    schedule = db.execute(
        select(AqcWorkOrderSchedule).where(AqcWorkOrderSchedule.id == int(schedule_id)).limit(1)
    ).scalars().first()
    if schedule is None:
        return {"success": False, "message": "定时开单不存在"}
    if not _is_admin(user) and int(schedule.created_by or 0) != int(user.id or 0):
        return {"success": False, "message": "没有权限删除该定时开单"}
    db.delete(schedule)
    db.commit()
    return {"success": True, "message": "定时开单已删除"}


@router.get("", response_model=WorkOrderListResponse)
def list_work_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="mine"),
    order_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    date_start: str | None = Query(default=None),
    date_end: str | None = Query(default=None),
    applicant_id: int | None = Query(default=None, ge=1),
    approver_id: int | None = Query(default=None, ge=1),
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    _backfill_shared_drafts_for_accessible_groups(db, user)
    stmt = select(AqcWorkOrder)
    count_stmt = select(func.count(AqcWorkOrder.id))

    scope_condition = _query_scope_filter(user, scope)
    if scope_condition is not None:
        if isinstance(scope_condition, tuple):
            stmt = stmt.where(*scope_condition)
            count_stmt = count_stmt.where(*scope_condition)
        else:
            stmt = stmt.where(scope_condition)
            count_stmt = count_stmt.where(scope_condition)
    extra_condition = _scope_extra_conditions(db, user, scope)
    if extra_condition is not None:
        stmt = stmt.where(extra_condition)
        count_stmt = count_stmt.where(extra_condition)

    clean_type = _clean_text(order_type, 20)
    if clean_type:
        stmt = stmt.where(AqcWorkOrder.order_type == clean_type)
        count_stmt = count_stmt.where(AqcWorkOrder.order_type == clean_type)

    clean_status = _clean_text(status, 20)
    if clean_status:
        stmt = stmt.where(AqcWorkOrder.status == clean_status)
        count_stmt = count_stmt.where(AqcWorkOrder.status == clean_status)

    clean_keyword = _clean_text(keyword, 120)
    if clean_keyword:
        like = f"%{clean_keyword}%"
        keyword_condition = or_(
            AqcWorkOrder.order_num.like(like),
            AqcWorkOrder.reason.like(like),
            AqcWorkOrder.source_shop_name.like(like),
            AqcWorkOrder.target_shop_name.like(like),
            AqcWorkOrder.supplier_name.like(like),
            AqcWorkOrder.partner_name.like(like),
            AqcWorkOrder.applicant_name.like(like),
            AqcWorkOrder.approver_name.like(like),
        )
        stmt = stmt.where(keyword_condition)
        count_stmt = count_stmt.where(keyword_condition)

    parsed_date_start = _parse_filter_date(date_start)
    if parsed_date_start is not None:
        stmt = stmt.where(AqcWorkOrder.form_date >= parsed_date_start)
        count_stmt = count_stmt.where(AqcWorkOrder.form_date >= parsed_date_start)

    parsed_date_end = _parse_filter_date(date_end, end=True)
    if parsed_date_end is not None:
        stmt = stmt.where(AqcWorkOrder.form_date < parsed_date_end)
        count_stmt = count_stmt.where(AqcWorkOrder.form_date < parsed_date_end)

    if applicant_id is not None:
        stmt = stmt.where(AqcWorkOrder.applicant_id == int(applicant_id))
        count_stmt = count_stmt.where(AqcWorkOrder.applicant_id == int(applicant_id))

    if approver_id is not None:
        stmt = stmt.where(AqcWorkOrder.approver_id == int(approver_id))
        count_stmt = count_stmt.where(AqcWorkOrder.approver_id == int(approver_id))

    total = int(db.execute(count_stmt).scalar() or 0)
    rows = (
        db.execute(
            stmt.order_by(AqcWorkOrder.updated_at.desc(), AqcWorkOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    metric_map = _build_order_metric_map(db, [int(item.id) for item in rows])
    return {
        "success": True,
        "total": total,
        "orders": [
            _to_order_summary(item, metrics=metric_map.get(int(item.id), (0, 0, 0.0)))
            for item in rows
        ],
    }


@router.get("/logs", response_model=WorkOrderLogListResponse)
def list_work_order_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="mine"),
    order_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    date_start: str | None = Query(default=None),
    date_end: str | None = Query(default=None),
    applicant_id: int | None = Query(default=None, ge=1),
    approver_id: int | None = Query(default=None, ge=1),
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    _backfill_shared_drafts_for_accessible_groups(db, user)
    stmt = select(AqcWorkOrderAction, AqcWorkOrder).join(AqcWorkOrder, AqcWorkOrder.id == AqcWorkOrderAction.work_order_id)
    count_stmt = select(func.count(AqcWorkOrderAction.id)).join(AqcWorkOrder, AqcWorkOrder.id == AqcWorkOrderAction.work_order_id)

    scope_condition = _query_scope_filter(user, scope)
    if scope_condition is not None:
        if isinstance(scope_condition, tuple):
            stmt = stmt.where(*scope_condition)
            count_stmt = count_stmt.where(*scope_condition)
        else:
            stmt = stmt.where(scope_condition)
            count_stmt = count_stmt.where(scope_condition)
    extra_condition = _scope_extra_conditions(db, user, scope)
    if extra_condition is not None:
        stmt = stmt.where(extra_condition)
        count_stmt = count_stmt.where(extra_condition)

    clean_type = _clean_text(order_type, 20)
    if clean_type:
        stmt = stmt.where(AqcWorkOrder.order_type == clean_type)
        count_stmt = count_stmt.where(AqcWorkOrder.order_type == clean_type)

    clean_keyword = _clean_text(keyword, 120)
    if clean_keyword:
        like = f"%{clean_keyword}%"
        keyword_condition = or_(
            AqcWorkOrder.order_num.like(like),
            AqcWorkOrder.reason.like(like),
            AqcWorkOrderAction.actor_name.like(like),
            AqcWorkOrderAction.comment.like(like),
            AqcWorkOrder.applicant_name.like(like),
            AqcWorkOrder.approver_name.like(like),
        )
        stmt = stmt.where(keyword_condition)
        count_stmt = count_stmt.where(keyword_condition)

    parsed_date_start = _parse_filter_date(date_start)
    if parsed_date_start is not None:
        stmt = stmt.where(AqcWorkOrderAction.created_at >= parsed_date_start)
        count_stmt = count_stmt.where(AqcWorkOrderAction.created_at >= parsed_date_start)

    parsed_date_end = _parse_filter_date(date_end, end=True)
    if parsed_date_end is not None:
        stmt = stmt.where(AqcWorkOrderAction.created_at < parsed_date_end)
        count_stmt = count_stmt.where(AqcWorkOrderAction.created_at < parsed_date_end)

    if applicant_id is not None:
        stmt = stmt.where(AqcWorkOrder.applicant_id == int(applicant_id))
        count_stmt = count_stmt.where(AqcWorkOrder.applicant_id == int(applicant_id))

    if approver_id is not None:
        stmt = stmt.where(AqcWorkOrder.approver_id == int(approver_id))
        count_stmt = count_stmt.where(AqcWorkOrder.approver_id == int(approver_id))

    total = int(db.execute(count_stmt).scalar() or 0)
    rows = db.execute(
        stmt.order_by(AqcWorkOrderAction.created_at.desc(), AqcWorkOrderAction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "success": True,
        "total": total,
        "logs": [_to_work_order_log_out(action, order) for action, order in rows],
    }


@router.get("/{order_id}", response_model=WorkOrderDetailResponse)
def get_work_order_detail(
    order_id: int,
    user: AqcUser = Depends(require_permissions("workorders.read")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "order": None}
    if not _can_view_order(db, user, order):
        return {"success": False, "message": "没有权限查看该工单", "order": None}
    return {"success": True, "order": _to_order_detail(db, order, user)}


@router.get("/{order_id}/allocation-draft", response_model=WorkOrderAllocationDraftResponse)
def get_work_order_allocation_draft(
    order_id: int,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "order": None, "draft": None}
    if not _can_allocate_order(db, user, order):
        return {"success": False, "message": "当前工单暂不支持分配", "order": None, "draft": None}
    try:
        draft = _build_allocation_draft_out(db, order=order, draft=order.allocation_draft)
    except Exception as exc:
        return {"success": False, "message": str(exc), "order": None, "draft": None}
    target_options = _available_allocation_target_options(db, source_shop_id=draft.sourceShopId)
    approver_options = [
        WorkOrderApproverOptionOut(
            id=int(item.id),
            username=_clean_text(item.username, 50),
            displayName=_display_name(item),
            aqcRoleKey=get_aqc_role_key(item),
        )
        for item in db.execute(select(AqcUser).where(AqcUser.is_active.is_(True)).order_by(AqcUser.updated_at.desc(), AqcUser.id.desc())).scalars().all()
        if (int(item.id) != int(user.id) or _is_admin(user)) and get_aqc_role_key(item) == "aqc_admin"
    ]
    return {
        "success": True,
        "order": _to_order_detail(db, order, user),
        "draft": draft,
        "targetOptions": target_options,
        "approverOptions": approver_options,
    }


@router.put("/{order_id}/allocation-draft", response_model=WorkOrderAllocationDraftResponse)
def save_work_order_allocation_draft(
    order_id: int,
    payload: WorkOrderAllocationDraftSaveRequest,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "order": None, "draft": None}
    if not _can_allocate_order(db, user, order):
        return {"success": False, "message": "当前工单暂不支持分配", "order": None, "draft": None}
    try:
        draft_model = _create_or_update_allocation_draft(db, order=order, actor=user, payload=payload)
        db.commit()
        refreshed = _load_order_for_detail(db, order_id)
        if refreshed is None:
            return {"success": False, "message": "工单不存在", "order": None, "draft": None}
        draft = _build_allocation_draft_out(db, order=refreshed, draft=draft_model)
        return {
            "success": True,
            "message": "分配草稿已保存",
            "order": _to_order_detail(db, refreshed, user),
            "draft": draft,
            "targetOptions": _available_allocation_target_options(db, source_shop_id=draft.sourceShopId),
            "approverOptions": [
                WorkOrderApproverOptionOut(
                    id=int(item.id),
                    username=_clean_text(item.username, 50),
                    displayName=_display_name(item),
                    aqcRoleKey=get_aqc_role_key(item),
                )
                for item in db.execute(select(AqcUser).where(AqcUser.is_active.is_(True)).order_by(AqcUser.updated_at.desc(), AqcUser.id.desc())).scalars().all()
                if (int(item.id) != int(user.id) or _is_admin(user)) and get_aqc_role_key(item) == "aqc_admin"
            ],
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "order": None, "draft": None}


@router.post("/{order_id}/allocation-draft/confirm", response_model=WorkOrderAllocationConfirmResponse)
def confirm_work_order_allocation_draft(
    order_id: int,
    payload: WorkOrderAllocationDraftSaveRequest,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "createdCount": 0, "orderIds": []}
    if not _can_allocate_order(db, user, order):
        return {"success": False, "message": "当前工单暂不支持分配", "createdCount": 0, "orderIds": []}
    try:
        draft = _create_or_update_allocation_draft(db, order=order, actor=user, payload=payload)
        source_shop_id = _allocation_source_shop_id(order)
        source_shop = db.execute(select(AqcShop).where(AqcShop.id == int(source_shop_id or 0)).limit(1)).scalars().first()
        if source_shop is None:
            raise ValueError("分配发货仓库不存在")
        shop_map = _get_shop_map(db)
        ordered_items = {
            int(item.id): item
            for item in sorted(order.items or [], key=lambda row: (int(row.sort_index or 0), int(row.id or 0)))
            if item.id is not None
        }
        allocation_map = _load_allocation_draft_rows(draft.allocations_json)
        grouped_items: dict[int, list[tuple[AqcWorkOrderItem, int]]] = {}
        for item_id, target_map in allocation_map.items():
            source_item = ordered_items.get(int(item_id))
            if source_item is None:
                continue
            for target_shop_id, quantity in target_map.items():
                if int(quantity or 0) <= 0:
                    continue
                grouped_items.setdefault(int(target_shop_id), []).append((source_item, int(quantity)))
        if not grouped_items:
            raise ValueError("当前没有可生成的分配明细，请先填写分配数量")

        created_orders = []
        for target_shop_id in [int(shop_id) for shop_id in _loads(draft.target_shop_ids_json) if int(shop_id) > 0]:
            target_items = grouped_items.get(int(target_shop_id), [])
            if not target_items:
                continue
            target_shop = shop_map.get(int(target_shop_id))
            if target_shop is None:
                continue
            created_orders.append(
                _create_transfer_order_from_allocation(
                    db,
                    source_order=order,
                    draft=draft,
                    actor=user,
                    source_shop=source_shop,
                    target_shop=target_shop,
                    target_items=target_items,
                )
            )
        if not created_orders:
            raise ValueError("当前没有有效的分配目标，无法生成调拨单")

        db.delete(draft)
        db.commit()
        return {
            "success": True,
            "message": f"已生成 {len(created_orders)} 张商品调拨单草稿",
            "createdCount": len(created_orders),
            "orderIds": [int(item.id) for item in created_orders if item.id is not None],
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "createdCount": 0, "orderIds": []}


def _save_work_order(
    db: Session,
    *,
    user: AqcUser,
    payload: WorkOrderSaveRequest,
    order: AqcWorkOrder | None = None,
) -> tuple[bool, str, AqcWorkOrder]:
    is_new = order is None
    target_status = _clean_text(payload.status, 20) or "draft"
    strict = target_status == "pending"
    sale_affects_inventory = bool(payload.saleAffectsInventory) and payload.orderType == "sale"
    group_id = int(payload.groupId or 0) if payload.groupId is not None else None
    shared_group = None
    if group_id:
        shared_group = db.execute(
            select(AqcGroup).where(AqcGroup.id == group_id, AqcGroup.is_active.is_(True)).limit(1)
        ).scalars().first()
        if shared_group is None:
            raise ValueError("所选群组不存在或已停用")
        if not _is_group_member(db, int(shared_group.id), int(user.id or 0)):
            raise ValueError("当前账号不在所选群组中，不能共享草稿")
    else:
        shared_group = _default_group_for_user(db, int(user.id or 0))

    shop_map = _get_shop_map(db)
    source_shop = shop_map.get(int(payload.sourceShopId)) if payload.sourceShopId is not None else None
    target_shop = shop_map.get(int(payload.targetShopId)) if payload.targetShopId is not None else None
    if strict:
        resolved_approver_id = payload.approverId
        if resolved_approver_id is None:
            default_approver = _resolve_work_order_default_approver(db, payload.orderType)
            resolved_approver_id = int(default_approver.id) if default_approver is not None else None
        approver = _validate_approver(db, user, resolved_approver_id)
        _validate_shop_for_type(payload.orderType, source_shop, target_shop)
    else:
        approver = None
        resolved_approver_id = payload.approverId
        if resolved_approver_id is None:
            default_approver = _resolve_work_order_default_approver(db, payload.orderType)
            resolved_approver_id = int(default_approver.id) if default_approver is not None else None
        if resolved_approver_id is not None:
            try:
                approver = _validate_approver(db, user, resolved_approver_id)
            except Exception:
                approver = None

    form_date = _parse_form_date(payload.formDate)
    reason = _clean_text(payload.reason, 255) or _default_reason(payload.orderType, form_date, source_shop, target_shop)

    if strict and payload.orderType == "purchase" and not _clean_text(payload.supplierName, 255):
        raise ValueError("请填写供货单位")
    if strict and payload.orderType == "return" and not _clean_text(payload.partnerName, 255):
        raise ValueError("请填写收货单位")
    if strict and payload.orderType in SALES_ORDER_TYPES and source_shop is None:
        raise ValueError("请选择销售店铺")

    prepared_items = _prepare_items_for_save(
        db,
        payload.orderType,
        payload.items,
        strict=strict,
        sale_affects_inventory=sale_affects_inventory,
    )

    if order is None:
        order = AqcWorkOrder(
            order_num=_generate_order_num(db, payload.orderType),
            applicant_id=user.id,
            applicant_name=_display_name(user),
        )
        db.add(order)
        db.flush()
        previous_status = ""
    else:
        if not _can_edit_order(db, user, order):
            raise ValueError("当前工单状态不可编辑")
        previous_status = _clean_text(order.status, 20)
    previous_group_id = int(order.shared_group_id) if order.shared_group_id is not None else None

    order.order_type = _clean_text(payload.orderType, 20)
    order.status = target_status
    order.reason = reason
    order.form_date = form_date
    order.sale_affects_inventory = sale_affects_inventory
    order.source_shop_id = source_shop.id if source_shop is not None else None
    order.source_shop_name = _clean_text(source_shop.name if source_shop else "", 255)
    order.target_shop_id = target_shop.id if target_shop is not None else None
    order.target_shop_name = _clean_text(target_shop.name if target_shop else "", 255)
    order.supplier_name = _clean_text(payload.supplierName, 255)
    order.partner_name = _clean_text(payload.partnerName, 255)
    order.approver_id = approver.id if approver is not None else None
    order.approver_name = _display_name(approver)
    if is_new:
        order.applicant_name = _display_name(user)
    next_group_id = int(shared_group.id) if shared_group is not None else None
    order.shared_group_id = next_group_id
    order.shared_group_name = _clean_text(shared_group.name if shared_group else "", 80)
    if next_group_id is None:
        order.shared_by_id = None
        order.shared_by_name = ""
    elif is_new or next_group_id != previous_group_id:
        order.shared_by_id = int(user.id)
        order.shared_by_name = _display_name(user)
    if target_status == "pending":
        order.submitted_at = _now_shanghai()
        if previous_status != "rejected":
            order.approval_comment = ""
        order.approved_at = None
        order.stock_applied = False
    _sync_order_items(order, prepared_items)
    db.flush()

    action_type = "submitted" if target_status == "pending" else "saved"
    _append_action(
        db,
        order=order,
        actor=user,
        action_type=action_type,
        status_from=previous_status,
        status_to=target_status,
        comment="",
    )
    db.commit()
    refreshed = _load_order_for_detail(db, int(order.id))
    if refreshed is None:
        raise ValueError("工单保存失败，请重试")
    message = "工单已提交审批" if target_status == "pending" else "工单草稿已保存"
    return is_new, message, refreshed


@router.post("", response_model=WorkOrderDetailResponse)
def create_work_order(
    payload: WorkOrderSaveRequest,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    try:
        _created, message, order = _save_work_order(db, user=user, payload=payload, order=None)
        return {"success": True, "message": message, "order": _to_order_detail(db, order, user)}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "order": None}


@router.put("/{order_id}", response_model=WorkOrderDetailResponse)
def update_work_order(
    order_id: int,
    payload: WorkOrderSaveRequest,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "order": None}
    if not _can_edit_order(db, user, order):
        return {"success": False, "message": "当前工单状态不可编辑", "order": None}
    try:
        _created, message, refreshed = _save_work_order(db, user=user, payload=payload, order=order)
        return {"success": True, "message": message, "order": _to_order_detail(db, refreshed, user)}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "order": None}


@router.post("/{order_id}/withdraw", response_model=WorkOrderDetailResponse)
def withdraw_work_order(
    order_id: int,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "order": None}
    if not _can_withdraw_order(user, order):
        return {"success": False, "message": "当前工单不能转回草稿箱", "order": None}

    previous_status = _clean_text(order.status, 20)
    try:
        order.status = "draft"
        order.submitted_at = None
        order.approved_at = None
        order.approval_comment = ""
        order.stock_applied = False
        _append_action(
            db,
            order=order,
            actor=user,
            action_type="withdrawn",
            status_from=previous_status,
            status_to="draft",
            comment="",
        )
        db.commit()
        refreshed = _load_order_for_detail(db, order_id)
        if refreshed is None:
            return {"success": False, "message": "工单不存在", "order": None}
        return {
            "success": True,
            "message": "工单已转回草稿箱",
            "order": _to_order_detail(db, refreshed, user),
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "order": None}


@router.delete("/{order_id}", response_model=MessageResponse)
def delete_work_order(
    order_id: int,
    user: AqcUser = Depends(require_permissions("workorders.write")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在"}
    if not _can_delete_order(db, user, order):
        return {"success": False, "message": "当前工单不能删除"}

    was_pending = order.status == "pending"
    try:
        db.delete(order)
        db.commit()
        return {
            "success": True,
            "message": "待审批工单已删除并撤销审批" if was_pending else "工单已删除",
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc)}


@router.post("/{order_id}/review", response_model=WorkOrderDetailResponse)
def review_work_order(
    order_id: int,
    payload: WorkOrderReviewRequest,
    user: AqcUser = Depends(require_permissions("workorders.approve")),
    db: Session = Depends(get_db),
):
    order = _load_order_for_detail(db, order_id)
    if order is None:
        return {"success": False, "message": "工单不存在", "order": None}
    if not _can_review_order(user, order):
        return {"success": False, "message": "当前账号不能审批该工单", "order": None}

    previous_status = _clean_text(order.status, 20)
    comment = _clean_text(payload.comment, 1000)
    try:
        if payload.approved:
            inventory_applied = False
            if order.order_type == "sale" and bool(order.sale_affects_inventory):
                _apply_sale_order_with_inventory(db, order, actor=user)
                inventory_applied = True
            elif order.order_type == "sale_return":
                _apply_sale_return_order(db, order, actor=user)
                inventory_applied = True
            elif order.order_type == "sale_exchange":
                _apply_sale_exchange_order(db, order, actor=user)
                inventory_applied = True
            elif _order_type_affects_inventory(order.order_type):
                _apply_work_order_inventory(db, order, actor=user)
                inventory_applied = True
            order.status = "approved"
            order.stock_applied = inventory_applied
            order.approved_at = _now_shanghai()
            order.approval_comment = comment
            _append_action(
                db,
                order=order,
                actor=user,
                action_type="approved",
                status_from=previous_status,
                status_to="approved",
                comment=comment,
            )
        else:
            order.status = "rejected"
            order.stock_applied = False
            order.approved_at = None
            order.approval_comment = comment
            _append_action(
                db,
                order=order,
                actor=user,
                action_type="rejected",
                status_from=previous_status,
                status_to="rejected",
                comment=comment,
            )
        db.commit()
        refreshed = _load_order_for_detail(db, order_id)
        if refreshed is None:
            return {"success": False, "message": "工单不存在", "order": None}
        return {
            "success": True,
            "message": "工单已审批" if payload.approved else "工单已驳回至草稿箱",
            "order": _to_order_detail(db, refreshed, user),
        }
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "order": None}

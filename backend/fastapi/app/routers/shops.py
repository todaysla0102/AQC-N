from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import assign_user_shops, get_aqc_role_key, require_permissions, scoped_shop_conditions, to_iso, user_shop_ids
from ..inventory import aggregate_shop_goods_quantity, inventory_log_scope_current_total, inventory_log_total_after_map, list_inventory_logs, recalculate_goods_stock
from ..models import AqcGoodsItem, AqcGoodsInventory, AqcInventoryLog, AqcShop, AqcUser
from ..schemas import (
    InventoryLogListResponse,
    InventoryLogOut,
    MessageResponse,
    ShopCreateRequest,
    ShopListResponse,
    ShopOptionListResponse,
    ShopOptionOut,
    ShopOut,
    ShopUpdateRequest,
)


router = APIRouter(prefix="/shops", tags=["shops"])
SHOP_TYPE_STORE = 0
SHOP_TYPE_WAREHOUSE = 1
SHOP_TYPE_OTHER_WAREHOUSE = 2
SHOP_TYPE_REPAIR = 3
REPORT_DISABLED_SHOP_NAMES = {"aqc flow"}


def _is_warehouse_shop(item: AqcShop) -> bool:
    # Legacy imported rows may carry historical shop_type values such as 1/2,
    # but they are still real stores. Only manual rows without legacy_id and
    # explicit warehouse type should be treated as warehouses.
    return item.legacy_id is None and int(item.shop_type or 0) == SHOP_TYPE_WAREHOUSE


def _is_other_warehouse_shop(item: AqcShop) -> bool:
    return item.legacy_id is None and int(item.shop_type or 0) == SHOP_TYPE_OTHER_WAREHOUSE


def _is_repair_shop(item: AqcShop) -> bool:
    return item.legacy_id is None and int(item.shop_type or 0) == SHOP_TYPE_REPAIR


def _resolved_shop_type(item: AqcShop) -> int:
    if _is_repair_shop(item):
        return SHOP_TYPE_REPAIR
    if _is_other_warehouse_shop(item):
        return SHOP_TYPE_OTHER_WAREHOUSE
    return SHOP_TYPE_WAREHOUSE if _is_warehouse_shop(item) else SHOP_TYPE_STORE


def _warehouse_condition():
    return and_(AqcShop.legacy_id.is_(None), AqcShop.shop_type == SHOP_TYPE_WAREHOUSE)


def _other_warehouse_condition():
    return and_(AqcShop.legacy_id.is_(None), AqcShop.shop_type == SHOP_TYPE_OTHER_WAREHOUSE)


def _repair_condition():
    return and_(AqcShop.legacy_id.is_(None), AqcShop.shop_type == SHOP_TYPE_REPAIR)


def _is_repair_engineer_eligible(user: AqcUser) -> bool:
    role_key = get_aqc_role_key(user)
    return bool(user.is_active) and role_key in {"aqc_engineer", "aqc_admin"}


def _is_store_member_eligible(user: AqcUser) -> bool:
    role_key = get_aqc_role_key(user)
    return bool(user.is_active) and role_key in {"aqc_admin", "aqc_manager", "aqc_sales"}


def _can_enable_report_for_shop(*, shop_type: int, name: str | None) -> bool:
    clean_name = str(name or "").strip().lower()
    return int(shop_type) == SHOP_TYPE_STORE and clean_name not in REPORT_DISABLED_SHOP_NAMES


def _store_condition():
    return or_(
        AqcShop.legacy_id.is_not(None),
        AqcShop.shop_type.is_(None),
        AqcShop.shop_type == SHOP_TYPE_STORE,
    )


def _store_or_repair_condition():
    return or_(_store_condition(), _repair_condition())


def _sorted_assigned_users(item: AqcShop) -> list[AqcUser]:
    manager_user_id = item.manager_user_id
    return sorted(
        [user for user in item.assigned_users if user and user.is_active],
        key=lambda user: (
            0 if user.id == manager_user_id else 1,
            0 if get_aqc_role_key(user) == "aqc_manager" else 1,
            user.display_name or user.username or "",
        ),
    )


def _sort_shop_member_rows(users: list[AqcUser], *, manager_user_id: int | None = None) -> list[AqcUser]:
    return sorted(
        [user for user in users if user and user.is_active],
        key=lambda user: (
            0 if user.id == manager_user_id else 1,
            0 if get_aqc_role_key(user) == "aqc_manager" else 1,
            0 if get_aqc_role_key(user) == "aqc_admin" else 1,
            (user.display_name or user.username or "").strip(),
            int(user.id or 0),
        ),
    )


def _build_shop_member_map(db: Session, shop_ids: list[int]) -> dict[int, list[AqcUser]]:
    normalized_shop_ids = sorted({int(shop_id) for shop_id in shop_ids if int(shop_id) > 0})
    result = {shop_id: [] for shop_id in normalized_shop_ids}
    if not normalized_shop_ids:
        return result

    users = db.execute(
        select(AqcUser).where(AqcUser.is_active.is_(True))
    ).scalars().all()
    for user in users:
        for shop_id in user_shop_ids(user):
            if shop_id in result:
                result[shop_id].append(user)
    return result


def _to_shop_out(item: AqcShop, *, goods_quantity: int = 0, member_users: list[AqcUser] | None = None) -> ShopOut:
    if _is_other_warehouse_shop(item):
        return ShopOut(
            id=item.id,
            legacyId=item.legacy_id,
            name=item.name,
            image=item.image or "",
            phone=item.phone,
            address=item.address or "",
            province=item.province,
            city=item.city,
            district=item.district,
            latitude=item.latitude,
            longitude=item.longitude,
            businessHours=item.business_hours,
            brandIds=item.brand_ids or "",
            shopType=_resolved_shop_type(item),
            channel=item.channel,
            managerUserId=None,
            managerName=None,
            scheduleEnabled=False,
            targetEnabled=False,
            reportEnabled=False,
            scheduleMemberCount=0,
            salespersonIds=[],
            division=item.division,
            shareCode=item.share_code,
            createdBy=item.created_by,
            createdByName=item.creator.display_name if item.creator else None,
            salespeople="",
            goodsQuantity=0,
            createdAt=to_iso(item.created_at) or "",
            updatedAt=to_iso(item.updated_at) or "",
        )

    if _is_repair_shop(item):
        assigned_users = _sort_shop_member_rows(
            [user for user in (member_users if member_users is not None else _sorted_assigned_users(item)) if _is_repair_engineer_eligible(user)],
            manager_user_id=item.manager_user_id,
        )
        engineer_names = [
            name
            for name in [(user.display_name or user.username or "").strip() for user in assigned_users]
            if name
        ]
        deduped_engineers: list[str] = []
        for name in engineer_names:
            if name not in deduped_engineers:
                deduped_engineers.append(name)
        return ShopOut(
            id=item.id,
            legacyId=item.legacy_id,
            name=item.name,
            image=item.image or "",
            phone=item.phone,
            address=item.address or "",
            province=item.province,
            city=item.city,
            district=item.district,
            latitude=item.latitude,
            longitude=item.longitude,
            businessHours=item.business_hours,
            brandIds=item.brand_ids or "",
            shopType=_resolved_shop_type(item),
            channel=item.channel,
            managerUserId=None,
            managerName=None,
            scheduleEnabled=False,
            targetEnabled=False,
            reportEnabled=False,
            scheduleMemberCount=0,
            salespersonIds=[user.id for user in assigned_users],
            division=item.division,
            shareCode=item.share_code,
            createdBy=item.created_by,
            createdByName=item.creator.display_name if item.creator else None,
            salespeople="、".join(deduped_engineers),
            goodsQuantity=0,
            createdAt=to_iso(item.created_at) or "",
            updatedAt=to_iso(item.updated_at) or "",
        )

    if _is_warehouse_shop(item):
        manager_name = None
        manager_user = item.manager_user
        if manager_user and manager_user.is_active:
            manager_name = (manager_user.display_name or manager_user.username or "").strip() or None
        if not manager_name:
            manager_name = (item.manager_name or "").strip() or None

        return ShopOut(
            id=item.id,
            legacyId=item.legacy_id,
            name=item.name,
            image=item.image or "",
            phone=item.phone,
            address=item.address or "",
            province=item.province,
            city=item.city,
            district=item.district,
            latitude=item.latitude,
            longitude=item.longitude,
            businessHours=item.business_hours,
            brandIds=item.brand_ids or "",
            shopType=_resolved_shop_type(item),
            channel=item.channel,
            managerUserId=item.manager_user_id,
            managerName=manager_name,
            scheduleEnabled=False,
            targetEnabled=False,
            reportEnabled=False,
            scheduleMemberCount=0,
            salespersonIds=[],
            division=item.division,
            shareCode=item.share_code,
            createdBy=item.created_by,
            createdByName=item.creator.display_name if item.creator else None,
            salespeople="",
            goodsQuantity=int(goods_quantity or 0),
            createdAt=to_iso(item.created_at) or "",
            updatedAt=to_iso(item.updated_at) or "",
        )

    assigned_users = _sort_shop_member_rows(
        [user for user in (member_users if member_users is not None else _sorted_assigned_users(item)) if _is_store_member_eligible(user)],
        manager_user_id=item.manager_user_id,
    )
    salesperson_names: list[str] = []
    for user in assigned_users:
        name = (user.display_name or user.username or "").strip()
        if name and name not in salesperson_names:
            salesperson_names.append(name)

    manager_name = None
    manager_user = item.manager_user
    if manager_user and manager_user.is_active:
        manager_name = (manager_user.display_name or manager_user.username or "").strip() or None
    if not manager_name:
        for user in assigned_users:
            if get_aqc_role_key(user) == "aqc_manager":
                manager_name = (user.display_name or user.username or "").strip() or None
                if manager_name:
                    break

    raw_manager_name = (item.manager_name or "").strip()
    if not manager_name and raw_manager_name and not raw_manager_name.isdigit():
        manager_name = raw_manager_name
        if raw_manager_name not in salesperson_names:
            salesperson_names.insert(0, raw_manager_name)

    return ShopOut(
        id=item.id,
        legacyId=item.legacy_id,
        name=item.name,
        image=item.image or "",
        phone=item.phone,
        address=item.address or "",
        province=item.province,
        city=item.city,
        district=item.district,
        latitude=item.latitude,
        longitude=item.longitude,
        businessHours=item.business_hours,
        brandIds=item.brand_ids or "",
        shopType=_resolved_shop_type(item),
        channel=item.channel,
        managerUserId=item.manager_user_id,
        managerName=manager_name,
        scheduleEnabled=bool(getattr(item, "schedule_enabled", False)),
        targetEnabled=bool(getattr(item, "target_enabled", False)),
        reportEnabled=bool(getattr(item, "report_enabled", False)),
        scheduleMemberCount=len(assigned_users),
        salespersonIds=[user.id for user in assigned_users],
        division=item.division,
        shareCode=item.share_code,
        createdBy=item.created_by,
        createdByName=item.creator.display_name if item.creator else None,
        salespeople="、".join(salesperson_names),
        goodsQuantity=int(goods_quantity or 0),
        createdAt=to_iso(item.created_at) or "",
        updatedAt=to_iso(item.updated_at) or "",
    )


def _to_inventory_log_out(item: AqcInventoryLog, *, total_quantity_after: int = 0) -> InventoryLogOut:
    return InventoryLogOut(
        id=int(item.id),
        goodsId=item.goods_item_id,
        goodsName=item.goods_name or "",
        goodsModel=item.goods_model or "",
        shopId=item.shop_id,
        shopName=item.shop_name or "",
        changeContent=item.change_content or "",
        quantityBefore=int(item.quantity_before or 0),
        quantityAfter=int(item.quantity_after or 0),
        totalQuantityAfter=int(total_quantity_after or 0),
        operatorId=item.operator_id,
        operatorName=item.operator_name or "",
        relatedType=item.related_type or "",
        relatedId=item.related_id,
        createdAt=to_iso(item.created_at) or "",
    )


@router.get("/options", response_model=ShopOptionListResponse)
def list_shop_options(
    q: str | None = None,
    limit: int = Query(default=120, ge=1, le=300),
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcShop.id, AqcShop.name, AqcShop.shop_type).where(_store_or_repair_condition())
    scope_conditions = scoped_shop_conditions(user)
    if scope_conditions:
        stmt = stmt.where(*scope_conditions)
    keyword = (q or "").strip()
    if keyword:
        stmt = stmt.where(AqcShop.name.like(f"%{keyword}%"))

    rows = db.execute(
        stmt.order_by(AqcShop.id.asc()).limit(limit)
    ).all()
    options = [
        ShopOptionOut(
            id=int(row[0]),
            name=str(row[1] or ""),
            shopType=SHOP_TYPE_REPAIR if int(row[2] or 0) == SHOP_TYPE_REPAIR else SHOP_TYPE_STORE,
        )
        for row in rows
    ]
    return {"success": True, "options": options}


@router.get("", response_model=ShopListResponse)
def list_shops(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    shop_type: int | None = Query(default=None, ge=0, le=20),
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcShop).options(
        selectinload(AqcShop.creator).load_only(AqcUser.id, AqcUser.display_name),
        selectinload(AqcShop.manager_user).load_only(
            AqcUser.id,
            AqcUser.username,
            AqcUser.display_name,
            AqcUser.is_active,
        ),
        selectinload(AqcShop.assigned_users).load_only(
            AqcUser.id,
            AqcUser.username,
            AqcUser.display_name,
            AqcUser.is_active,
            AqcUser.aqc_role_key,
            AqcUser.role,
            AqcUser.vip,
        ),
    )
    count_stmt = select(func.count(AqcShop.id))

    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        condition = or_(
            AqcShop.name.like(like),
            AqcShop.phone.like(like),
            AqcShop.address.like(like),
            AqcShop.manager_name.like(like),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    if shop_type is not None:
        if int(shop_type) == SHOP_TYPE_WAREHOUSE:
            condition = _warehouse_condition()
        elif int(shop_type) == SHOP_TYPE_OTHER_WAREHOUSE:
            condition = _other_warehouse_condition()
        elif int(shop_type) == SHOP_TYPE_REPAIR:
            condition = _repair_condition()
        else:
            condition = _store_condition()
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.execute(count_stmt).scalar() or 0
    rows = (
        db.execute(
            stmt.order_by(AqcShop.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    goods_quantity_map = aggregate_shop_goods_quantity(db, [item.id for item in rows])
    shop_member_map = _build_shop_member_map(db, [item.id for item in rows])

    return {
        "success": True,
        "total": int(total),
        "shops": [
            _to_shop_out(
                item,
                goods_quantity=goods_quantity_map.get(item.id, 0),
                member_users=shop_member_map.get(int(item.id), []),
            )
            for item in rows
        ],
    }


@router.get("/{shop_id}/inventory-logs", response_model=InventoryLogListResponse)
def list_shop_inventory_logs(
    shop_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    item_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    _user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(AqcShop).where(AqcShop.id == shop_id).limit(1)).scalars().first()
    if shop is None:
        return {"success": False, "total": 0, "logs": []}
    total, rows = list_inventory_logs(
        db,
        goods_item_id=int(item_id) if item_id is not None else None,
        shop_id=int(shop_id),
        keyword=q,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    total_after_map = inventory_log_total_after_map(
        db,
        rows,
        goods_item_id=int(item_id) if item_id is not None else None,
        shop_id=int(shop_id),
    )
    return {
        "success": True,
        "total": total,
        "currentQuantityTotal": inventory_log_scope_current_total(
            db,
            goods_item_id=int(item_id) if item_id is not None else None,
            shop_id=int(shop_id),
        ),
        "logs": [_to_inventory_log_out(item, total_quantity_after=total_after_map.get(int(item.id), 0)) for item in rows],
    }


def _normalize_selected_user_ids(user_ids: list[int] | None) -> list[int]:
    normalized: list[int] = []
    for item in user_ids or []:
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            continue
        if user_id > 0 and user_id not in normalized:
            normalized.append(user_id)
    return normalized


def _apply_shop_user_assignments(
    db: Session,
    shop: AqcShop,
    *,
    manager_user_id: int | None,
    salesperson_ids: list[int] | None,
    manager_name: str | None,
) -> str | None:
    if _is_other_warehouse_shop(shop):
        current_assigned_users = db.execute(select(AqcUser).where(AqcUser.shop_id == shop.id)).scalars().all()
        for current_user in current_assigned_users:
            next_shop_ids = [item for item in user_shop_ids(current_user) if item != shop.id]
            assign_user_shops(current_user, next_shop_ids)
        shop.manager_user_id = None
        shop.manager_name = None
        return None

    if _is_repair_shop(shop):
        selected_ids = _normalize_selected_user_ids(salesperson_ids)
        selected_users = (
            db.execute(select(AqcUser).where(AqcUser.id.in_(selected_ids))).scalars().all()
            if selected_ids
            else []
        )
        selected_user_map = {item.id: item for item in selected_users}
        missing_ids = [str(item) for item in selected_ids if item not in selected_user_map]
        if missing_ids:
            return f"所选工程师账户不存在：{', '.join(missing_ids)}"

        invalid_users = [
            (item.display_name or item.username or str(item.id)).strip()
            for item in selected_users
            if not _is_repair_engineer_eligible(item)
        ]
        if invalid_users:
            return f"以下账户不是可用工程师或管理员：{'、'.join(invalid_users)}"

        current_assigned_users = db.execute(select(AqcUser).where(AqcUser.shop_id == shop.id)).scalars().all()
        for current_user in current_assigned_users:
            if current_user.id not in selected_user_map:
                next_shop_ids = [item for item in user_shop_ids(current_user) if item != shop.id]
                assign_user_shops(current_user, next_shop_ids)

        for selected_user in selected_users:
            assign_user_shops(selected_user, [shop.id, *user_shop_ids(selected_user)])

        shop.manager_user_id = None
        shop.manager_name = None
        return None

    if _is_warehouse_shop(shop):
        if manager_user_id is not None:
            manager_user = db.execute(select(AqcUser).where(AqcUser.id == int(manager_user_id)).limit(1)).scalars().first()
            if manager_user is None:
                return "库管账户不存在"
            if not manager_user.is_active or get_aqc_role_key(manager_user) == "aqc_departed":
                return "所选库管账户不可用"
            shop.manager_user_id = manager_user.id
            shop.manager_name = ((manager_user.display_name or manager_user.username or "").strip()[:120] or None)
        else:
            shop.manager_user_id = None
            shop.manager_name = (manager_name or "").strip()[:120] or None
        return None

    selected_ids = _normalize_selected_user_ids(salesperson_ids)
    if manager_user_id:
        manager_user_id = int(manager_user_id)
        if manager_user_id not in selected_ids:
            selected_ids.insert(0, manager_user_id)

    selected_users = (
        db.execute(select(AqcUser).where(AqcUser.id.in_(selected_ids))).scalars().all()
        if selected_ids
        else []
    )
    selected_user_map = {item.id: item for item in selected_users}
    missing_ids = [str(item) for item in selected_ids if item not in selected_user_map]
    if missing_ids:
        return f"所选账户不存在：{', '.join(missing_ids)}"

    invalid_users = [
        (item.display_name or item.username or str(item.id)).strip()
        for item in selected_users
        if not item.is_active or get_aqc_role_key(item) == "aqc_departed"
    ]
    if invalid_users:
        return f"以下账户不可分配到门店：{'、'.join(invalid_users)}"

    if manager_user_id is not None and manager_user_id not in selected_user_map:
        return "店长账户不存在"

    current_assigned_users = db.execute(select(AqcUser).where(AqcUser.shop_id == shop.id)).scalars().all()
    for current_user in current_assigned_users:
        if current_user.id not in selected_user_map:
            next_shop_ids = [item for item in user_shop_ids(current_user) if item != shop.id]
            assign_user_shops(current_user, next_shop_ids)

    for selected_user in selected_users:
        assign_user_shops(selected_user, [shop.id, *user_shop_ids(selected_user)])

    if manager_user_id is not None:
        manager_user = selected_user_map.get(manager_user_id)
        shop.manager_user_id = manager_user_id
        shop.manager_name = ((manager_user.display_name or manager_user.username or "").strip()[:120] or None) if manager_user else None
    else:
        shop.manager_user_id = None
        shop.manager_name = (manager_name or "").strip()[:120] or None

    return None


@router.post("", response_model=MessageResponse)
def create_shop(
    payload: ShopCreateRequest,
    user: AqcUser = Depends(require_permissions("shops.write")),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        return {"success": False, "message": "名称不能为空"}

    shop = AqcShop(
        name=name[:255],
        image=(payload.image or "").strip()[:500],
        phone=(payload.phone or "").strip()[:40] or None,
        address=(payload.address or "").strip()[:255],
        province=(payload.province or "").strip()[:100] or None,
        city=(payload.city or "").strip()[:100] or None,
        district=(payload.district or "").strip()[:100] or None,
        latitude=(payload.latitude or "").strip()[:50] or None,
        longitude=(payload.longitude or "").strip()[:50] or None,
        business_hours=(payload.businessHours or "").strip()[:100] or None,
        brand_ids=(payload.brandIds or "").strip(),
        shop_type=int(payload.shopType),
        channel=int(payload.channel),
        schedule_enabled=bool(payload.scheduleEnabled) if int(payload.shopType) == SHOP_TYPE_STORE else False,
        target_enabled=bool(payload.targetEnabled) if int(payload.shopType) == SHOP_TYPE_STORE else False,
        report_enabled=bool(payload.reportEnabled) if _can_enable_report_for_shop(shop_type=int(payload.shopType), name=name) else False,
        manager_user_id=payload.managerUserId,
        manager_name=(payload.managerName or "").strip()[:120] or None,
        division=(payload.division or "").strip()[:120] or None,
        share_code=(payload.shareCode or "").strip()[:255] or None,
        status=1,
        is_enabled=True,
        created_by=user.id,
    )
    db.add(shop)
    db.flush()
    assignment_error = _apply_shop_user_assignments(
        db,
        shop,
        manager_user_id=payload.managerUserId,
        salesperson_ids=payload.salespersonIds,
        manager_name=payload.managerName,
    )
    if assignment_error:
        db.rollback()
        return {"success": False, "message": assignment_error}
    db.commit()
    return {"success": True, "message": "店铺/仓库创建成功"}


@router.put("/{shop_id}", response_model=MessageResponse)
def update_shop(
    shop_id: int,
    payload: ShopUpdateRequest,
    _user: AqcUser = Depends(require_permissions("shops.write")),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(AqcShop).where(AqcShop.id == shop_id).limit(1)).scalars().first()
    if shop is None:
        return {"success": False, "message": "店铺不存在"}

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            return {"success": False, "message": "名称不能为空"}
        shop.name = name[:255]

    if payload.image is not None:
        shop.image = (payload.image or "").strip()[:500]
    if payload.phone is not None:
        shop.phone = (payload.phone or "").strip()[:40] or None
    if payload.address is not None:
        shop.address = (payload.address or "").strip()[:255]
    if payload.province is not None:
        shop.province = (payload.province or "").strip()[:100] or None
    if payload.city is not None:
        shop.city = (payload.city or "").strip()[:100] or None
    if payload.district is not None:
        shop.district = (payload.district or "").strip()[:100] or None
    if payload.latitude is not None:
        shop.latitude = (payload.latitude or "").strip()[:50] or None
    if payload.longitude is not None:
        shop.longitude = (payload.longitude or "").strip()[:50] or None
    if payload.businessHours is not None:
        shop.business_hours = (payload.businessHours or "").strip()[:100] or None
    if payload.brandIds is not None:
        shop.brand_ids = (payload.brandIds or "").strip()
    if payload.shopType is not None:
        shop.shop_type = int(payload.shopType)
        if int(shop.shop_type or 0) != SHOP_TYPE_STORE:
            shop.schedule_enabled = False
            shop.target_enabled = False
            shop.report_enabled = False
    if payload.channel is not None:
        shop.channel = int(payload.channel)
    if payload.scheduleEnabled is not None:
        shop.schedule_enabled = bool(payload.scheduleEnabled) if int(shop.shop_type or 0) == SHOP_TYPE_STORE else False
    if payload.targetEnabled is not None:
        shop.target_enabled = bool(payload.targetEnabled) if int(shop.shop_type or 0) == SHOP_TYPE_STORE else False
    if payload.reportEnabled is not None:
        shop.report_enabled = bool(payload.reportEnabled) if _can_enable_report_for_shop(shop_type=int(shop.shop_type or 0), name=shop.name) else False
    if payload.managerUserId is not None:
        shop.manager_user_id = payload.managerUserId
    if payload.managerName is not None:
        shop.manager_name = (payload.managerName or "").strip()[:120] or None
    if payload.division is not None:
        shop.division = (payload.division or "").strip()[:120] or None
    if payload.shareCode is not None:
        shop.share_code = (payload.shareCode or "").strip()[:255] or None

    if not _can_enable_report_for_shop(shop_type=int(shop.shop_type or 0), name=shop.name):
        shop.report_enabled = False

    if payload.managerUserId is not None or payload.salespersonIds is not None or payload.managerName is not None:
        assignment_error = _apply_shop_user_assignments(
            db,
            shop,
            manager_user_id=payload.managerUserId,
            salesperson_ids=payload.salespersonIds,
            manager_name=payload.managerName,
        )
        if assignment_error:
            db.rollback()
            return {"success": False, "message": assignment_error}

    db.commit()
    return {"success": True, "message": "店铺/仓库更新成功"}


@router.delete("/{shop_id}", response_model=MessageResponse)
def delete_shop(
    shop_id: int,
    _user: AqcUser = Depends(require_permissions("shops.manage")),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(AqcShop).where(AqcShop.id == shop_id).limit(1)).scalars().first()
    if shop is None:
        return {"success": False, "message": "店铺不存在"}

    goods_items = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.shop_id == shop.id)).scalars().all()
    for goods_item in goods_items:
        goods_item.shop_id = None

    inventory_rows = db.execute(select(AqcGoodsInventory).where(AqcGoodsInventory.shop_id == shop.id)).scalars().all()
    affected_goods_ids = sorted({int(item.goods_item_id) for item in inventory_rows if item.goods_item_id})
    for inventory_row in inventory_rows:
        db.delete(inventory_row)

    db.delete(shop)
    recalculate_goods_stock(db, affected_goods_ids)
    db.commit()
    return {"success": True, "message": "店铺/仓库已删除"}

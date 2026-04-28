from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .models import AqcGoodsItem, AqcGoodsInventory, AqcInventoryLog, AqcShop, AqcUser


SHOP_TYPE_STORE = 0
SHOP_TYPE_WAREHOUSE = 1
SHOP_TYPE_OTHER_WAREHOUSE = 2
SHOP_TYPE_REPAIR = 3
SHOP_NAME_NORMALIZATION_ALIASES = {
    "澳群淘宝": "澳群线上Casio淘宝",
    "澳群线上casio淘宝": "澳群线上Casio淘宝",
    "武汉新佳丽广场casio专卖店": "武汉新佳丽Casio专卖店",
    "武汉新佳丽casio专卖店": "武汉新佳丽Casio专卖店",
    "武汉世贸广场casio专柜": "武商世贸Casio专柜",
    "武商世贸casio专柜": "武商世贸Casio专柜",
    "十堰武商卡西欧专柜": "十堰武商Casio专柜",
    "十堰武商casio专柜": "十堰武商Casio专柜",
}
SHOP_NAME_ALIASES = (
    ("澳群线上casio淘宝", "澳群淘宝"),
    ("澳群淘宝", "澳群淘宝"),
    ("武商梦时代casio专卖店", "梦时代"),
    ("梦时代", "梦时代"),
    ("武汉新佳丽广场casio专卖店", "新佳丽"),
    ("武汉新佳丽casio专卖店", "新佳丽"),
    ("新佳丽", "新佳丽"),
    ("武汉世贸广场casio专柜", "世贸"),
    ("武商世贸casio专柜", "世贸"),
    ("世贸广场", "世贸"),
    ("十堰武商卡西欧专柜", "十堰武商"),
    ("十堰武商casio专柜", "十堰武商"),
    ("十堰武商", "十堰武商"),
    ("武商奥莱casio专柜", "武商奥莱"),
    ("武商奥莱", "武商奥莱"),
    ("宜昌国贸casio专卖店", "宜昌国贸"),
    ("宜昌国贸", "宜昌国贸"),
    ("武昌万象城casio专卖店", "武昌万象城"),
    ("武昌万象城", "武昌万象城"),
    ("孝感保利仓库", "孝感保利"),
    ("孝感保利", "孝感保利"),
)


def _clean_shop_name(value: str | None) -> str:
    return str(value or "").strip()[:255]


def _normalize_shop_lookup_key(value: str | None) -> str:
    clean_name = _clean_shop_name(value)
    if not clean_name:
        return ""
    return "".join(ch.lower() if ch.isascii() else ch for ch in clean_name if not ch.isspace())


def normalize_shop_name(shop_name: str | None) -> tuple[str, str]:
    original = _clean_shop_name(shop_name)
    if not original:
        return "", ""
    normalized = SHOP_NAME_NORMALIZATION_ALIASES.get(_normalize_shop_lookup_key(original), original)
    return original, normalized


def simplify_shop_name(shop_name: str | None) -> str:
    _, clean_name = normalize_shop_name(shop_name)
    if not clean_name:
        return ""
    lookup_key = _normalize_shop_lookup_key(clean_name)
    for keyword, alias in SHOP_NAME_ALIASES:
        if keyword in lookup_key:
            return alias
    return clean_name


def is_warehouse_shop(item: AqcShop | None) -> bool:
    if item is None:
        return False
    return item.legacy_id is None and int(item.shop_type or 0) == SHOP_TYPE_WAREHOUSE


def is_other_warehouse_shop(item: AqcShop | None) -> bool:
    if item is None:
        return False
    return item.legacy_id is None and int(item.shop_type or 0) == SHOP_TYPE_OTHER_WAREHOUSE


def resolved_shop_type(item: AqcShop | None) -> int:
    if item is not None and item.legacy_id is None and int(item.shop_type or 0) == SHOP_TYPE_REPAIR:
        return SHOP_TYPE_REPAIR
    if is_other_warehouse_shop(item):
        return SHOP_TYPE_OTHER_WAREHOUSE
    return SHOP_TYPE_WAREHOUSE if is_warehouse_shop(item) else SHOP_TYPE_STORE


def aggregate_shop_goods_quantity(db: Session, shop_ids: list[int] | None) -> dict[int, int]:
    normalized_ids = sorted({int(item) for item in (shop_ids or []) if int(item) > 0})
    if not normalized_ids:
        return {}

    rows = db.execute(
        select(
            AqcGoodsInventory.shop_id,
            func.coalesce(func.sum(AqcGoodsInventory.quantity), 0),
        )
        .where(AqcGoodsInventory.shop_id.in_(normalized_ids))
        .group_by(AqcGoodsInventory.shop_id)
    ).all()
    return {int(row[0]): int(row[1] or 0) for row in rows if row[0] is not None}


def recalculate_goods_stock(db: Session, goods_item_ids: list[int] | None) -> dict[int, int]:
    normalized_ids = sorted({int(item) for item in (goods_item_ids or []) if int(item) > 0})
    if not normalized_ids:
        return {}

    rows = db.execute(
        select(
            AqcGoodsInventory.goods_item_id,
            func.coalesce(func.sum(AqcGoodsInventory.quantity), 0),
        )
        .where(AqcGoodsInventory.goods_item_id.in_(normalized_ids))
        .group_by(AqcGoodsInventory.goods_item_id)
    ).all()
    total_map = {int(row[0]): int(row[1] or 0) for row in rows if row[0] is not None}

    items = db.execute(
        select(AqcGoodsItem).where(AqcGoodsItem.id.in_(normalized_ids))
    ).scalars().all()
    for item in items:
        item.stock = int(total_map.get(int(item.id), 0))

    return total_map


def inventory_actor_name(actor: AqcUser | None = None, *, actor_name: str | None = None) -> str:
    if actor is not None:
        return str(actor.display_name or actor.username or "").strip()[:80]
    return str(actor_name or "").strip()[:80]


def _inventory_log_bounds(raw: str | None, *, end: bool = False) -> datetime | None:
    clean = str(raw or "").strip()
    if not clean:
        return None
    try:
        if len(clean) <= 10:
            base = datetime.fromisoformat(clean)
            return base + timedelta(days=1) if end else base
        return datetime.fromisoformat(clean.replace("T", " "))
    except Exception:
        return None


def _get_inventory_row(db: Session, goods_item_id: int, shop_id: int) -> AqcGoodsInventory | None:
    return (
        db.execute(
            select(AqcGoodsInventory)
            .where(
                AqcGoodsInventory.goods_item_id == int(goods_item_id),
                AqcGoodsInventory.shop_id == int(shop_id),
            )
            .limit(1)
        )
        .scalars()
        .first()
    )


def append_inventory_log(
    db: Session,
    *,
    goods_item: AqcGoodsItem | None,
    shop: AqcShop | None,
    quantity_before: int,
    quantity_after: int,
    change_content: str,
    operator_id: int | None = None,
    operator_name: str | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
    created_at: datetime | None = None,
) -> AqcInventoryLog:
    log = AqcInventoryLog(
        goods_item_id=int(goods_item.id) if goods_item and goods_item.id is not None else None,
        goods_name=str(goods_item.name or "").strip()[:191] if goods_item else "",
        goods_model=str(goods_item.model_name or goods_item.name or "").strip()[:191] if goods_item else "",
        shop_id=int(shop.id) if shop and shop.id is not None else None,
        shop_name=str(shop.name or "").strip()[:255] if shop else "",
        change_content=str(change_content or "").strip()[:255],
        quantity_before=int(quantity_before or 0),
        quantity_after=int(quantity_after or 0),
        operator_id=int(operator_id) if operator_id is not None else None,
        operator_name=str(operator_name or "").strip()[:80],
        related_type=str(related_type or "").strip()[:40],
        related_id=int(related_id) if related_id is not None else None,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(log)
    return log


def set_inventory_quantity(
    db: Session,
    *,
    goods_item: AqcGoodsItem,
    shop: AqcShop,
    quantity: int,
    change_content: str,
    operator_id: int | None = None,
    operator_name: str | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
    created_at: datetime | None = None,
) -> tuple[int, int]:
    current_row = _get_inventory_row(db, int(goods_item.id), int(shop.id))
    before_quantity = int(current_row.quantity or 0) if current_row is not None else 0
    after_quantity = int(quantity or 0)
    if before_quantity == after_quantity:
        return before_quantity, after_quantity

    if current_row is None:
        if after_quantity != 0:
            db.add(
                AqcGoodsInventory(
                    goods_item_id=int(goods_item.id),
                    shop_id=int(shop.id),
                    quantity=after_quantity,
                )
            )
    elif after_quantity == 0:
        db.delete(current_row)
    else:
        current_row.quantity = after_quantity

    append_inventory_log(
        db,
        goods_item=goods_item,
        shop=shop,
        quantity_before=before_quantity,
        quantity_after=after_quantity,
        change_content=change_content,
        operator_id=operator_id,
        operator_name=operator_name,
        related_type=related_type,
        related_id=related_id,
        created_at=created_at,
    )
    return before_quantity, after_quantity


def apply_inventory_delta(
    db: Session,
    *,
    goods_item: AqcGoodsItem,
    shop: AqcShop,
    delta: int,
    change_content: str,
    operator_id: int | None = None,
    operator_name: str | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
    created_at: datetime | None = None,
) -> tuple[int, int]:
    if int(delta or 0) == 0:
        current_row = _get_inventory_row(db, int(goods_item.id), int(shop.id))
        current_quantity = int(current_row.quantity or 0) if current_row is not None else 0
        return current_quantity, current_quantity
    current_row = _get_inventory_row(db, int(goods_item.id), int(shop.id))
    current_quantity = int(current_row.quantity or 0) if current_row is not None else 0
    return set_inventory_quantity(
        db,
        goods_item=goods_item,
        shop=shop,
        quantity=current_quantity + int(delta or 0),
        change_content=change_content,
        operator_id=operator_id,
        operator_name=operator_name,
        related_type=related_type,
        related_id=related_id,
        created_at=created_at,
    )


def replace_goods_inventory_quantities(
    db: Session,
    *,
    goods_item: AqcGoodsItem,
    quantity_map: dict[int, int],
    scope_shop_ids: list[int] | None = None,
    change_content: str,
    operator_id: int | None = None,
    operator_name: str | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
    created_at: datetime | None = None,
) -> int:
    normalized_quantity_map = {
        int(shop_id): int(quantity)
        for shop_id, quantity in (quantity_map or {}).items()
        if int(shop_id) > 0
    }
    normalized_scope_ids = sorted(
        {
            int(shop_id)
            for shop_id in (
                (scope_shop_ids or [])
                + list(normalized_quantity_map.keys())
            )
            if int(shop_id) > 0
        }
    )
    if not normalized_scope_ids:
        return 0

    shops = db.execute(
        select(AqcShop).where(AqcShop.id.in_(normalized_scope_ids))
    ).scalars().all()
    shop_map = {int(item.id): item for item in shops if item.id is not None}
    changed_count = 0
    for shop_id in normalized_scope_ids:
        shop = shop_map.get(int(shop_id))
        if shop is None:
            continue
        before_quantity, after_quantity = set_inventory_quantity(
            db,
            goods_item=goods_item,
            shop=shop,
            quantity=int(normalized_quantity_map.get(int(shop_id), 0)),
            change_content=change_content,
            operator_id=operator_id,
            operator_name=operator_name,
            related_type=related_type,
            related_id=related_id,
            created_at=created_at,
        )
        if before_quantity != after_quantity:
            changed_count += 1
    return changed_count


def list_inventory_logs(
    db: Session,
    *,
    goods_item_id: int | None = None,
    shop_id: int | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[AqcInventoryLog]]:
    stmt = select(AqcInventoryLog)
    count_stmt = select(func.count(AqcInventoryLog.id))

    conditions: list = []
    if goods_item_id is not None and int(goods_item_id) > 0:
        conditions.append(AqcInventoryLog.goods_item_id == int(goods_item_id))
    if shop_id is not None and int(shop_id) > 0:
        conditions.append(AqcInventoryLog.shop_id == int(shop_id))

    clean_keyword = str(keyword or "").strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        conditions.append(
            or_(
                AqcInventoryLog.goods_model.like(like),
                AqcInventoryLog.goods_name.like(like),
                AqcInventoryLog.shop_name.like(like),
                AqcInventoryLog.change_content.like(like),
                AqcInventoryLog.operator_name.like(like),
            )
        )

    parsed_start = _inventory_log_bounds(date_from)
    if parsed_start is not None:
        conditions.append(AqcInventoryLog.created_at >= parsed_start)
    parsed_end = _inventory_log_bounds(date_to, end=True)
    if parsed_end is not None:
        conditions.append(AqcInventoryLog.created_at < parsed_end)

    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = int(db.execute(count_stmt).scalar() or 0)
    rows = (
        db.execute(
            stmt.order_by(AqcInventoryLog.created_at.desc(), AqcInventoryLog.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return total, rows


def inventory_log_scope_current_total(
    db: Session,
    *,
    goods_item_id: int | None = None,
    shop_id: int | None = None,
) -> int:
    stmt = select(func.coalesce(func.sum(AqcGoodsInventory.quantity), 0))
    if goods_item_id is not None and int(goods_item_id) > 0:
        stmt = stmt.where(AqcGoodsInventory.goods_item_id == int(goods_item_id))
    if shop_id is not None and int(shop_id) > 0:
        stmt = stmt.where(AqcGoodsInventory.shop_id == int(shop_id))
    return int(db.execute(stmt).scalar() or 0)


def inventory_log_total_after_map(
    db: Session,
    rows: list[AqcInventoryLog],
    *,
    goods_item_id: int | None = None,
    shop_id: int | None = None,
) -> dict[int, int]:
    if not rows:
        return {}

    current_total = inventory_log_scope_current_total(
        db,
        goods_item_id=goods_item_id,
        shop_id=shop_id,
    )
    anchor = rows[0]
    newer_stmt = select(func.coalesce(func.sum(AqcInventoryLog.quantity_after - AqcInventoryLog.quantity_before), 0))
    if goods_item_id is not None and int(goods_item_id) > 0:
        newer_stmt = newer_stmt.where(AqcInventoryLog.goods_item_id == int(goods_item_id))
    if shop_id is not None and int(shop_id) > 0:
        newer_stmt = newer_stmt.where(AqcInventoryLog.shop_id == int(shop_id))
    newer_stmt = newer_stmt.where(
        or_(
            AqcInventoryLog.created_at > anchor.created_at,
            and_(
                AqcInventoryLog.created_at == anchor.created_at,
                AqcInventoryLog.id > anchor.id,
            ),
        )
    )
    future_delta = int(db.execute(newer_stmt).scalar() or 0)

    result: dict[int, int] = {}
    for row in rows:
        result[int(row.id)] = int(current_total - future_delta)
        future_delta += int(row.quantity_after or 0) - int(row.quantity_before or 0)
    return result

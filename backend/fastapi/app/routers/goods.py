from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import require_permissions, to_iso
from ..goods_attributes import (
    GOODS_ATTRIBUTE_NONE,
    GOODS_ATTRIBUTE_VALUES,
    clean_goods_text,
    compose_goods_name,
    normalize_goods_attribute,
    split_model_attribute,
)
from ..importers.inventory_template_import import import_inventory_template, inspect_inventory_template_import
from ..importers.ngoods_import import import_ngoods_catalog, inspect_ngoods_catalog_import
from ..inventory import (
    inventory_actor_name,
    inventory_log_scope_current_total,
    inventory_log_total_after_map,
    list_inventory_logs,
    recalculate_goods_stock,
    replace_goods_inventory_quantities,
    resolved_shop_type,
    simplify_shop_name,
)
from ..models import AqcGoodsItem, AqcGoodsInventory, AqcInventoryLog, AqcSaleRecord, AqcShop, AqcUser
from ..schemas import (
    GoodsBarcodeLookupResponse,
    GoodsCatalogMetaResponse,
    GoodsCatalogImportResponse,
    GoodsFilterOptionOut,
    GoodsIndexOptionOut,
    GoodsInventoryOut,
    GoodsInventoryResponse,
    GoodsInventoryUpdateRequest,
    GoodsItemCreateRequest,
    GoodsItemDetailResponse,
    GoodsItemListResponse,
    GoodsItemOut,
    GoodsItemSummaryOut,
    GoodsItemUpdateRequest,
    InventoryLogListResponse,
    InventoryLogOut,
    MessageResponse,
)


router = APIRouter(prefix="/goods", tags=["goods"])

CATALOG_READY_CONDITION = or_(
    func.coalesce(AqcGoodsItem.model_name, "") != "",
    func.coalesce(AqcGoodsItem.name, "") != "",
    func.coalesce(AqcGoodsItem.barcode, "") != "",
)

SORT_FIELD_MAP = {
    "product_code": AqcGoodsItem.updated_at,
    "brand": AqcGoodsItem.brand,
    "series": AqcGoodsItem.series_name,
    "model": AqcGoodsItem.model_name,
    "price": AqcGoodsItem.price,
    "barcode": AqcGoodsItem.barcode,
    "stock": AqcGoodsItem.stock,
    "sales_count": AqcGoodsItem.sale_num,
    "updated_at": AqcGoodsItem.updated_at,
    "created_at": AqcGoodsItem.created_at,
}


def _clean_text(value: str | None, max_length: int) -> str:
    return clean_goods_text(value, max_length)


def _to_amount(value: float | int | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_index_key(
    brand: str,
    series: str,
    model: str,
    provided: str | None = None,
) -> str:
    seed = (provided or "").strip() or brand.strip() or series.strip() or model.strip()
    if not seed:
        return "#"
    for ch in seed:
        if ch.isascii() and ch.isalnum():
            return ch.upper()
        if ch.isdigit():
            return ch
    return "#"


def _find_identifier_conflict(
    db: Session,
    *,
    barcode: str = "",
    exclude_item_id: int | None = None,
) -> str | None:
    clean_barcode = barcode.strip()
    if clean_barcode:
        stmt = select(AqcGoodsItem.id).where(AqcGoodsItem.barcode == clean_barcode)
        if exclude_item_id is not None:
            stmt = stmt.where(AqcGoodsItem.id != exclude_item_id)
        if db.execute(stmt.limit(1)).scalar() is not None:
            return "商品条码已存在，请确认后重试"

    return None


def _normalize_goods_signature(
    *,
    brand: str = "",
    series: str = "",
    model: str = "",
    model_attribute: str = GOODS_ATTRIBUTE_NONE,
) -> tuple[str, str, str, str]:
    normalized_attribute = normalize_goods_attribute(model_attribute)
    return (
        _clean_text(brand, 120),
        _clean_text(series, 120),
        _clean_text(model, 191),
        normalized_attribute if normalized_attribute in GOODS_ATTRIBUTE_VALUES else GOODS_ATTRIBUTE_NONE,
    )


def _find_goods_by_signature(
    db: Session,
    *,
    brand: str = "",
    series: str = "",
    model: str = "",
    model_attribute: str = GOODS_ATTRIBUTE_NONE,
    exclude_item_id: int | None = None,
) -> list[AqcGoodsItem]:
    signature = _normalize_goods_signature(
        brand=brand,
        series=series,
        model=model,
        model_attribute=model_attribute,
    )
    if not any(signature[:3]):
        return []
    stmt = select(AqcGoodsItem).where(
        AqcGoodsItem.brand == signature[0],
        AqcGoodsItem.series_name == signature[1],
        AqcGoodsItem.model_name == signature[2],
        AqcGoodsItem.model_attribute == signature[3],
    )
    if exclude_item_id is not None:
        stmt = stmt.where(AqcGoodsItem.id != exclude_item_id)
    return db.execute(stmt.order_by(AqcGoodsItem.id.asc())).scalars().all()


def _find_signature_conflict(
    db: Session,
    *,
    brand: str = "",
    series: str = "",
    model: str = "",
    model_attribute: str = GOODS_ATTRIBUTE_NONE,
    barcode: str = "",
    exclude_item_id: int | None = None,
) -> str | None:
    matches = _find_goods_by_signature(
        db,
        brand=brand,
        series=series,
        model=model,
        model_attribute=model_attribute,
        exclude_item_id=exclude_item_id,
    )
    if not matches:
        return None
    clean_barcode = _clean_text(barcode, 64)
    if clean_barcode:
        return None
    return "已存在同名商品，请补充条码后再新增，避免库存混淆"


def _normalize_has_stock_filter(value: str | bool | None) -> str | None:
    if isinstance(value, bool):
        return "nonzero" if value else None
    clean = str(value or "").strip().lower()
    if clean in {"", "all", "none"}:
        return None
    if clean in {"true", "1", "nonzero"}:
        return "nonzero"
    if clean in {"zero", "0"}:
        return "zero"
    if clean in {"negative", "abnormal", "lt0"}:
        return "negative"
    return None


def _parse_sales_date(raw: str | None, *, end: bool = False) -> datetime | None:
    clean = str(raw or "").strip()
    if not clean:
        return None
    try:
        base = datetime.fromisoformat(clean[:10])
    except Exception:
        return None
    if end:
        return base + timedelta(days=1)
    return base


def _build_goods_conditions(
    *,
    keyword: str = "",
    product_code: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    model_attribute: str | None = None,
    barcode: str | None = None,
    index_key: str | None = None,
    putaway: int | None = None,
    status: int | None = None,
    shop_id: int | None = None,
    distribution_shop_id: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    has_stock: str | bool | None = None,
    catalog_only: bool = True,
) -> list:
    conditions: list = []

    if catalog_only:
        conditions.append(CATALOG_READY_CONDITION)

    clean_keyword = keyword.strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        conditions.append(
            or_(
                AqcGoodsItem.brand.like(like),
                AqcGoodsItem.series_name.like(like),
                AqcGoodsItem.model_name.like(like),
                AqcGoodsItem.barcode.like(like),
                AqcGoodsItem.name.like(like),
                AqcGoodsItem.remark.like(like),
            )
        )

    if brand:
        conditions.append(AqcGoodsItem.brand == brand.strip())
    if series:
        conditions.append(AqcGoodsItem.series_name == series.strip())
    if model:
        conditions.append(AqcGoodsItem.model_name.like(f"%{model.strip()}%"))
    if model_attribute:
        normalized_attribute = normalize_goods_attribute(model_attribute)
        if normalized_attribute in GOODS_ATTRIBUTE_VALUES:
            conditions.append(AqcGoodsItem.model_attribute == normalized_attribute)
    if barcode:
        conditions.append(AqcGoodsItem.barcode.like(f"%{barcode.strip()}%"))
    if index_key:
        conditions.append(AqcGoodsItem.index_key == index_key.strip().upper()[:8])
    if putaway is not None:
        conditions.append(AqcGoodsItem.putaway == putaway)
    if status is not None:
        conditions.append(AqcGoodsItem.status == status)
    if shop_id is not None:
        conditions.append(AqcGoodsItem.shop_id == shop_id)
    normalized_has_stock = _normalize_has_stock_filter(has_stock)
    if normalized_has_stock:
        if distribution_shop_id is not None:
            quantity_operator = AqcGoodsInventory.quantity != 0
            if normalized_has_stock == "zero":
                quantity_operator = AqcGoodsInventory.quantity == 0
            elif normalized_has_stock == "negative":
                quantity_operator = AqcGoodsInventory.quantity < 0
            conditions.append(
                select(AqcGoodsInventory.id)
                .where(
                    AqcGoodsInventory.goods_item_id == AqcGoodsItem.id,
                    AqcGoodsInventory.shop_id == int(distribution_shop_id),
                    quantity_operator,
                )
                .exists()
            )
        else:
            if normalized_has_stock == "zero":
                conditions.append(AqcGoodsItem.stock == 0)
            elif normalized_has_stock == "negative":
                conditions.append(AqcGoodsItem.stock < 0)
            else:
                conditions.append(AqcGoodsItem.stock != 0)
    if price_min is not None:
        conditions.append(AqcGoodsItem.price >= _to_amount(price_min))
    if price_max is not None:
        conditions.append(AqcGoodsItem.price <= _to_amount(price_max))

    return conditions


def _load_goods_item_detail(db: Session, item_id: int) -> AqcGoodsItem | None:
    return (
        db.execute(
            select(AqcGoodsItem)
            .options(
                selectinload(AqcGoodsItem.shop).load_only(AqcShop.id, AqcShop.name),
                selectinload(AqcGoodsItem.creator).load_only(AqcUser.id, AqcUser.display_name),
            )
            .where(AqcGoodsItem.id == item_id)
            .limit(1)
        )
        .scalars()
        .first()
    )


def _inventory_quantity_map_for_shop(
    db: Session,
    goods_item_ids: list[int],
    shop_id: int | None,
) -> dict[int, int]:
    normalized_ids = sorted({int(item) for item in goods_item_ids if int(item) > 0})
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


def _inventory_quantity_maps_for_shops(
    db: Session,
    goods_item_ids: list[int],
    shop_ids: list[int],
) -> dict[int, dict[str, int]]:
    normalized_ids = sorted({int(item) for item in goods_item_ids if int(item) > 0})
    normalized_shop_ids = sorted({int(item) for item in shop_ids if int(item) > 0})
    if not normalized_ids or not normalized_shop_ids:
        return {}

    rows = db.execute(
        select(AqcGoodsInventory.goods_item_id, AqcGoodsInventory.shop_id, AqcGoodsInventory.quantity)
        .where(
            AqcGoodsInventory.goods_item_id.in_(normalized_ids),
            AqcGoodsInventory.shop_id.in_(normalized_shop_ids),
        )
    ).all()
    quantity_map: dict[int, dict[str, int]] = {}
    for goods_item_id, shop_id, quantity in rows:
        if goods_item_id is None or shop_id is None:
            continue
        quantity_map.setdefault(int(goods_item_id), {})[str(int(shop_id))] = int(quantity or 0)
    return quantity_map


def _sales_quantity_map(
    db: Session,
    goods_item_ids: list[int],
    *,
    sold_at_start: datetime | None = None,
    sold_at_end: datetime | None = None,
) -> dict[int, int]:
    normalized_ids = sorted({int(item) for item in goods_item_ids if int(item) > 0})
    if not normalized_ids:
        return {}

    conditions = [AqcSaleRecord.goods_id.in_(normalized_ids)]
    if sold_at_start is not None:
        conditions.append(AqcSaleRecord.sold_at >= sold_at_start)
    if sold_at_end is not None:
        conditions.append(AqcSaleRecord.sold_at < sold_at_end)

    rows = db.execute(
        select(AqcSaleRecord.goods_id, func.coalesce(func.sum(AqcSaleRecord.quantity), 0))
        .where(*conditions)
        .group_by(AqcSaleRecord.goods_id)
    ).all()
    return {
        int(goods_id): int(quantity or 0)
        for goods_id, quantity in rows
        if goods_id is not None
    }


def _sales_quantity_maps_for_shops(
    db: Session,
    goods_item_ids: list[int],
    shop_ids: list[int],
    *,
    sold_at_start: datetime | None = None,
    sold_at_end: datetime | None = None,
) -> dict[int, dict[str, int]]:
    normalized_ids = sorted({int(item) for item in goods_item_ids if int(item) > 0})
    normalized_shop_ids = sorted({int(item) for item in shop_ids if int(item) > 0})
    if not normalized_ids or not normalized_shop_ids:
        return {}

    conditions = [
        AqcSaleRecord.goods_id.in_(normalized_ids),
        AqcSaleRecord.shop_id.in_(normalized_shop_ids),
    ]
    if sold_at_start is not None:
        conditions.append(AqcSaleRecord.sold_at >= sold_at_start)
    if sold_at_end is not None:
        conditions.append(AqcSaleRecord.sold_at < sold_at_end)

    rows = db.execute(
        select(AqcSaleRecord.goods_id, AqcSaleRecord.shop_id, func.coalesce(func.sum(AqcSaleRecord.quantity), 0))
        .where(*conditions)
        .group_by(AqcSaleRecord.goods_id, AqcSaleRecord.shop_id)
    ).all()
    quantity_map: dict[int, dict[str, int]] = {}
    for goods_item_id, shop_id, quantity in rows:
        if goods_item_id is None or shop_id is None:
            continue
        quantity_map.setdefault(int(goods_item_id), {})[str(int(shop_id))] = int(quantity or 0)
    return quantity_map


def _sales_quantity_sort_subquery(
    *,
    sold_at_start: datetime | None = None,
    sold_at_end: datetime | None = None,
):
    conditions = [AqcSaleRecord.goods_id == AqcGoodsItem.id]
    if sold_at_start is not None:
        conditions.append(AqcSaleRecord.sold_at >= sold_at_start)
    if sold_at_end is not None:
        conditions.append(AqcSaleRecord.sold_at < sold_at_end)
    return (
        select(func.coalesce(func.sum(AqcSaleRecord.quantity), 0))
        .where(*conditions)
        .scalar_subquery()
    )


def _parse_compare_shop_ids(raw_value: str | None) -> list[int]:
    if raw_value is None:
        return []
    normalized_ids: list[int] = []
    for chunk in str(raw_value).split(","):
        text = chunk.strip()
        if not text or not text.isdigit():
            continue
        value = int(text)
        if value <= 0 or value in normalized_ids:
            continue
        normalized_ids.append(value)
    return normalized_ids


def _load_inventory_rows(db: Session, goods_item_id: int) -> list[GoodsInventoryOut]:
    inventory_rows = db.execute(
        select(AqcGoodsInventory).where(AqcGoodsInventory.goods_item_id == goods_item_id)
    ).scalars().all()
    quantity_map = {
        int(item.shop_id): int(item.quantity or 0)
        for item in inventory_rows
        if item.shop_id is not None
    }

    shops = db.execute(
        select(AqcShop).order_by(AqcShop.updated_at.desc(), AqcShop.id.desc())
    ).scalars().all()
    sorted_shops = sorted(
        shops,
        key=lambda item: (
            0 if resolved_shop_type(item) == 0 else 1,
            simplify_shop_name(item.name) or _clean_text(item.name, 255),
            _clean_text(item.name, 255),
            int(item.id),
        ),
    )

    return [
        GoodsInventoryOut(
            shopId=int(shop.id),
            shopName=_clean_text(shop.name, 255),
            shopShortName=simplify_shop_name(shop.name) or _clean_text(shop.name, 255),
            shopType=resolved_shop_type(shop),
            quantity=int(quantity_map.get(int(shop.id), 0)),
        )
        for shop in sorted_shops
    ]


def _normalize_inventory_quantity_map(payload: GoodsInventoryUpdateRequest) -> dict[int, int]:
    quantity_map: dict[int, int] = {}
    for entry in payload.quantities:
        shop_id = int(entry.shopId)
        if shop_id <= 0:
            continue
        quantity_map[shop_id] = int(entry.quantity or 0)
    return quantity_map


def _goods_catalog_import_message(stats: dict, *, dry_run: bool) -> str:
    created = int(stats.get("created") or 0)
    duplicates = int(stats.get("duplicates") or 0)
    invalid_rows = int(len(stats.get("invalidRows") or []))
    rows_ready = int(stats.get("rowsReady") or 0)

    if dry_run:
        if invalid_rows:
            return "校验未通过，请先处理无效行"
        if rows_ready <= 0 and duplicates > 0:
            return f"校验完成，没有可新增商品，已识别 {duplicates} 条重复商品"
        return f"校验完成，可新增 {int(stats.get('createdCandidates') or 0)} 条，重复 {duplicates} 条"

    if invalid_rows:
        return "商品表存在无效行，已中止导入"
    if created > 0 and duplicates > 0:
        return f"成功导入 {created} 条新商品，跳过 {duplicates} 条重复商品"
    if created > 0:
        return f"成功导入 {created} 条新商品"
    if duplicates > 0:
        return f"未导入新商品，{duplicates} 条均为重复商品"
    return "未导入新商品"


def _inventory_template_import_message(stats: dict, *, dry_run: bool) -> str:
    rows_ready = int(stats.get("rowsReady") or 0)
    updated_goods = int(stats.get("updatedGoods") or 0)
    changed_entries = int(stats.get("changedEntries") or 0)
    unmatched_goods = int(len(stats.get("unmatchedGoods") or []))
    ambiguous_goods = int(len(stats.get("ambiguousGoods") or []))
    unmatched_shops = int(len(stats.get("unmatchedShops") or []))

    if dry_run:
        if unmatched_shops:
            return f"校验未通过，存在 {unmatched_shops} 个未匹配店铺/仓库"
        if rows_ready <= 0:
            return f"校验完成，没有可导入的库存记录；缺失型号 {unmatched_goods} 个，歧义型号 {ambiguous_goods} 个"
        return f"校验完成，可更新 {rows_ready} 个商品库存；缺失型号 {unmatched_goods} 个，歧义型号 {ambiguous_goods} 个"

    if updated_goods > 0:
        return f"成功更新 {updated_goods} 个商品库存，写入 {changed_entries} 条库存变更；跳过缺失/歧义型号 {unmatched_goods + ambiguous_goods} 个"
    return f"没有写入库存变更；跳过缺失型号 {unmatched_goods} 个、歧义型号 {ambiguous_goods} 个"


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


def _to_goods_out(
    item: AqcGoodsItem,
    *,
    shop_quantity: int = 0,
    compare_quantities: dict[str, int] | None = None,
    sales_count: int | None = None,
    compare_sales_counts: dict[str, int] | None = None,
) -> GoodsItemOut:
    return GoodsItemOut(
        id=item.id,
        legacyId=item.legacy_id,
        name=item.name,
        productCode="",
        brand=item.brand or "",
        series=item.series_name or "",
        model=item.model_name or "",
        modelAttribute=normalize_goods_attribute(item.model_attribute),
        barcode=item.barcode or "",
        indexKey=item.index_key or "",
        categoryId=item.category_id,
        coverImage=item.cover_image or "",
        imageList=item.image_list or "[]",
        description=item.description or "",
        detail=item.detail or "",
        price=float(item.price or 0),
        originalPrice=float(item.original_price or 0),
        salePrice=float(item.sale_price or 0),
        score=item.score,
        stock=int(item.stock or 0),
        shopQuantity=int(shop_quantity or 0),
        compareQuantities={str(key): int(value or 0) for key, value in (compare_quantities or {}).items()},
        salesCount=int(item.sale_num if sales_count is None else sales_count),
        compareSalesCounts={str(key): int(value or 0) for key, value in (compare_sales_counts or {}).items()},
        saleNum=item.sale_num,
        sort=int(item.sort or 0),
        putaway=item.putaway,
        status=item.status,
        goodsType=item.goods_type,
        remark=item.remark or "",
        goodspec=item.goodspec,
        scoreRule=item.score_rule or "",
        legacyAdminId=item.legacy_admin_id,
        shopId=item.shop_id,
        shopName=item.shop.name if item.shop else None,
        createdBy=item.created_by,
        createdByName=item.creator.display_name if item.creator else None,
        createdAt=to_iso(item.created_at) or "",
        updatedAt=to_iso(item.updated_at) or "",
    )


def _to_goods_summary_out(
    item: AqcGoodsItem,
    *,
    shop_quantity: int = 0,
    compare_quantities: dict[str, int] | None = None,
    sales_count: int | None = None,
    compare_sales_counts: dict[str, int] | None = None,
) -> GoodsItemSummaryOut:
    return GoodsItemSummaryOut(
        id=item.id,
        legacyId=item.legacy_id,
        name=item.name,
        productCode="",
        brand=item.brand or "",
        series=item.series_name or "",
        model=item.model_name or "",
        modelAttribute=normalize_goods_attribute(item.model_attribute),
        barcode=item.barcode or "",
        indexKey=item.index_key or "",
        categoryId=item.category_id,
        coverImage=item.cover_image or "",
        price=float(item.price or 0),
        originalPrice=float(item.original_price or 0),
        salePrice=float(item.sale_price or 0),
        score=item.score,
        stock=int(item.stock or 0),
        shopQuantity=int(shop_quantity or 0),
        compareQuantities={str(key): int(value or 0) for key, value in (compare_quantities or {}).items()},
        salesCount=int(item.sale_num if sales_count is None else sales_count),
        compareSalesCounts={str(key): int(value or 0) for key, value in (compare_sales_counts or {}).items()},
        saleNum=item.sale_num,
        sort=int(item.sort or 0),
        putaway=item.putaway,
        status=item.status,
        goodsType=item.goods_type,
        remark=item.remark or "",
        goodspec=item.goodspec,
        legacyAdminId=item.legacy_admin_id,
        shopId=item.shop_id,
        shopName=item.shop.name if item.shop else None,
        createdBy=item.created_by,
        createdByName=item.creator.display_name if item.creator else None,
        createdAt=to_iso(item.created_at) or "",
        updatedAt=to_iso(item.updated_at) or "",
    )


def _build_inventory_response(
    db: Session,
    item: AqcGoodsItem,
    *,
    message: str | None = None,
) -> GoodsInventoryResponse:
    return GoodsInventoryResponse(
        success=True,
        message=message,
        item=_to_goods_summary_out(item),
        inventories=_load_inventory_rows(db, int(item.id)),
        totalStock=int(item.stock or 0),
    )


def _apply_payload_to_goods_item(
    goods_item: AqcGoodsItem,
    payload: GoodsItemCreateRequest | GoodsItemUpdateRequest,
    *,
    overwrite_name: bool,
) -> None:
    brand = _clean_text(payload.brand, 120) if payload.brand is not None else goods_item.brand or ""
    series = _clean_text(payload.series, 120) if payload.series is not None else goods_item.series_name or ""
    payload_model = payload.model if payload.model is not None else goods_item.model_name or ""
    payload_model_attribute = payload.modelAttribute if payload.modelAttribute is not None else goods_item.model_attribute or GOODS_ATTRIBUTE_NONE
    model, model_attribute = split_model_attribute(payload_model, payload_model_attribute)
    barcode = _clean_text(payload.barcode, 64) if payload.barcode is not None else goods_item.barcode or ""
    index_key = _normalize_index_key(brand, series, model, payload.indexKey)

    if payload.name is not None:
        goods_item.name = compose_goods_name(brand, series, model, payload.name)
    elif overwrite_name:
        goods_item.name = compose_goods_name(brand, series, model, goods_item.name)

    goods_item.product_code = ""
    goods_item.brand = brand
    goods_item.series_name = series
    goods_item.model_name = model
    goods_item.model_attribute = model_attribute
    goods_item.barcode = barcode
    goods_item.index_key = index_key

    if payload.categoryId is not None:
        goods_item.category_id = payload.categoryId
    if payload.coverImage is not None:
        goods_item.cover_image = _clean_text(payload.coverImage, 500)
    if payload.imageList is not None:
        goods_item.image_list = (payload.imageList or "[]").strip()
    if payload.description is not None:
        goods_item.description = (payload.description or "").strip()
    if payload.detail is not None:
        goods_item.detail = (payload.detail or "").strip()
    if payload.price is not None:
        goods_item.price = _to_amount(payload.price)
    if payload.originalPrice is not None:
        goods_item.original_price = _to_amount(payload.originalPrice)
    if payload.salePrice is not None:
        goods_item.sale_price = _to_amount(payload.salePrice)
    if payload.score is not None:
        goods_item.score = payload.score
    if payload.saleNum is not None:
        goods_item.sale_num = payload.saleNum
    if payload.sort is not None:
        goods_item.sort = payload.sort
    if payload.putaway is not None:
        goods_item.putaway = payload.putaway
    if payload.status is not None:
        goods_item.status = payload.status
    if payload.goodsType is not None:
        goods_item.goods_type = payload.goodsType
    if payload.remark is not None:
        goods_item.remark = _clean_text(payload.remark, 255)
    if payload.goodspec is not None:
        goods_item.goodspec = _clean_text(payload.goodspec, 255) or None
    if payload.scoreRule is not None:
        goods_item.score_rule = (payload.scoreRule or "").strip()
    if payload.legacyAdminId is not None:
        goods_item.legacy_admin_id = payload.legacyAdminId


@router.get("/items", response_model=GoodsItemListResponse)
def list_goods_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    q: str | None = None,
    product_code: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    model_attribute: str | None = None,
    barcode: str | None = None,
    index_key: str | None = None,
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    putaway: int | None = Query(default=None, ge=0, le=20),
    status: int | None = Query(default=None, ge=0, le=20),
    shop_id: int | None = Query(default=None, ge=1),
    distribution_shop_id: int | None = Query(default=None, ge=1),
    compare_shop_ids: str | None = Query(default=None),
    sales_date_start: str | None = Query(default=None),
    sales_date_end: str | None = Query(default=None),
    has_stock: str | None = Query(default=None),
    catalog_only: bool = Query(default=True),
    sort_field: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    _user: AqcUser = Depends(require_permissions("goods.read")),
    db: Session = Depends(get_db),
):
    conditions = _build_goods_conditions(
        keyword=q or "",
        product_code=product_code,
        brand=brand,
        series=series,
        model=model,
        model_attribute=model_attribute,
        barcode=barcode,
        index_key=index_key,
        putaway=putaway,
        status=status,
        shop_id=shop_id,
        distribution_shop_id=distribution_shop_id,
        price_min=price_min,
        price_max=price_max,
        has_stock=has_stock,
        catalog_only=catalog_only,
    )
    shop_quantity_total_conditions = _build_goods_conditions(
        keyword=q or "",
        product_code=product_code,
        brand=brand,
        series=series,
        model=model,
        model_attribute=model_attribute,
        barcode=barcode,
        index_key=index_key,
        putaway=putaway,
        status=status,
        shop_id=shop_id,
        price_min=price_min,
        price_max=price_max,
        has_stock=None,
        catalog_only=catalog_only,
    )

    stmt = (
        select(AqcGoodsItem)
        .options(
            selectinload(AqcGoodsItem.shop).load_only(AqcShop.id, AqcShop.name),
            selectinload(AqcGoodsItem.creator).load_only(AqcUser.id, AqcUser.display_name),
        )
        .where(*conditions)
    )
    count_stmt = select(func.count(AqcGoodsItem.id)).where(*conditions)
    parsed_sales_start = _parse_sales_date(sales_date_start)
    parsed_sales_end = _parse_sales_date(sales_date_end, end=True)

    order_key = (sort_field or "updated_at").strip().lower()
    sort_column = SORT_FIELD_MAP.get(order_key, AqcGoodsItem.updated_at)
    if order_key == "sales_count":
        sort_column = _sales_quantity_sort_subquery(
            sold_at_start=parsed_sales_start,
            sold_at_end=parsed_sales_end,
        )
    sort_desc = (sort_order or "desc").strip().lower() != "asc"
    order_expr = sort_column.desc() if sort_desc else sort_column.asc()
    tie_breaker = AqcGoodsItem.id.desc() if sort_desc else AqcGoodsItem.id.asc()

    total = db.execute(count_stmt).scalar() or 0
    stock_total = int(
        db.execute(
            select(func.coalesce(func.sum(AqcGoodsItem.stock), 0)).where(*conditions)
        ).scalar()
        or 0
    )
    rows = (
        db.execute(
            stmt.order_by(order_expr, tie_breaker)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    compare_shop_id_list = _parse_compare_shop_ids(compare_shop_ids)
    sales_count_map = _sales_quantity_map(
        db,
        [int(item.id) for item in rows],
        sold_at_start=parsed_sales_start,
        sold_at_end=parsed_sales_end,
    )

    shop_quantity_map = _inventory_quantity_map_for_shop(
        db,
        [int(item.id) for item in rows],
        distribution_shop_id,
    )
    compare_quantity_map = _inventory_quantity_maps_for_shops(
        db,
        [int(item.id) for item in rows],
        compare_shop_id_list,
    )
    compare_sales_map = _sales_quantity_maps_for_shops(
        db,
        [int(item.id) for item in rows],
        compare_shop_id_list,
        sold_at_start=parsed_sales_start,
        sold_at_end=parsed_sales_end,
    ) if compare_shop_id_list else {}

    shop_quantity_total = 0
    shop_amount_total = 0.0
    if distribution_shop_id is not None:
        quantity_conditions = [
            AqcGoodsInventory.shop_id == int(distribution_shop_id),
            *shop_quantity_total_conditions,
        ]
        normalized_has_stock = _normalize_has_stock_filter(has_stock)
        if normalized_has_stock == "zero":
            quantity_conditions.append(AqcGoodsInventory.quantity == 0)
        elif normalized_has_stock == "negative":
            quantity_conditions.append(AqcGoodsInventory.quantity < 0)
        elif normalized_has_stock == "nonzero":
            quantity_conditions.append(AqcGoodsInventory.quantity != 0)
        shop_quantity_total = int(
            db.execute(
                select(func.coalesce(func.sum(AqcGoodsInventory.quantity), 0))
                .select_from(AqcGoodsInventory)
                .join(AqcGoodsItem, AqcGoodsItem.id == AqcGoodsInventory.goods_item_id)
                .where(*quantity_conditions)
            ).scalar()
            or 0
        )
        shop_amount_total = float(
            db.execute(
                select(func.coalesce(func.sum(AqcGoodsInventory.quantity * AqcGoodsItem.price), 0))
                .select_from(AqcGoodsInventory)
                .join(AqcGoodsItem, AqcGoodsItem.id == AqcGoodsInventory.goods_item_id)
                .where(*quantity_conditions)
            ).scalar()
            or 0
        )

    return {
        "success": True,
        "total": int(total),
        "items": [
            _to_goods_summary_out(
                item,
                shop_quantity=shop_quantity_map.get(int(item.id), 0),
                compare_quantities=compare_quantity_map.get(int(item.id), {}),
                sales_count=sales_count_map.get(int(item.id), 0),
                compare_sales_counts=compare_sales_map.get(int(item.id), {}),
            )
            for item in rows
        ],
        "shopQuantityTotal": int(shop_quantity_total),
        "shopAmountTotal": round(shop_amount_total, 2),
        "stockTotal": int(stock_total),
        "salesTotal": int(sum(sales_count_map.get(int(item.id), 0) for item in rows)),
    }


@router.get("/catalog/meta", response_model=GoodsCatalogMetaResponse)
def goods_catalog_meta(
    q: str | None = None,
    product_code: str | None = None,
    brand: str | None = None,
    series: str | None = None,
    model: str | None = None,
    model_attribute: str | None = None,
    barcode: str | None = None,
    index_key: str | None = None,
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    distribution_shop_id: int | None = Query(default=None, ge=1),
    has_stock: str | None = Query(default=None),
    catalog_only: bool = Query(default=True),
    draft_context: bool = Query(default=False),
    _user: AqcUser = Depends(require_permissions("goods.read")),
    db: Session = Depends(get_db),
):
    total_conditions = _build_goods_conditions(
        keyword=q or "",
        product_code=product_code,
        brand=brand,
        series=series,
        model=model,
        model_attribute=model_attribute,
        barcode=barcode,
        index_key=index_key,
        distribution_shop_id=distribution_shop_id,
        price_min=price_min,
        price_max=price_max,
        has_stock=has_stock,
        catalog_only=catalog_only,
    )
    brand_conditions = _build_goods_conditions(
        keyword=q or "",
        product_code=product_code,
        series=series,
        model=model,
        model_attribute=model_attribute,
        barcode=barcode,
        index_key=index_key,
        distribution_shop_id=distribution_shop_id,
        price_min=price_min,
        price_max=price_max,
        has_stock=has_stock,
        catalog_only=catalog_only,
    )
    series_conditions = _build_goods_conditions(
        keyword=q or "",
        product_code=product_code,
        brand=brand,
        model=model,
        model_attribute=model_attribute,
        barcode=barcode,
        index_key=index_key,
        distribution_shop_id=distribution_shop_id,
        price_min=price_min,
        price_max=price_max,
        has_stock=has_stock,
        catalog_only=catalog_only,
    )
    attribute_conditions = _build_goods_conditions(
        keyword=q or "",
        product_code=product_code,
        brand=brand,
        series=series,
        model=model,
        barcode=barcode,
        index_key=index_key,
        distribution_shop_id=distribution_shop_id,
        price_min=price_min,
        price_max=price_max,
        has_stock=has_stock,
        catalog_only=catalog_only,
    )

    total_items = db.execute(select(func.count(AqcGoodsItem.id)).where(*total_conditions)).scalar() or 0
    brand_count = db.execute(
        select(func.count(func.distinct(AqcGoodsItem.brand))).where(
            *[condition for condition in total_conditions if condition is not None],
            AqcGoodsItem.brand != "",
        )
    ).scalar() or 0
    series_count = db.execute(
        select(func.count(func.distinct(AqcGoodsItem.series_name))).where(
            *[condition for condition in total_conditions if condition is not None],
            AqcGoodsItem.series_name != "",
        )
    ).scalar() or 0
    price_row = db.execute(
        select(
            func.coalesce(func.min(AqcGoodsItem.price), 0),
            func.coalesce(func.max(AqcGoodsItem.price), 0),
        ).where(*total_conditions)
    ).one()

    brand_rows = db.execute(
        select(AqcGoodsItem.brand, func.count(AqcGoodsItem.id))
        .where(*brand_conditions, AqcGoodsItem.brand != "")
        .group_by(AqcGoodsItem.brand)
        .order_by(AqcGoodsItem.brand.asc())
        .limit(300)
    ).all()
    series_rows = db.execute(
        select(AqcGoodsItem.series_name, func.count(AqcGoodsItem.id))
        .where(*series_conditions, AqcGoodsItem.series_name != "")
        .group_by(AqcGoodsItem.series_name)
        .order_by(AqcGoodsItem.series_name.asc())
        .limit(400)
    ).all()
    attribute_rows = db.execute(
        select(AqcGoodsItem.model_attribute, func.count(AqcGoodsItem.id))
        .where(*attribute_conditions)
        .group_by(AqcGoodsItem.model_attribute)
        .order_by(AqcGoodsItem.model_attribute.asc())
    ).all()
    index_rows = db.execute(
        select(AqcGoodsItem.index_key, func.count(AqcGoodsItem.id))
        .where(*brand_conditions, AqcGoodsItem.index_key != "")
        .group_by(AqcGoodsItem.index_key)
        .order_by(AqcGoodsItem.index_key.asc())
    ).all()
    return {
        "success": True,
        "totalItems": int(total_items),
        "brandCount": int(brand_count),
        "seriesCount": int(series_count),
        "priceMin": float(price_row[0] or 0),
        "priceMax": float(price_row[1] or 0),
        "nextProductCode": "",
        "brandOptions": [
            GoodsFilterOptionOut(value=str(row[0]), label=str(row[0]), count=int(row[1] or 0))
            for row in brand_rows
        ],
        "seriesOptions": [
            GoodsFilterOptionOut(value=str(row[0]), label=str(row[0]), count=int(row[1] or 0))
            for row in series_rows
        ],
        "attributeOptions": [
            GoodsFilterOptionOut(
                value=normalize_goods_attribute(row[0]),
                label=normalize_goods_attribute(row[0]),
                count=int(row[1] or 0),
            )
            for row in attribute_rows
        ],
        "indexOptions": [
            GoodsIndexOptionOut(key=str(row[0]), count=int(row[1] or 0))
            for row in index_rows
        ],
    }


@router.get("/barcode/{barcode}", response_model=GoodsBarcodeLookupResponse)
def get_goods_item_by_barcode(
    barcode: str,
    catalog_only: bool = Query(default=True),
    _user: AqcUser = Depends(require_permissions("goods.read")),
    db: Session = Depends(get_db),
):
    clean_barcode = _clean_text(barcode, 64)
    if not clean_barcode:
        return {"success": False, "message": "条码不能为空", "item": None}

    stmt = (
        select(AqcGoodsItem)
        .options(
            selectinload(AqcGoodsItem.shop).load_only(AqcShop.id, AqcShop.name),
            selectinload(AqcGoodsItem.creator).load_only(AqcUser.id, AqcUser.display_name),
        )
        .where(AqcGoodsItem.barcode == clean_barcode)
    )
    if catalog_only:
        stmt = stmt.where(CATALOG_READY_CONDITION)

    item = db.execute(stmt.order_by(AqcGoodsItem.id.desc()).limit(1)).scalars().first()
    if item is None:
        return {"success": False, "message": "未找到匹配条码的商品", "item": None}
    return {"success": True, "item": _to_goods_out(item)}


@router.get("/items/{item_id}", response_model=GoodsItemDetailResponse)
def get_goods_item_detail(
    item_id: int,
    _user: AqcUser = Depends(require_permissions("goods.read")),
    db: Session = Depends(get_db),
):
    item = _load_goods_item_detail(db, item_id)
    if item is None:
        return {"success": False, "item": None}
    return {"success": True, "item": _to_goods_out(item)}


@router.get("/items/{item_id}/inventory", response_model=GoodsInventoryResponse)
def get_goods_item_inventory(
    item_id: int,
    _user: AqcUser = Depends(require_permissions("goods.read")),
    db: Session = Depends(get_db),
):
    item = _load_goods_item_detail(db, item_id)
    if item is None:
        return {"success": False, "message": "商品不存在", "item": None, "inventories": [], "totalStock": 0}
    return _build_inventory_response(db, item)


@router.get("/items/{item_id}/inventory-logs", response_model=InventoryLogListResponse)
def list_goods_inventory_logs(
    item_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    shop_id: int | None = Query(default=None, ge=1),
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    _user: AqcUser = Depends(require_permissions("goods.read")),
    db: Session = Depends(get_db),
):
    item = _load_goods_item_detail(db, item_id)
    if item is None:
        return {"success": False, "total": 0, "logs": []}
    total, rows = list_inventory_logs(
        db,
        goods_item_id=int(item_id),
        shop_id=int(shop_id) if shop_id is not None else None,
        keyword=q,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    total_after_map = inventory_log_total_after_map(
        db,
        rows,
        goods_item_id=int(item_id),
        shop_id=int(shop_id) if shop_id is not None else None,
    )
    return {
        "success": True,
        "total": total,
        "currentQuantityTotal": inventory_log_scope_current_total(
            db,
            goods_item_id=int(item_id),
            shop_id=int(shop_id) if shop_id is not None else None,
        ),
        "logs": [_to_inventory_log_out(row, total_quantity_after=total_after_map.get(int(row.id), 0)) for row in rows],
    }


@router.post("/template-import", response_model=GoodsCatalogImportResponse)
async def import_goods_catalog_template(
    request: Request,
    dry_run: bool = Query(default=False),
    x_file_name: str | None = Header(default=None, alias="X-File-Name"),
    user: AqcUser = Depends(require_permissions("goods.write")),
    db: Session = Depends(get_db),
):
    filename = unquote((x_file_name or "").strip()) or "goods-template.xlsx"
    if Path(filename).suffix.lower() != ".xlsx":
        return {"success": False, "message": "仅支持上传 .xlsx 商品表", "stats": {}}

    content = await request.body()
    if not content:
        return {"success": False, "message": "上传内容为空，请重新选择商品表", "stats": {}}

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            tmp_file.write(content)
            temp_path = tmp_file.name

        if dry_run:
            stats, _ = inspect_ngoods_catalog_import(db, temp_path, allow_updates=False)
            has_invalid_rows = bool(stats.get("invalidRows"))
            return {
                "success": not has_invalid_rows,
                "message": _goods_catalog_import_message(stats, dry_run=True),
                "stats": stats,
            }

        stats = import_ngoods_catalog(db, temp_path, allow_updates=False, created_by=user.id)
        db.commit()
        return {
            "success": True,
            "message": _goods_catalog_import_message(stats, dry_run=False),
            "stats": stats,
        }
    except ValueError as exc:
        db.rollback()
        try:
            stats, _ = inspect_ngoods_catalog_import(db, temp_path, allow_updates=False)
        except Exception:
            stats = {}
        return {"success": False, "message": str(exc), "stats": stats}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"商品表导入失败：{exc}", "stats": {}}
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/inventory-import", response_model=GoodsCatalogImportResponse)
async def import_goods_inventory_template(
    request: Request,
    dry_run: bool = Query(default=False),
    x_file_name: str | None = Header(default=None, alias="X-File-Name"),
    user: AqcUser = Depends(require_permissions("goods.write")),
    db: Session = Depends(get_db),
):
    filename = unquote((x_file_name or "").strip()) or "goods-inventory.xls"
    if Path(filename).suffix.lower() != ".xls":
        return {"success": False, "message": "仅支持上传 .xls 库存表", "stats": {}}

    content = await request.body()
    if not content:
        return {"success": False, "message": "上传内容为空，请重新选择库存表", "stats": {}}

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xls") as tmp_file:
            tmp_file.write(content)
            temp_path = tmp_file.name

        if dry_run:
            stats, _ = inspect_inventory_template_import(db, temp_path)
            has_blockers = bool(stats.get("unmatchedShops"))
            return {
                "success": not has_blockers,
                "message": _inventory_template_import_message(stats, dry_run=True),
                "stats": stats,
            }

        stats = import_inventory_template(
            db,
            temp_path,
            operator_id=user.id,
            operator_name=inventory_actor_name(user),
        )
        db.commit()
        return {
            "success": True,
            "message": _inventory_template_import_message(stats, dry_run=False),
            "stats": stats,
        }
    except ValueError as exc:
        db.rollback()
        try:
            stats, _ = inspect_inventory_template_import(db, temp_path)
        except Exception:
            stats = {}
        return {"success": False, "message": str(exc), "stats": stats}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"库存表导入失败：{exc}", "stats": {}}
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/items", response_model=MessageResponse)
def create_goods_item(
    payload: GoodsItemCreateRequest,
    user: AqcUser = Depends(require_permissions("goods.write")),
    db: Session = Depends(get_db),
):
    barcode = _clean_text(payload.barcode, 64)
    clean_model, _ = split_model_attribute(payload.model, payload.modelAttribute)
    conflict_message = _find_identifier_conflict(db, barcode=barcode)
    if conflict_message:
        return {"success": False, "message": conflict_message}
    signature_conflict = _find_signature_conflict(
        db,
        brand=_clean_text(payload.brand, 120),
        series=_clean_text(payload.series, 120),
        model=clean_model,
        model_attribute=payload.modelAttribute or GOODS_ATTRIBUTE_NONE,
        barcode=barcode,
    )
    if signature_conflict:
        return {"success": False, "message": signature_conflict}

    draft_name = compose_goods_name(
        _clean_text(payload.brand, 120),
        _clean_text(payload.series, 120),
        clean_model,
        payload.name,
    )
    if not draft_name.strip():
        return {"success": False, "message": "商品名称不能为空"}

    if payload.shopId is not None:
        exists = db.execute(select(AqcShop.id).where(AqcShop.id == payload.shopId).limit(1)).scalar()
        if exists is None:
            return {"success": False, "message": "关联店铺不存在"}

    quantity_map = _normalize_inventory_quantity_map(payload)
    if quantity_map:
        shops = db.execute(select(AqcShop).where(AqcShop.id.in_(sorted(quantity_map.keys())))).scalars().all()
        shop_id_set = {int(shop.id) for shop in shops}
        missing_ids = [str(shop_id) for shop_id in sorted(quantity_map.keys()) if shop_id not in shop_id_set]
        if missing_ids:
            return {"success": False, "message": f"以下店铺/仓库不存在：{', '.join(missing_ids)}"}

    goods_item = AqcGoodsItem(
        name=draft_name,
        category_id=payload.categoryId,
        cover_image=_clean_text(payload.coverImage, 500),
        image_list=(payload.imageList or "[]").strip(),
        description=(payload.description or "").strip(),
        detail=(payload.detail or "").strip(),
        price=_to_amount(payload.price),
        original_price=_to_amount(payload.originalPrice),
        sale_price=_to_amount(payload.salePrice),
        score=payload.score,
        stock=0,
        sale_num=payload.saleNum,
        sort=payload.sort,
        putaway=payload.putaway,
        status=payload.status,
        goods_type=payload.goodsType,
        remark=_clean_text(payload.remark, 255),
        goodspec=_clean_text(payload.goodspec, 255) or None,
        score_rule=(payload.scoreRule or "").strip(),
        legacy_admin_id=payload.legacyAdminId,
        shop_id=payload.shopId,
        created_by=user.id,
    )
    _apply_payload_to_goods_item(goods_item, payload, overwrite_name=True)
    goods_item.barcode = barcode
    db.add(goods_item)
    db.flush()

    actor_name = inventory_actor_name(user)
    if quantity_map:
        replace_goods_inventory_quantities(
            db,
            goods_item=goods_item,
            quantity_map=quantity_map,
            scope_shop_ids=sorted(quantity_map.keys()),
            change_content="新建商品初始化库存",
            operator_id=user.id,
            operator_name=actor_name,
            related_type="goods_create",
            related_id=int(goods_item.id),
        )
        db.flush()
        recalculate_goods_stock(db, [int(goods_item.id)])
    elif payload.shopId is not None and int(payload.stock or 0) != 0:
        replace_goods_inventory_quantities(
            db,
            goods_item=goods_item,
            quantity_map={int(payload.shopId): int(payload.stock or 0)},
            scope_shop_ids=[int(payload.shopId)],
            change_content="新建商品初始化库存",
            operator_id=user.id,
            operator_name=actor_name,
            related_type="goods_create",
            related_id=int(goods_item.id),
        )
        db.flush()
        recalculate_goods_stock(db, [int(goods_item.id)])

    db.commit()
    return {"success": True, "message": "商品创建成功"}


@router.put("/items/{item_id}", response_model=MessageResponse)
def update_goods_item(
    item_id: int,
    payload: GoodsItemUpdateRequest,
    _user: AqcUser = Depends(require_permissions("goods.write")),
    db: Session = Depends(get_db),
):
    goods_item = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == item_id).limit(1)).scalars().first()
    if goods_item is None:
        return {"success": False, "message": "商品不存在"}

    if payload.shopId is not None:
        exists = db.execute(select(AqcShop.id).where(AqcShop.id == payload.shopId).limit(1)).scalar()
        if exists is None:
            return {"success": False, "message": "关联店铺不存在"}
        goods_item.shop_id = payload.shopId

    next_barcode = (
        _clean_text(payload.barcode, 64)
        if payload.barcode is not None
        else goods_item.barcode or ""
    )
    conflict_message = _find_identifier_conflict(
        db,
        barcode=next_barcode,
        exclude_item_id=goods_item.id,
    )
    if conflict_message:
        return {"success": False, "message": conflict_message}
    next_brand = _clean_text(payload.brand, 120) if payload.brand is not None else goods_item.brand or ""
    next_series = _clean_text(payload.series, 120) if payload.series is not None else goods_item.series_name or ""
    next_model_raw = payload.model if payload.model is not None else goods_item.model_name or ""
    next_model_attribute_raw = payload.modelAttribute if payload.modelAttribute is not None else goods_item.model_attribute or GOODS_ATTRIBUTE_NONE
    next_model, next_model_attribute = split_model_attribute(next_model_raw, next_model_attribute_raw)
    signature_conflict = _find_signature_conflict(
        db,
        brand=next_brand,
        series=next_series,
        model=next_model,
        model_attribute=next_model_attribute,
        barcode=next_barcode,
        exclude_item_id=goods_item.id,
    )
    if signature_conflict:
        return {"success": False, "message": signature_conflict}

    overwrite_name = any(
        value is not None
        for value in (
            payload.brand,
            payload.series,
            payload.model,
            payload.modelAttribute,
            payload.indexKey,
        )
    )
    _apply_payload_to_goods_item(goods_item, payload, overwrite_name=overwrite_name)

    if not (goods_item.name or "").strip():
        return {"success": False, "message": "商品名称不能为空"}

    db.commit()
    return {"success": True, "message": "商品更新成功"}


@router.put("/items/{item_id}/inventory", response_model=GoodsInventoryResponse)
def update_goods_item_inventory(
    item_id: int,
    payload: GoodsInventoryUpdateRequest,
    user: AqcUser = Depends(require_permissions("goods.write")),
    db: Session = Depends(get_db),
):
    item = _load_goods_item_detail(db, item_id)
    if item is None:
        return {"success": False, "message": "商品不存在", "item": None, "inventories": [], "totalStock": 0}

    quantity_map = _normalize_inventory_quantity_map(payload)
    if quantity_map:
        shops = db.execute(select(AqcShop).where(AqcShop.id.in_(sorted(quantity_map.keys())))).scalars().all()
        shop_id_set = {int(shop.id) for shop in shops}
        missing_ids = [str(shop_id) for shop_id in sorted(quantity_map.keys()) if shop_id not in shop_id_set]
        if missing_ids:
            return {
                "success": False,
                "message": f"以下店铺/仓库不存在：{', '.join(missing_ids)}",
                "item": _to_goods_summary_out(item),
                "inventories": _load_inventory_rows(db, int(item.id)),
                "totalStock": int(item.stock or 0),
            }

    replace_goods_inventory_quantities(
        db,
        goods_item=item,
        quantity_map=quantity_map,
        scope_shop_ids=sorted(quantity_map.keys()),
        change_content="手动调整商品库存",
        operator_id=user.id,
        operator_name=inventory_actor_name(user),
        related_type="goods_manual",
        related_id=int(item.id),
    )
    db.flush()
    recalculate_goods_stock(db, [int(item.id)])
    db.commit()

    refreshed_item = _load_goods_item_detail(db, item_id)
    if refreshed_item is None:
        return {"success": False, "message": "商品不存在", "item": None, "inventories": [], "totalStock": 0}
    return _build_inventory_response(db, refreshed_item, message="商品数量已更新")


@router.delete("/items/{item_id}", response_model=MessageResponse)
def delete_goods_item(
    item_id: int,
    _user: AqcUser = Depends(require_permissions("goods.manage")),
    db: Session = Depends(get_db),
):
    goods_item = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == item_id).limit(1)).scalars().first()
    if goods_item is None:
        return {"success": False, "message": "商品不存在"}

    db.delete(goods_item)
    db.commit()
    return {"success": True, "message": "商品已删除"}

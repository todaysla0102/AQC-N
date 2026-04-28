from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import or_, select

from ..database import SessionLocal, init_db
from ..inventory import append_inventory_log, normalize_shop_name, recalculate_goods_stock
from ..models import AqcGoodsInventory, AqcGoodsItem, AqcSaleRecord, AqcShop


def _clean_text(value: str | None, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def _parse_decimal(value: str | None) -> Decimal:
    try:
        return Decimal(str(value or "0").strip() or "0").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _parse_int(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text or text.upper() == "NULL":
        return None
    try:
        return int(text)
    except Exception:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text or text.upper() == "NULL":
        return None
    try:
        return datetime.fromisoformat(text.replace("T", " "))
    except Exception:
        return None


def _resolve_shop(db, *, target_shop_id: int | None, target_shop_name: str | None) -> AqcShop:
    if target_shop_id is not None:
        shop = db.execute(select(AqcShop).where(AqcShop.id == target_shop_id).limit(1)).scalars().first()
        if shop is not None:
            return shop
    _, normalized_name = normalize_shop_name(target_shop_name)
    if normalized_name:
        shop = db.execute(select(AqcShop).where(AqcShop.name == normalized_name).limit(1)).scalars().first()
        if shop is not None:
            return shop
    raise ValueError("未找到目标店铺")


def _resolve_optional_shop(db, *, shop_id: int | None, shop_name: str | None) -> AqcShop | None:
    if shop_id is not None:
        shop = db.execute(select(AqcShop).where(AqcShop.id == int(shop_id)).limit(1)).scalars().first()
        if shop is not None:
            return shop
    _, normalized_name = normalize_shop_name(shop_name)
    if normalized_name:
        return db.execute(select(AqcShop).where(AqcShop.name == normalized_name).limit(1)).scalars().first()
    return None


def _resolve_goods(db, row: dict[str, str]) -> AqcGoodsItem | None:
    goods_id = _parse_int(row.get("goods_id"))
    if goods_id is not None:
        goods = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == goods_id).limit(1)).scalars().first()
        if goods is not None:
            return goods
    barcode = _clean_text(row.get("goods_barcode"), 64)
    model = _clean_text(row.get("goods_model"), 191)
    brand = _clean_text(row.get("goods_brand"), 120)
    series = _clean_text(row.get("goods_series"), 120)
    if barcode:
        goods = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.barcode == barcode).limit(1)).scalars().first()
        if goods is not None:
            return goods
    if model:
        goods = (
            db.execute(
                select(AqcGoodsItem).where(
                    AqcGoodsItem.model_name == model,
                    AqcGoodsItem.brand == brand,
                    AqcGoodsItem.series_name == series,
                ).limit(1)
            )
            .scalars()
            .first()
        )
        if goods is not None:
            return goods
        return db.execute(select(AqcGoodsItem).where(AqcGoodsItem.model_name == model).limit(1)).scalars().first()
    return None


def _record_exists(db, *, row: dict[str, str], shop: AqcShop, salesperson: str) -> bool:
    sold_at = _parse_datetime(row.get("sold_at"))
    if sold_at is None:
        return False
    order_num = _clean_text(row.get("order_num"), 32)
    goods_barcode = _clean_text(row.get("goods_barcode"), 64)
    goods_model = _clean_text(row.get("goods_model"), 191)
    amount = _parse_decimal(row.get("amount"))
    conditions = [
        AqcSaleRecord.sold_at == sold_at,
        AqcSaleRecord.order_num == order_num,
        AqcSaleRecord.amount == amount,
        AqcSaleRecord.shop_id == int(shop.id),
        AqcSaleRecord.salesperson == salesperson,
    ]
    if goods_barcode:
        conditions.append(AqcSaleRecord.goods_barcode == goods_barcode)
    elif goods_model:
        conditions.append(AqcSaleRecord.goods_model == goods_model)
    return db.execute(select(AqcSaleRecord.id).where(*conditions).limit(1)).scalar() is not None


def _get_inventory_row(db, *, goods_item_id: int, shop_id: int) -> AqcGoodsInventory | None:
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


def restore_rows(
    *,
    tsv_path: str | Path,
    date_prefix: str,
    source_shop_name: str | None,
    target_shop_id: int | None,
    target_shop_name: str | None,
    target_salesperson: str,
    dry_run: bool,
    apply_inventory: bool,
) -> dict[str, object]:
    path = Path(tsv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"备份文件不存在: {path}")

    rows = list(csv.DictReader(path.open("r", encoding="utf-8"), delimiter="\t"))
    filtered_rows = [
        row
        for row in rows
        if (not source_shop_name or _clean_text(row.get("shop_name"), 255) == source_shop_name)
        and str(row.get("sold_at") or "").startswith(date_prefix)
    ]

    db = SessionLocal()
    try:
        shop = _resolve_shop(db, target_shop_id=target_shop_id, target_shop_name=target_shop_name or source_shop_name)
        touched_goods_ids: set[int] = set()
        restored_orders: list[str] = []
        skipped_orders: list[str] = []
        missing_goods: list[str] = []
        restored_amount = Decimal("0.00")
        inventory_rows: dict[tuple[int, int], AqcGoodsInventory] = {}

        for row in filtered_rows:
            goods = _resolve_goods(db, row)
            if goods is None:
                missing_goods.append(_clean_text(row.get("order_num"), 32))
                continue
            if _record_exists(db, row=row, shop=shop, salesperson=target_salesperson):
                skipped_orders.append(_clean_text(row.get("order_num"), 32))
                continue

            sold_at = _parse_datetime(row.get("sold_at"))
            created_at = _parse_datetime(row.get("created_at"))
            updated_at = _parse_datetime(row.get("updated_at"))
            quantity = int(_parse_int(row.get("quantity")) or 0)
            if sold_at is None or quantity <= 0:
                skipped_orders.append(_clean_text(row.get("order_num"), 32))
                continue

            original_salesperson = _clean_text(row.get("salesperson"), 80)
            note_parts = [_clean_text(row.get("note"), 5000)]
            note_parts.append(f"恢复备份:{path.name}")
            if original_salesperson and original_salesperson != target_salesperson:
                note_parts.append(f"原销售员:{original_salesperson}")
            ship_shop = _resolve_optional_shop(
                db,
                shop_id=_parse_int(row.get("ship_shop_id")),
                shop_name=_clean_text(row.get("ship_shop_name"), 255),
            ) or shop

            record = AqcSaleRecord(
                sold_at=sold_at,
                order_num=_clean_text(row.get("order_num"), 32),
                goods_id=int(goods.id),
                goods_code=_clean_text(row.get("goods_code"), 64) or _clean_text(goods.product_code, 64),
                goods_brand=_clean_text(row.get("goods_brand"), 120),
                goods_series=_clean_text(row.get("goods_series"), 120),
                goods_model=_clean_text(row.get("goods_model"), 191),
                goods_barcode=_clean_text(row.get("goods_barcode"), 64) or _clean_text(goods.barcode, 64),
                unit_price=_parse_decimal(row.get("unit_price")),
                receivable_amount=_parse_decimal(row.get("receivable_amount")),
                amount=_parse_decimal(row.get("amount")),
                coupon_amount=_parse_decimal(row.get("coupon_amount")),
                discount_rate=_parse_decimal(row.get("discount_rate")),
                quantity=quantity,
                channel=_clean_text(row.get("channel"), 50),
                shop_id=int(shop.id),
                shop_name=_clean_text(shop.name, 255),
                ship_shop_id=int(ship_shop.id),
                ship_shop_name=_clean_text(ship_shop.name, 255),
                salesperson=target_salesperson,
                index_key=_clean_text(row.get("index_key"), 8),
                customer_name=_clean_text(row.get("customer_name"), 120),
                note=";".join(part for part in note_parts if part)[:5000],
                created_by=_parse_int(row.get("created_by")),
                created_at=created_at or sold_at,
                updated_at=updated_at or sold_at,
                sale_status=_clean_text(row.get("sale_status"), 20) or "normal",
                source_sale_record_id=_parse_int(row.get("source_sale_record_id")),
                related_work_order_id=_parse_int(row.get("related_work_order_id")),
                returned_at=_parse_datetime(row.get("returned_at")),
            )
            db.add(record)
            if apply_inventory:
                inventory_key = (int(goods.id), int(ship_shop.id))
                inventory_row = inventory_rows.get(inventory_key)
                if inventory_row is None:
                    inventory_row = _get_inventory_row(db, goods_item_id=int(goods.id), shop_id=int(ship_shop.id))
                    if inventory_row is None:
                        inventory_row = AqcGoodsInventory(goods_item_id=int(goods.id), shop_id=int(ship_shop.id), quantity=0)
                        db.add(inventory_row)
                    inventory_rows[inventory_key] = inventory_row
                before_quantity = int(inventory_row.quantity or 0)
                after_quantity = before_quantity - quantity
                inventory_row.quantity = after_quantity
                append_inventory_log(
                    db,
                    goods_item=goods,
                    shop=ship_shop,
                    quantity_before=before_quantity,
                    quantity_after=after_quantity,
                    change_content=f"销售恢复扣减：订单 {record.order_num}",
                    operator_id=_parse_int(row.get("created_by")),
                    operator_name=target_salesperson,
                    related_type="sale_restore",
                )
                touched_goods_ids.add(int(goods.id))
            restored_orders.append(record.order_num)
            restored_amount += record.amount

        if dry_run:
            db.rollback()
        else:
            db.flush()
            if touched_goods_ids:
                recalculate_goods_stock(db, sorted(touched_goods_ids))
            db.commit()

        return {
            "success": True,
            "dryRun": dry_run,
            "path": str(path),
            "sourceShopName": source_shop_name or "",
            "targetShopName": _clean_text(shop.name, 255),
            "targetSalesperson": target_salesperson,
            "matchedRows": len(filtered_rows),
            "restoredCount": len(restored_orders),
            "restoredOrders": restored_orders,
            "restoredAmount": float(restored_amount),
            "skippedCount": len(skipped_orders),
            "skippedOrders": skipped_orders,
            "missingGoods": missing_goods,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 TSV 备份恢复误删销售记录")
    parser.add_argument("tsv_path")
    parser.add_argument("--date-prefix", required=True)
    parser.add_argument("--source-shop-name", default=None)
    parser.add_argument("--target-salesperson", required=True)
    parser.add_argument("--target-shop-id", type=int, default=None)
    parser.add_argument("--target-shop-name", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply-inventory", action="store_true")
    args = parser.parse_args(argv)

    init_db()
    try:
        result = restore_rows(
            tsv_path=args.tsv_path,
            date_prefix=args.date_prefix,
            source_shop_name=args.source_shop_name,
            target_shop_id=args.target_shop_id,
            target_shop_name=args.target_shop_name,
            target_salesperson=args.target_salesperson,
            dry_run=args.dry_run,
            apply_inventory=args.apply_inventory,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

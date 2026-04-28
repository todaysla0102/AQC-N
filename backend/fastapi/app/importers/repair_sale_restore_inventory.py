from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select

from ..database import SessionLocal, init_db
from ..inventory import append_inventory_log, recalculate_goods_stock
from ..models import AqcGoodsInventory, AqcGoodsItem, AqcInventoryLog, AqcShop

ORDER_NUM_PATTERN = re.compile(r"订单\s+([A-Za-z0-9]+)")


def _extract_order_num(change_content: str) -> str:
    matched = ORDER_NUM_PATTERN.search(str(change_content or ""))
    return matched.group(1) if matched else ""


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


def repair_sale_restore_inventory(*, dry_run: bool = False) -> dict[str, object]:
    db = SessionLocal()
    try:
        bad_logs = (
            db.execute(
                select(AqcInventoryLog)
                .where(
                    AqcInventoryLog.related_type == "sale_restore",
                    AqcInventoryLog.related_id.is_(None),
                    AqcInventoryLog.change_content.like("销售恢复扣减：订单 %"),
                )
                .order_by(AqcInventoryLog.id.asc())
            )
            .scalars()
            .all()
        )
        repaired_orders: list[str] = []
        removed_log_ids: list[int] = []
        touched_goods_ids: set[int] = set()
        restored_units = 0

        for log in bad_logs:
            goods_id = int(log.goods_item_id or 0)
            shop_id = int(log.shop_id or 0)
            delta = int(log.quantity_before or 0) - int(log.quantity_after or 0)
            if goods_id <= 0 or shop_id <= 0 or delta <= 0:
                continue
            goods = db.execute(select(AqcGoodsItem).where(AqcGoodsItem.id == goods_id).limit(1)).scalars().first()
            shop = db.execute(select(AqcShop).where(AqcShop.id == shop_id).limit(1)).scalars().first()
            if goods is None or shop is None:
                continue
            inventory_row = _get_inventory_row(db, goods_item_id=goods_id, shop_id=shop_id)
            if inventory_row is None:
                inventory_row = AqcGoodsInventory(goods_item_id=goods_id, shop_id=shop_id, quantity=0)
                db.add(inventory_row)
                db.flush()
            before_quantity = int(inventory_row.quantity or 0)
            after_quantity = before_quantity + delta
            inventory_row.quantity = after_quantity
            order_num = _extract_order_num(log.change_content)
            append_inventory_log(
                db,
                goods_item=goods,
                shop=shop,
                quantity_before=before_quantity,
                quantity_after=after_quantity,
                change_content=f"销售恢复回补：订单 {order_num}" if order_num else "销售恢复回补",
                operator_id=log.operator_id,
                operator_name=log.operator_name,
                related_type="sale_restore_fix",
            )
            touched_goods_ids.add(goods_id)
            restored_units += delta
            repaired_orders.append(order_num or f"log-{log.id}")
            removed_log_ids.append(int(log.id))
            db.delete(log)

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
            "matchedLogs": len(bad_logs),
            "removedLogIds": removed_log_ids,
            "repairedOrders": repaired_orders,
            "restoredUnits": restored_units,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="修复误执行的销售恢复库存扣减日志")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    init_db()
    try:
        result = repair_sale_restore_inventory(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

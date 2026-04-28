from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import xlrd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal, init_db
from ..goods_attributes import split_model_attribute
from ..inventory import recalculate_goods_stock, replace_goods_inventory_quantities
from ..models import AqcGoodsItem, AqcShop, AqcUser


IGNORED_HEADERS = {"", "行号", "商品全名", "基本单位"}


def _clean_text(value: str | None, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def _to_int(raw: object, default: int = 0) -> int:
    try:
        return int(float(str(raw or "").strip() or str(default)))
    except Exception:
        return default


def _find_header_row(sheet: xlrd.sheet.Sheet) -> tuple[int, list[str]]:
    for row_index in range(sheet.nrows):
        headers = [_clean_text(sheet.cell_value(row_index, col_index), 255) for col_index in range(sheet.ncols)]
        if "商品全名" in headers:
            return row_index, headers
    raise ValueError("库存表中未找到“商品全名”表头")


def _serialize_issue_entry(*, file_name: str, model: str, total_quantity: int, nonzero_locations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "file": file_name,
        "model": model,
        "totalQuantity": int(total_quantity),
        "locations": nonzero_locations,
    }


def inspect_inventory_template_import(
    db: Session,
    xls_path: str | Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = Path(xls_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"库存表不存在: {path}")
    if path.suffix.lower() != ".xls":
        raise ValueError("库存表仅支持 .xls 格式")

    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_index(0)
    header_row_index, headers = _find_header_row(sheet)
    goods_col_index = headers.index("商品全名")

    header_indices_by_name: dict[str, list[int]] = {}
    header_issues: dict[str, int] = {}
    for col_index, header_name in enumerate(headers):
        clean_header = _clean_text(header_name, 255)
        if col_index <= goods_col_index or clean_header in IGNORED_HEADERS:
            continue
        header_indices_by_name.setdefault(clean_header, []).append(col_index)
    for header_name, indices in header_indices_by_name.items():
        if len(indices) > 1:
            header_issues[header_name] = len(indices)

    shops = db.execute(select(AqcShop)).scalars().all()
    shop_by_name = {
        _clean_text(item.name, 255): item
        for item in shops
        if _clean_text(item.name, 255)
    }

    goods_items = db.execute(select(AqcGoodsItem)).scalars().all()
    goods_by_model: dict[str, list[AqcGoodsItem]] = {}
    for item in goods_items:
        model_name = _clean_text(item.model_name, 191)
        if not model_name:
            continue
        goods_by_model.setdefault(model_name, []).append(item)

    creator = (
        db.execute(select(AqcUser).where(AqcUser.username == "admin").limit(1)).scalars().first()
        or db.execute(select(AqcUser).order_by(AqcUser.id.asc()).limit(1)).scalars().first()
    )
    creator_id = creator.id if creator else None
    creator_name = _clean_text(creator.display_name or creator.username if creator else "", 80)

    report: dict[str, Any] = {
        "path": str(path),
        "file": path.name,
        "totalRows": max(sheet.nrows - header_row_index - 1, 0),
        "rowsReady": 0,
        "matchedGoods": 0,
        "matchedShops": 0,
        "updatedGoods": 0,
        "changedEntries": 0,
        "skippedRows": 0,
        "headerIssues": header_issues,
        "unmatchedGoods": [],
        "unmatchedZeroGoods": [],
        "ambiguousGoods": [],
        "unmatchedShops": [],
        "shopColumns": sorted(header_indices_by_name.keys()),
    }
    prepared_rows: list[dict[str, Any]] = []

    unmatched_shop_names = [name for name in header_indices_by_name if name not in shop_by_name]
    if unmatched_shop_names:
        report["unmatchedShops"] = unmatched_shop_names
        return report, prepared_rows
    report["matchedShops"] = len(header_indices_by_name)

    for row_index in range(header_row_index + 1, sheet.nrows):
        model_name, _ = split_model_attribute(sheet.cell_value(row_index, goods_col_index))
        if not model_name:
            report["skippedRows"] += 1
            continue

        quantity_map: dict[int, int] = {}
        nonzero_locations: list[dict[str, Any]] = []
        total_quantity = 0
        for header_name, column_indices in header_indices_by_name.items():
            shop = shop_by_name.get(header_name)
            if shop is None:
                continue
            quantity = sum(_to_int(sheet.cell_value(row_index, column_index), 0) for column_index in column_indices)
            quantity_map[int(shop.id)] = int(quantity)
            total_quantity += int(quantity)
            if int(quantity) != 0:
                nonzero_locations.append({"shopName": header_name, "quantity": int(quantity)})

        matched_goods = goods_by_model.get(model_name, [])
        if not matched_goods:
            issue_item = _serialize_issue_entry(
                file_name=path.name,
                model=model_name,
                total_quantity=total_quantity,
                nonzero_locations=nonzero_locations,
            )
            if nonzero_locations:
                report["unmatchedGoods"].append(issue_item)
            else:
                report["unmatchedZeroGoods"].append(issue_item)
            continue

        if len(matched_goods) > 1:
            report["ambiguousGoods"].append(
                {
                    "file": path.name,
                    "model": model_name,
                    "goodsIds": [int(item.id) for item in matched_goods],
                    "totalQuantity": int(total_quantity),
                    "locations": nonzero_locations,
                }
            )
            continue

        goods_item = matched_goods[0]
        prepared_rows.append(
            {
                "file": path.name,
                "goods_item": goods_item,
                "quantity_map": quantity_map,
                "scope_shop_ids": sorted(quantity_map.keys()),
                "operator_id": creator_id,
                "operator_name": creator_name,
            }
        )
        report["matchedGoods"] += 1
        report["rowsReady"] += 1

    return report, prepared_rows


def import_inventory_template(
    db: Session,
    xls_path: str | Path,
    *,
    operator_id: int | None = None,
    operator_name: str | None = None,
) -> dict[str, Any]:
    report, prepared_rows = inspect_inventory_template_import(db, xls_path)

    changed_entries = 0
    touched_goods_ids: set[int] = set()
    for item in prepared_rows:
        goods_item = item["goods_item"]
        changed_entries += replace_goods_inventory_quantities(
            db,
            goods_item=goods_item,
            quantity_map=item["quantity_map"],
            scope_shop_ids=item["scope_shop_ids"],
            change_content=f"库存表导入：{item['file']}",
            operator_id=operator_id if operator_id is not None else item["operator_id"],
            operator_name=operator_name or item["operator_name"],
            related_type="inventory_import",
        )
        touched_goods_ids.add(int(goods_item.id))

    if touched_goods_ids:
        db.flush()
        recalculate_goods_stock(db, sorted(touched_goods_ids))

    report["updatedGoods"] = len(prepared_rows)
    report["changedEntries"] = changed_entries
    report["skippedRiskGoods"] = len(report.get("unmatchedGoods") or []) + len(report.get("ambiguousGoods") or [])
    return report


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv
    if len(args) < 2:
        print("Usage: python -m app.importers.inventory_template_import <xls_path>", file=sys.stderr)
        return 1

    init_db()
    db = SessionLocal()
    try:
        stats = import_inventory_template(db, args[1])
        db.commit()
        print(json.dumps({"success": True, "stats": stats}, ensure_ascii=False))
        return 0
    except Exception as exc:
        db.rollback()
        print(json.dumps({"success": False, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal, init_db
from ..goods_attributes import compose_goods_name, split_model_attribute
from ..models import AqcGoodsItem


XML_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REQUIRED_HEADERS = ["品牌", "系列", "型号", "价格", "条码"]


def _clean_text(value: str | None, max_length: int) -> str:
    return (value or "").strip()[:max_length]


def _normalize_index_key(brand: str, series: str, model: str, product_code: str) -> str:
    seed = product_code or brand or series or model
    for ch in seed:
        if ch.isascii() and ch.isalnum():
            return ch.upper()
        if ch.isdigit():
            return ch
    return "#"


def _to_decimal(raw: str | None) -> Decimal:
    try:
        return Decimal(str(raw or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _to_int(raw: str | None, default: int = 0) -> int:
    try:
        return int(str(raw or "").strip())
    except Exception:
        return default


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return max(index - 1, 0)


def _load_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("main:si", XML_NS):
        parts = [node.text or "" for node in item.findall(".//main:t", XML_NS)]
        values.append("".join(parts))
    return values


def _resolve_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find("main:sheets/main:sheet", XML_NS)
    if first_sheet is None:
        raise ValueError("Excel 中未找到工作表")
    relationship_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for rel in rel_root:
        if rel.attrib.get("Id") == relationship_id:
            target = rel.attrib.get("Target", "").lstrip("/")
            if target.startswith("xl/"):
                return target
            return f"xl/{target}"
    raise ValueError("Excel 工作表关系解析失败")


def _read_catalog_rows(xlsx_path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings = _load_shared_strings(archive)
        sheet_path = _resolve_sheet_path(archive)
        root = ET.fromstring(archive.read(sheet_path))

    rows: list[dict[str, str]] = []
    headers: list[str] = []

    for row in root.findall(".//main:sheetData/main:row", XML_NS):
        cell_map: dict[int, str] = {}
        for cell in row.findall("main:c", XML_NS):
            index = _column_index(cell.attrib.get("r", "A1"))
            cell_type = cell.attrib.get("t")
            value = ""
            if cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//main:t", XML_NS))
            else:
                raw_value = cell.findtext("main:v", default="", namespaces=XML_NS)
                if cell_type == "s":
                    try:
                        value = shared_strings[int(raw_value)]
                    except Exception:
                        value = ""
                else:
                    value = raw_value or ""
            cell_map[index] = value.strip()

        if not cell_map:
            continue

        max_index = max(cell_map.keys())
        ordered_values = [cell_map.get(idx, "").strip() for idx in range(max_index + 1)]
        if not headers:
            headers = ordered_values
            continue

        row_data = {headers[idx]: ordered_values[idx] if idx < len(ordered_values) else "" for idx in range(len(headers))}
        rows.append(row_data)

    missing_headers = [header for header in REQUIRED_HEADERS if header not in headers]
    if missing_headers:
        raise ValueError(f"商品表缺少必要列: {', '.join(missing_headers)}")
    return rows


def _goods_signature(brand: str, series: str, model: str) -> tuple[str, str, str] | None:
    clean_brand = _clean_text(brand, 120)
    clean_series = _clean_text(series, 120)
    clean_model = _clean_text(model, 191)
    if not clean_model:
        return None
    return clean_brand, clean_series, clean_model


def _next_product_code(used_codes: set[str], current_max_code: int) -> tuple[str, int]:
    next_code = current_max_code
    while True:
        next_code += 1
        candidate = str(next_code)
        if candidate not in used_codes:
            used_codes.add(candidate)
            return candidate, next_code


def _identity_keys(product_code: str, barcode: str, signature: tuple[str, str, str] | None) -> list[tuple]:
    keys: list[tuple] = []
    if product_code:
        keys.append(("code", product_code))
    if barcode:
        keys.append(("barcode", barcode))
    if signature is not None:
        keys.append(("signature", *signature))
    return keys


def inspect_ngoods_catalog_import(
    db: Session,
    xlsx_path: str | Path,
    *,
    allow_updates: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = Path(xlsx_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"商品表不存在: {path}")

    rows = _read_catalog_rows(path)
    existing_items = db.execute(select(AqcGoodsItem).order_by(AqcGoodsItem.id.asc())).scalars().all()
    by_code = {_clean_text(item.product_code, 64): item for item in existing_items if _clean_text(item.product_code, 64)}
    by_barcode = {_clean_text(item.barcode, 64): item for item in existing_items if _clean_text(item.barcode, 64)}
    by_signature: dict[tuple[str, str, str], AqcGoodsItem] = {}
    used_codes = set(by_code.keys())
    max_numeric_code = 0

    for item in existing_items:
        signature = _goods_signature(item.brand or "", item.series_name or "", item.model_name or "")
        if signature is not None and signature not in by_signature:
            by_signature[signature] = item
        product_code = _clean_text(item.product_code, 64)
        if product_code.isdigit():
            max_numeric_code = max(max_numeric_code, int(product_code))

    report: dict[str, Any] = {
        "path": str(path),
        "file": path.name,
        "totalRows": len(rows),
        "rowsReady": 0,
        "createdCandidates": 0,
        "updateCandidates": 0,
        "created": 0,
        "updated": 0,
        "duplicates": 0,
        "skipped": 0,
        "generatedCodes": 0,
        "invalidRows": [],
        "duplicateItems": [],
    }
    prepared_rows: list[dict[str, Any]] = []
    seen_upload_keys: set[tuple] = set()

    for row_index, row in enumerate(rows, start=2):
        brand = _clean_text(row.get("品牌"), 120)
        series = _clean_text(row.get("系列"), 120)
        model, model_attribute = split_model_attribute(row.get("型号"))
        barcode = _clean_text(row.get("条码"), 64)
        product_code = _clean_text(row.get("编号"), 64)
        price = _to_decimal(row.get("价格"))

        if not any([brand, series, model, barcode, product_code]):
            report["skipped"] += 1
            continue
        if not model:
            report["invalidRows"].append({"row": row_index, "message": "缺少型号", "barcode": barcode, "productCode": product_code})
            continue

        signature = _goods_signature(brand, series, model)
        identity_keys = _identity_keys(product_code, barcode, signature)
        if identity_keys and any(key in seen_upload_keys for key in identity_keys):
            report["duplicates"] += 1
            report["duplicateItems"].append(
                {
                    "row": row_index,
                    "reason": "表内重复",
                    "brand": brand,
                    "series": series,
                    "model": model,
                    "barcode": barcode,
                    "productCode": product_code,
                }
            )
            continue

        matched_item = None
        duplicate_reason = ""
        if product_code and product_code in by_code:
            matched_item = by_code[product_code]
            duplicate_reason = "编号重复"
        elif barcode and barcode in by_barcode:
            matched_item = by_barcode[barcode]
            duplicate_reason = "条码重复"
        elif signature is not None and signature in by_signature:
            matched_item = by_signature[signature]
            duplicate_reason = "商品型号重复"

        if matched_item is not None and not allow_updates:
            report["duplicates"] += 1
            report["duplicateItems"].append(
                {
                    "row": row_index,
                    "reason": duplicate_reason,
                    "brand": brand,
                    "series": series,
                    "model": model,
                    "modelAttribute": model_attribute,
                    "barcode": barcode,
                    "productCode": _clean_text(matched_item.product_code, 64),
                    "existingBarcode": _clean_text(matched_item.barcode, 64),
                }
            )
            for key in identity_keys:
                seen_upload_keys.add(key)
            continue

        assigned_product_code = product_code
        if matched_item is not None:
            assigned_product_code = product_code or _clean_text(matched_item.product_code, 64)
            if not assigned_product_code:
                assigned_product_code, max_numeric_code = _next_product_code(used_codes, max_numeric_code)
                report["generatedCodes"] += 1
            report["updateCandidates"] += 1
        else:
            if assigned_product_code:
                if assigned_product_code in used_codes:
                    report["invalidRows"].append(
                        {
                            "row": row_index,
                            "message": "商品编号重复且无法自动处理",
                            "brand": brand,
                            "series": series,
                            "model": model,
                            "productCode": assigned_product_code,
                        }
                    )
                    continue
                used_codes.add(assigned_product_code)
            else:
                assigned_product_code, max_numeric_code = _next_product_code(used_codes, max_numeric_code)
                report["generatedCodes"] += 1
            report["createdCandidates"] += 1

        prepared_rows.append(
            {
                "action": "update" if matched_item is not None else "create",
                "goods_item": matched_item,
                "brand": brand,
                "series": series,
                "model": model,
                "modelAttribute": model_attribute,
                "barcode": barcode,
                "productCode": assigned_product_code,
                "price": price,
            }
        )
        report["rowsReady"] += 1
        for key in _identity_keys(assigned_product_code, barcode, signature):
            seen_upload_keys.add(key)

    return report, prepared_rows


def import_ngoods_catalog(
    db: Session,
    xlsx_path: str | Path,
    *,
    allow_updates: bool = True,
    created_by: int | None = None,
) -> dict[str, int | str | list[dict[str, Any]]]:
    report, prepared_rows = inspect_ngoods_catalog_import(db, xlsx_path, allow_updates=allow_updates)
    if report["invalidRows"]:
        raise ValueError("商品表存在无效行，已中止导入")

    created = 0
    updated = 0

    for item in prepared_rows:
        goods_item = item["goods_item"]
        if goods_item is None:
            goods_item = AqcGoodsItem(
                name=compose_goods_name(item["brand"], item["series"], item["model"]),
                created_by=created_by,
            )
            db.add(goods_item)
            created += 1
        else:
            updated += 1

        goods_item.name = compose_goods_name(item["brand"], item["series"], item["model"])
        goods_item.product_code = item["productCode"]
        goods_item.brand = item["brand"]
        goods_item.series_name = item["series"]
        goods_item.model_name = item["model"]
        goods_item.model_attribute = item["modelAttribute"]
        goods_item.barcode = item["barcode"]
        goods_item.index_key = _normalize_index_key(item["brand"], item["series"], item["model"], item["productCode"])
        goods_item.price = item["price"]
        goods_item.original_price = item["price"]
        goods_item.sale_price = item["price"]
        goods_item.sort = _to_int(item["productCode"], 0)
        goods_item.putaway = 1 if int(goods_item.putaway or 0) != 2 else 2
        goods_item.status = int(goods_item.status or 3) or 3
        goods_item.goodspec = goods_item.goodspec or item["series"] or None

    db.flush()
    report["created"] = created
    report["updated"] = updated
    report["imported"] = created + updated
    return report


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv
    if len(args) < 2:
        print("Usage: python -m app.importers.ngoods_import <xlsx_path>", file=sys.stderr)
        return 1

    init_db()
    db = SessionLocal()
    try:
        stats = import_ngoods_catalog(db, args[1])
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

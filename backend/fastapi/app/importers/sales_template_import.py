from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal, init_db
from ..inventory import apply_inventory_delta, normalize_shop_name, recalculate_goods_stock
from ..models import AqcGoodsItem, AqcSaleRecord, AqcShop, AqcUser


XML_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXPECTED_HEADERS = [
    "订单号",
    "系列",
    "型号",
    "品牌",
    "单价",
    "数量",
    "应收金额",
    "折扣",
    "优惠券",
    "实收金额",
    "买家信息",
    "下单门店",
    "付款渠道",
    "导购",
    "状态",
    "是否确认",
    "下单时间",
]
def _clean_text(value: str | None, max_length: int) -> str:
    return (value or "").strip()[:max_length]


def _to_decimal(raw: str | None, default: str = "0.00") -> Decimal:
    try:
        return Decimal(str(raw or default).strip() or default).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal(default)


def _to_int(raw: str | None, default: int = 0) -> int:
    try:
        return int(Decimal(str(raw or default).strip() or str(default)).quantize(Decimal("1"), rounding=ROUND_DOWN))
    except Exception:
        return default


def _parse_datetime(raw: str | None) -> datetime:
    text = (raw or "").strip()
    if not text:
        raise ValueError("缺少下单时间")
    return datetime.fromisoformat(text.replace("T", " "))


def _normalize_shop_name(raw: str | None) -> tuple[str, str]:
    return normalize_shop_name(_clean_text(raw, 255))


def _normalize_index_key(series: str, brand: str, model: str) -> str:
    seed = f"{series} {brand} {model}".strip()
    if not seed:
        return "#"
    for ch in seed:
        if ch.isascii() and ch.isalpha():
            return ch.upper()
        if ch.isdigit():
            return ch
    return "#"


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
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError("Excel 工作表关系解析失败")


def _read_template_rows(xlsx_path: Path) -> list[dict[str, str]]:
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

    missing_headers = [header for header in EXPECTED_HEADERS if header not in headers]
    if missing_headers:
        raise ValueError(f"销售表缺少必要列: {', '.join(missing_headers)}")
    return rows


def _row_signature(
    *,
    sold_at: datetime,
    brand: str,
    series: str,
    model: str,
    unit_price: Decimal,
    receivable_amount: Decimal,
    received_amount: Decimal,
    coupon_amount: Decimal,
    quantity: int,
    shop_name: str,
    salesperson: str,
    channel: str,
) -> tuple[str, str, str, str, str, str, str, str, int, str, str, str]:
    return (
        sold_at.strftime("%Y-%m-%d %H:%M:%S"),
        brand,
        series,
        model,
        f"{unit_price:.2f}",
        f"{receivable_amount:.2f}",
        f"{received_amount:.2f}",
        f"{coupon_amount:.2f}",
        quantity,
        shop_name,
        salesperson,
        channel,
    )


def inspect_sales_template_import(
    db: Session,
    xlsx_path: str | Path,
    *,
    allowed_shop_ids: list[int] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = Path(xlsx_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"销售表不存在: {path}")

    rows = _read_template_rows(path)

    goods_items = db.execute(select(AqcGoodsItem)).scalars().all()
    goods_by_key = {
        (
            _clean_text(item.brand, 120),
            _clean_text(item.series_name, 120),
            _clean_text(item.model_name, 191),
        ): item
        for item in goods_items
    }
    goods_by_model = {}
    for item in goods_items:
        model = _clean_text(item.model_name, 191)
        if model and model not in goods_by_model:
            goods_by_model[model] = item

    shops = db.execute(select(AqcShop)).scalars().all()
    shop_by_name = {_clean_text(item.name, 255): item for item in shops if _clean_text(item.name, 255)}

    creator = (
        db.execute(select(AqcUser).where(AqcUser.username == "admin").limit(1)).scalars().first()
        or db.execute(select(AqcUser).order_by(AqcUser.id.asc()).limit(1)).scalars().first()
    )
    creator_id = creator.id if creator else None

    allowed_shop_id_set = {int(item) for item in (allowed_shop_ids or []) if int(item) > 0}
    report: dict[str, Any] = {
        "path": str(path),
        "file": path.name,
        "totalRows": len(rows),
        "rowsReady": 0,
        "duplicates": 0,
        "duplicateOrders": [],
        "skipped": 0,
        "matchedGoods": 0,
        "matchedShops": 0,
        "unmatchedGoods": [],
        "unmatchedShops": [],
        "outOfScopeShops": [],
        "aliasCounts": {},
    }
    prepared_rows: list[dict[str, Any]] = []
    parsed_rows: list[dict[str, Any]] = []
    sold_at_values: list[datetime] = []
    model_values: set[str] = set()
    shop_name_values: set[str] = set()

    for row in rows:
        order_num = _clean_text(row.get("订单号"), 32)
        brand = _clean_text(row.get("品牌"), 120)
        series = _clean_text(row.get("系列"), 120)
        model = _clean_text(row.get("型号"), 191)
        sold_at_raw = _clean_text(row.get("下单时间"), 32)
        if not (order_num and model and sold_at_raw):
            parsed_rows.append({"skip": True})
            continue
        sold_at = _parse_datetime(sold_at_raw)
        unit_price = _to_decimal(row.get("单价"))
        quantity = max(_to_int(row.get("数量"), 1), 1)
        receivable_amount = _to_decimal(row.get("应收金额")) or (unit_price * quantity).quantize(Decimal("0.01"))
        coupon_amount = _to_decimal(row.get("优惠券"))
        received_amount = _to_decimal(row.get("实收金额")) or receivable_amount
        discount_raw = _clean_text(row.get("折扣"), 16)
        if not discount_raw or discount_raw == "/":
            discount_rate = Decimal("10.00") if received_amount >= receivable_amount else (
                received_amount / receivable_amount * Decimal("10")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            discount_rate = _to_decimal(discount_raw, "10.00")
        buyer_info = _clean_text(row.get("买家信息"), 120)
        raw_shop_name, normalized_shop_name = _normalize_shop_name(row.get("下单门店"))
        channel = _clean_text(row.get("付款渠道"), 50)
        salesperson = _clean_text(row.get("导购"), 80)
        status = _clean_text(row.get("状态"), 40)
        confirmed = _clean_text(row.get("是否确认"), 40)
        shop_name = normalized_shop_name or _clean_text(row.get("买家信息"), 255)
        signature = _row_signature(
            sold_at=sold_at,
            brand=brand,
            series=series,
            model=model,
            unit_price=unit_price,
            receivable_amount=receivable_amount,
            received_amount=received_amount,
            coupon_amount=coupon_amount,
            quantity=quantity,
            shop_name=shop_name,
            salesperson=salesperson,
            channel=channel,
        )
        sold_at_values.append(sold_at)
        if model:
            model_values.add(model)
        if shop_name:
            shop_name_values.add(shop_name)
        parsed_rows.append(
            {
                "skip": False,
                "order_num": order_num,
                "brand": brand,
                "series": series,
                "model": model,
                "sold_at": sold_at,
                "unit_price": unit_price,
                "quantity": quantity,
                "receivable_amount": receivable_amount,
                "coupon_amount": coupon_amount,
                "received_amount": received_amount,
                "discount_rate": discount_rate,
                "buyer_info": buyer_info,
                "raw_shop_name": raw_shop_name,
                "shop_name": shop_name,
                "channel": channel,
                "salesperson": salesperson,
                "status": status,
                "confirmed": confirmed,
                "signature": signature,
            }
        )

    existing_signatures: set[tuple[str, str, str, str, str, str, str, str, int, str, str, str]] = set()
    if sold_at_values:
        existing_stmt = select(AqcSaleRecord).where(
            AqcSaleRecord.sold_at >= min(sold_at_values),
            AqcSaleRecord.sold_at <= max(sold_at_values),
        )
        if model_values:
            existing_stmt = existing_stmt.where(AqcSaleRecord.goods_model.in_(sorted(model_values)))
        if shop_name_values:
            existing_stmt = existing_stmt.where(AqcSaleRecord.shop_name.in_(sorted(shop_name_values)))
        existing_rows = db.execute(existing_stmt).scalars().all()
        existing_signatures = {
            _row_signature(
                sold_at=item.sold_at,
                brand=_clean_text(item.goods_brand, 120),
                series=_clean_text(item.goods_series, 120),
                model=_clean_text(item.goods_model, 191),
                unit_price=Decimal(str(item.unit_price or 0)),
                receivable_amount=Decimal(str(item.receivable_amount or 0)),
                received_amount=Decimal(str(item.amount or 0)),
                coupon_amount=Decimal(str(item.coupon_amount or 0)),
                quantity=int(item.quantity or 0),
                shop_name=_clean_text(item.shop_name, 255),
                salesperson=_clean_text(item.salesperson, 80),
                channel=_clean_text(item.channel, 50),
            )
            for item in existing_rows
        }

    for row in parsed_rows:
        if row.get("skip"):
            report["skipped"] += 1
            continue
        order_num = str(row["order_num"])
        brand = str(row["brand"])
        series = str(row["series"])
        model = str(row["model"])
        sold_at = row["sold_at"]
        unit_price = row["unit_price"]
        quantity = int(row["quantity"])
        receivable_amount = row["receivable_amount"]
        coupon_amount = row["coupon_amount"]
        received_amount = row["received_amount"]
        discount_rate = row["discount_rate"]
        buyer_info = str(row["buyer_info"])
        raw_shop_name = str(row["raw_shop_name"])
        shop_name = str(row["shop_name"])
        channel = str(row["channel"])
        salesperson = str(row["salesperson"])
        status = str(row["status"])
        confirmed = str(row["confirmed"])
        signature = row["signature"]
        if raw_shop_name and raw_shop_name != shop_name:
            report["aliasCounts"][raw_shop_name] = int(report["aliasCounts"].get(raw_shop_name) or 0) + 1
        if signature in existing_signatures:
            report["duplicates"] += 1
            report["duplicateOrders"].append(order_num)
            continue

        goods = goods_by_key.get((brand, series, model)) or goods_by_model.get(model)
        shop = shop_by_name.get(shop_name)
        if goods is not None:
            report["matchedGoods"] += 1
        else:
            report["unmatchedGoods"].append({"order": order_num, "brand": brand, "series": series, "model": model})
        if shop is not None:
            report["matchedShops"] += 1
        else:
            report["unmatchedShops"].append({"order": order_num, "shop": raw_shop_name or shop_name, "mappedShop": shop_name})

        if goods is None or shop is None:
            continue

        if allowed_shop_id_set and shop.id not in allowed_shop_id_set:
            report["outOfScopeShops"].append({"order": order_num, "shopId": int(shop.id), "shop": shop_name})
            continue

        note_parts = [f"来源表:{path.name}"]
        if raw_shop_name and raw_shop_name != shop_name:
            note_parts.append(f"原门店:{raw_shop_name}")
        if status:
            note_parts.append(f"状态:{status}")
        if confirmed:
            note_parts.append(f"确认:{confirmed}")

        prepared_rows.append(
            {
                "signature": signature,
                "sold_at": sold_at,
                "order_num": order_num,
                "goods": goods,
                "brand": brand,
                "series": series,
                "model": model,
                "unit_price": unit_price,
                "receivable_amount": receivable_amount,
                "received_amount": received_amount,
                "coupon_amount": coupon_amount,
                "discount_rate": discount_rate,
                "quantity": quantity,
                "channel": channel,
                "shop": shop,
                "shop_name": shop_name,
                "salesperson": salesperson,
                "buyer_info": buyer_info,
                "note": ";".join(note_parts)[:5000],
            }
        )
        existing_signatures.add(signature)
        report["rowsReady"] += 1

    return report, prepared_rows


def import_sales_template(
    db: Session,
    xlsx_path: str | Path,
    *,
    creator_id: int | None = None,
    creator_name: str | None = None,
    allowed_shop_ids: list[int] | None = None,
) -> dict[str, Any]:
    report, prepared_rows = inspect_sales_template_import(db, xlsx_path, allowed_shop_ids=allowed_shop_ids)
    if report["unmatchedGoods"] or report["unmatchedShops"] or report["outOfScopeShops"]:
        raise ValueError("存在未匹配商品、门店或越权门店，已中止导入")

    imported = 0
    received_total = Decimal("0.00")
    touched_goods_ids: set[int] = set()
    for item in prepared_rows:
        record = AqcSaleRecord(
            sold_at=item["sold_at"],
            order_num=item["order_num"],
            goods_id=item["goods"].id,
            goods_code=_clean_text(item["goods"].product_code, 64),
            goods_brand=item["brand"],
            goods_series=item["series"],
            goods_model=item["model"],
            goods_barcode=_clean_text(item["goods"].barcode, 64),
            unit_price=item["unit_price"],
            receivable_amount=item["receivable_amount"],
            amount=item["received_amount"],
            coupon_amount=item["coupon_amount"],
            discount_rate=item["discount_rate"],
            quantity=item["quantity"],
            channel=item["channel"],
            shop_id=item["shop"].id,
            shop_name=item["shop_name"],
            ship_shop_id=item["shop"].id,
            ship_shop_name=item["shop_name"],
            salesperson=item["salesperson"],
            index_key=_normalize_index_key(item["series"], item["brand"], item["model"]),
            customer_name=item["buyer_info"] if item["buyer_info"] and item["buyer_info"] != item["shop_name"][:120] else "",
            note=item["note"],
            created_by=creator_id,
        )
        db.add(record)
        if item["goods"] is not None and item["shop"] is not None and int(item["quantity"] or 0):
            apply_inventory_delta(
                db,
                goods_item=item["goods"],
                shop=item["shop"],
                delta=-int(item["quantity"] or 0),
                change_content=f"销售导入扣减：订单 {item['order_num']}",
                operator_id=creator_id,
                operator_name=_clean_text(creator_name, 80),
                related_type="sale_import",
            )
            touched_goods_ids.add(int(item["goods"].id))
        imported += 1
        received_total += item["received_amount"]

    db.flush()
    if touched_goods_ids:
        recalculate_goods_stock(db, sorted(touched_goods_ids))
    report["imported"] = imported
    report["receivedTotal"] = float(received_total)
    return report


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv
    if len(args) < 2:
        print("Usage: python -m app.importers.sales_template_import <xlsx_path>", file=sys.stderr)
        return 1

    init_db()
    db = SessionLocal()
    try:
        stats = import_sales_template(db, args[1])
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

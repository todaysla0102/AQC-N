#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FASTAPI_ROOT = ROOT / "backend" / "fastapi"
if str(FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(FASTAPI_ROOT))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import AqcGoodsItem  # noqa: E402


DEFAULT_CLOCK_PLACEHOLDERS = {
    "images/7f4b977a19ce3a6a6d9035af44417ad6.jpg",
}
INSERT_RE_TEMPLATE = r"INSERT INTO `{table}` VALUES \((.*)\);"


@dataclass
class LegacyGoodsImage:
    source_table: str
    legacy_id: int
    name: str
    model: str
    barcode: str
    cover: str
    gallery: list[str]

    @property
    def key(self) -> str:
        return f"{self.source_table}:{self.legacy_id}"

    @property
    def images(self) -> list[str]:
        return unique_image_paths([self.cover, *self.gallery])


def unique_image_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in paths:
        clean = normalize_legacy_path(item)
        if not clean or clean in DEFAULT_CLOCK_PLACEHOLDERS or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        clean = str(item or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def normalize_key(value: str | None) -> str:
    return re.sub(r"[^0-9A-Z]+", "", str(value or "").upper())


def normalize_legacy_path(value: str | None) -> str:
    clean = str(value or "").strip().strip('"').strip("'").replace("\\/", "/")
    if not clean:
        return ""
    clean = re.sub(r"^https?://[^/]+/", "", clean, flags=re.I)
    clean = clean.lstrip("/")
    if clean.startswith("upload/"):
        clean = clean[len("upload/") :]
    return clean


def parse_gallery(raw: str | None) -> list[str]:
    clean = str(raw or "").strip()
    if not clean or clean == "[]":
        return []
    try:
        parsed = json.loads(clean.replace("\\/", "/"))
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [normalize_legacy_path(str(item or "")) for item in parsed]


def parse_insert_rows(sql_text: str, table: str) -> list[tuple]:
    rows: list[tuple] = []
    insert_re = re.compile(INSERT_RE_TEMPLATE.format(table=re.escape(table)))
    for match in insert_re.finditer(sql_text):
        raw_tuple = "(" + re.sub(r"\bNULL\b", "None", match.group(1)) + ")"
        try:
            row = ast.literal_eval(raw_tuple)
        except Exception:
            continue
        if isinstance(row, tuple):
            rows.append(row)
    return rows


def parse_goods_item_rows(sql_text: str) -> list[LegacyGoodsImage]:
    rows: list[LegacyGoodsImage] = []
    for row in parse_insert_rows(sql_text, "goods_item"):
        if len(row) <= 51:
            continue
        legacy_id = int(row[0] or 0)
        if legacy_id <= 0:
            continue
        rows.append(
            LegacyGoodsImage(
                source_table="goods_item",
                legacy_id=legacy_id,
                name=str(row[1] or "").strip(),
                model=str(row[51] or row[1] or "").strip(),
                barcode="",
                cover=normalize_legacy_path(row[12]),
                gallery=parse_gallery(row[13]),
            )
        )
    return rows


def parse_clock_offline_rows(sql_text: str) -> list[LegacyGoodsImage]:
    rows: list[LegacyGoodsImage] = []
    for row in parse_insert_rows(sql_text, "clock_offline"):
        if len(row) <= 56:
            continue
        legacy_id = int(row[0] or 0)
        if legacy_id <= 0:
            continue
        rows.append(
            LegacyGoodsImage(
                source_table="clock_offline",
                legacy_id=legacy_id,
                name=str(row[1] or "").strip(),
                barcode=str(row[2] or "").strip(),
                cover=normalize_legacy_path(row[12]),
                gallery=parse_gallery(row[13]),
                model=str(row[55] or row[1] or "").strip(),
            )
        )
    return rows


def parse_legacy_goods(sql_path: Path) -> list[LegacyGoodsImage]:
    sql_text = sql_path.read_text(errors="ignore")
    return [*parse_goods_item_rows(sql_text), *parse_clock_offline_rows(sql_text)]


def source_roots_from_args(args: argparse.Namespace) -> list[Path]:
    candidates = [Path(args.legacy_root).resolve()]
    if args.fallback_legacy_root:
        candidates.append(Path(args.fallback_legacy_root).resolve())
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def find_sql_path(args: argparse.Namespace, source_roots: list[Path]) -> Path:
    if args.sql:
        return Path(args.sql).resolve()
    for root in source_roots:
        candidate = root / "database" / "whaqc_data.sql"
        if candidate.exists():
            return candidate
    return source_roots[0] / "database" / "whaqc_data.sql"


def build_source_index(source_roots: list[Path]) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for source_root in source_roots:
        upload_root = source_root / "public" / "upload"
        if not upload_root.exists():
            continue
        for path in upload_root.rglob("*"):
            if not path.is_file():
                continue
            index.setdefault(path.name.lower(), []).append(path)
    return index


def resolve_source(path_value: str, source_roots: list[Path], source_index: dict[str, list[Path]]) -> Path | None:
    for source_root in source_roots:
        legacy_public = source_root / "public"
        for direct in (
            legacy_public / "upload" / path_value,
            legacy_public / path_value,
            source_root / path_value,
        ):
            if direct.exists():
                return direct
    matches = source_index.get(Path(path_value).name.lower()) or []
    return matches[0] if matches else None


def copy_legacy_image(source: Path, target_dir: Path, source_key: str, ordinal: int) -> str:
    suffix = source.suffix.lower() or ".png"
    safe_source_key = re.sub(r"[^0-9A-Za-z_.-]+", "-", source_key).strip("-_.") or "legacy"
    safe_stem = re.sub(r"[^0-9A-Za-z_.-]+", "-", source.stem).strip("-_.") or "image"
    target = target_dir / f"{safe_source_key}-{ordinal:02d}-{safe_stem}{suffix}"
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        shutil.copy2(source, target)
    rel = target.relative_to(Path(settings.upload_root).resolve()).as_posix()
    return f"{settings.upload_url_prefix.rstrip('/')}/{rel}"


def add_unique_key(by_key: dict[str, list[AqcGoodsItem]], value: str | None, item: AqcGoodsItem) -> None:
    key = normalize_key(value)
    if not key:
        return
    bucket = by_key.setdefault(key, [])
    if all(existing.id != item.id for existing in bucket):
        bucket.append(item)


def match_item(
    row: LegacyGoodsImage,
    by_legacy_id: dict[int, AqcGoodsItem],
    by_barcode: dict[str, list[AqcGoodsItem]],
    by_key: dict[str, list[AqcGoodsItem]],
) -> AqcGoodsItem | None:
    if row.source_table == "goods_item" and row.legacy_id in by_legacy_id:
        return by_legacy_id[row.legacy_id]
    barcode_matches = by_barcode.get(normalize_key(row.barcode)) or []
    if len(barcode_matches) == 1:
        return barcode_matches[0]
    for candidate in (row.model, row.name):
        matches = by_key.get(normalize_key(candidate)) or []
        if len(matches) == 1:
            return matches[0]
    return None


def parse_existing_image_list(raw: str | None) -> list[str]:
    try:
        parsed = json.loads(str(raw or "[]"))
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return unique_strings([str(item or "") for item in parsed])


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy AQC-O goods images into AQC-N uploads and backfill matched goods.")
    parser.add_argument("--legacy-root", default=str(ROOT / "legacy-assets" / "aqc-o"))
    parser.add_argument("--fallback-legacy-root", default=str(ROOT / "legacy-assets" / "aqc-o"))
    parser.add_argument("--sql", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--copy-only", action="store_true", help="Only copy referenced legacy images, without connecting to the AQC-N database.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing AQC-N image fields even when they already use /uploads.")
    args = parser.parse_args()

    if "AQC_UPLOAD_ROOT" not in os.environ:
        settings.upload_root = str(ROOT / "uploads")
    if "AQC_UPLOAD_URL_PREFIX" not in os.environ:
        settings.upload_url_prefix = "/uploads"

    source_roots = source_roots_from_args(args)
    if not source_roots:
        raise SystemExit("No legacy roots found.")

    sql_path = find_sql_path(args, source_roots)
    upload_root = Path(settings.upload_root).resolve()
    target_base = upload_root / "goods" / "legacy"
    target_base.mkdir(parents=True, exist_ok=True)

    all_rows = parse_legacy_goods(sql_path)
    legacy_rows = [row for row in all_rows if row.images]
    source_index = build_source_index(source_roots)

    copied = 0
    missing_files: list[str] = []
    copied_by_key: dict[str, list[str]] = {}
    for row in legacy_rows:
        target_dir = target_base / row.source_table / str(row.legacy_id)
        if not args.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        urls: list[str] = []
        for index, legacy_path in enumerate(row.images, start=1):
            source = resolve_source(legacy_path, source_roots, source_index)
            if source is None:
                missing_files.append(f"{row.key}:{legacy_path}")
                continue
            if args.dry_run:
                rel = (Path("goods") / "legacy" / row.source_table / str(row.legacy_id) / source.name).as_posix()
                urls.append(f"{settings.upload_url_prefix.rstrip('/')}/{rel}")
            else:
                urls.append(copy_legacy_image(source, target_dir, row.key, index))
                copied += 1
        copied_by_key[row.key] = unique_strings(urls)

    matched = 0
    updated = 0
    skipped_existing = 0
    unmatched: list[str] = []
    if not args.copy_only:
        with SessionLocal() as db:
            items = db.execute(select(AqcGoodsItem)).scalars().all()
            by_legacy_id = {int(item.legacy_id): item for item in items if item.legacy_id is not None}
            by_barcode: dict[str, list[AqcGoodsItem]] = {}
            by_key: dict[str, list[AqcGoodsItem]] = {}
            for item in items:
                add_unique_key(by_barcode, item.barcode, item)
                for value in (item.model_name, item.goodspec, item.name):
                    add_unique_key(by_key, value, item)

            for row in legacy_rows:
                urls = copied_by_key.get(row.key) or []
                if not urls:
                    continue
                item = match_item(row, by_legacy_id, by_barcode, by_key)
                if item is None:
                    unmatched.append(f"{row.key}:{row.barcode or row.model or row.name}")
                    continue
                matched += 1
                already_local = str(item.cover_image or "").startswith(settings.upload_url_prefix.rstrip("/") + "/")
                if already_local and not args.force:
                    skipped_existing += 1
                    continue
                existing = parse_existing_image_list(item.image_list)
                item.cover_image = urls[0]
                item.image_list = json.dumps(unique_strings([*urls[1:], *existing]), ensure_ascii=False)
                updated += 1

            if args.dry_run:
                db.rollback()
            else:
                db.commit()

    row_counts = Counter(row.source_table for row in all_rows)
    image_row_counts = Counter(row.source_table for row in legacy_rows)
    print(json.dumps({
        "dryRun": args.dry_run,
        "copyOnly": args.copy_only,
        "sql": str(sql_path),
        "sourceRoots": [str(root) for root in source_roots],
        "rowsByTable": dict(row_counts),
        "rowsWithImagesByTable": dict(image_row_counts),
        "legacyRowsWithImages": len(legacy_rows),
        "copiedFiles": 0 if args.dry_run else copied,
        "matchedGoods": matched,
        "updatedGoods": updated,
        "skippedExistingGoods": skipped_existing,
        "missingFiles": len(missing_files),
        "unmatchedGoods": len(unmatched),
        "missingFileSamples": missing_files[:20],
        "unmatchedSamples": unmatched[:20],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

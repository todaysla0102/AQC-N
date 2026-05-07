#!/usr/bin/env python3
"""Import old clock_offline images onto existing AQC-N goods by model.

This tool is intentionally narrow: it parses only the legacy clock_offline
table, matches only existing AQC-N model names, and emits only image field
updates for aqc_goods_items.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


CLOCK_IMAGE_INDEX = 12
CLOCK_IMAGES_INDEX = 13
CLOCK_MODEL_INDEX = 55


@dataclass(frozen=True)
class LegacyClockImage:
    model: str
    normalized_model: str
    images: tuple[str, ...]


@dataclass(frozen=True)
class GoodsRow:
    goods_id: int
    model: str
    normalized_model: str
    cover_image: str
    image_list: str


def normalize_model(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def sql_quote(value: str) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def parse_sql_values(values: str) -> list[str | None]:
    parsed: list[str | None] = []
    current: list[str] = []
    in_string = False
    was_string = False
    index = 0
    while index < len(values):
        char = values[index]
        if in_string:
            if char == "\\":
                if index + 1 < len(values):
                    current.append(values[index + 1])
                    index += 2
                    continue
            elif char == "'":
                if index + 1 < len(values) and values[index + 1] == "'":
                    current.append("'")
                    index += 2
                    continue
                in_string = False
                was_string = True
                index += 1
                continue
            current.append(char)
            index += 1
            continue
        if char == "'":
            in_string = True
            was_string = True
            index += 1
            continue
        if char == ",":
            token = "".join(current).strip()
            parsed.append(token if was_string or token.upper() != "NULL" else None)
            current = []
            was_string = False
            index += 1
            continue
        current.append(char)
        index += 1
    token = "".join(current).strip()
    parsed.append(token if was_string or token.upper() != "NULL" else None)
    return parsed


def iter_clock_rows(sql_path: Path) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    prefix = "INSERT INTO `clock_offline` VALUES ("
    with sql_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(prefix):
                continue
            values = line[len(prefix) :].rstrip()
            if values.endswith(");"):
                values = values[:-2]
            rows.append(parse_sql_values(values))
    return rows


def parse_image_list(raw: object) -> list[str]:
    if raw is None:
        return []
    value = str(raw).strip()
    if not value or value.upper() == "NULL":
        return []
    parsed: object
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, str) and parsed.strip():
        return [parsed.strip()]
    return [piece.strip() for piece in re.split(r"[,;\n\r]+", value) if piece.strip()]


def clean_legacy_image_path(value: object) -> str:
    image_path = str(value or "").strip()
    if not image_path:
        return ""
    image_path = image_path.split("?", 1)[0].lstrip("/")
    if image_path.startswith("upload/"):
        image_path = image_path[len("upload/") :]
    return image_path


def existing_legacy_image(legacy_root: Path, image_path: str) -> Path | None:
    cleaned = clean_legacy_image_path(image_path)
    if not cleaned:
        return None
    candidates = [
        legacy_root / "public" / "upload" / cleaned,
        legacy_root / "public" / cleaned,
        legacy_root / cleaned,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def collect_legacy_clock_images(legacy_root: Path) -> tuple[dict[str, LegacyClockImage], Counter]:
    sql_path = legacy_root / "whaqc_data.sql"
    rows = iter_clock_rows(sql_path)
    grouped: dict[str, list[LegacyClockImage]] = defaultdict(list)
    stats: Counter = Counter(clock_rows=len(rows))
    for row in rows:
        if len(row) <= CLOCK_MODEL_INDEX:
            stats["short_rows"] += 1
            continue
        model = str(row[CLOCK_MODEL_INDEX] or "").strip()
        normalized_model = normalize_model(model)
        if not normalized_model:
            stats["rows_without_model"] += 1
            continue
        raw_images = [row[CLOCK_IMAGE_INDEX], *parse_image_list(row[CLOCK_IMAGES_INDEX])]
        images: list[str] = []
        seen: set[str] = set()
        for raw_image in raw_images:
            cleaned = clean_legacy_image_path(raw_image)
            if cleaned and cleaned not in seen:
                images.append(cleaned)
                seen.add(cleaned)
        if not images:
            stats["rows_without_images"] += 1
            continue
        stats["rows_with_images"] += 1
        grouped[normalized_model].append(LegacyClockImage(model=model, normalized_model=normalized_model, images=tuple(images)))

    usable: dict[str, LegacyClockImage] = {}
    for normalized_model, entries in grouped.items():
        image_sets = {entry.images for entry in entries}
        if len(image_sets) == 1:
            usable[normalized_model] = entries[0]
        else:
            stats["skipped_ambiguous_legacy_models"] += 1
    stats["usable_legacy_models"] = len(usable)
    return usable, stats


def load_goods_tsv(path: Path) -> tuple[dict[str, GoodsRow], Counter]:
    by_model: dict[str, list[GoodsRow]] = defaultdict(list)
    stats: Counter = Counter()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            stats["goods_rows"] += 1
            normalized_model = normalize_model(row[1])
            if not normalized_model:
                stats["goods_without_model"] += 1
                continue
            by_model[normalized_model].append(
                GoodsRow(
                    goods_id=int(row[0]),
                    model=row[1],
                    normalized_model=normalized_model,
                    cover_image=row[2] if len(row) > 2 else "",
                    image_list=row[3] if len(row) > 3 else "[]",
                )
            )
    usable: dict[str, GoodsRow] = {}
    for normalized_model, entries in by_model.items():
        if len(entries) == 1:
            usable[normalized_model] = entries[0]
        else:
            stats["skipped_ambiguous_aqc_models"] += 1
    stats["usable_aqc_models"] = len(usable)
    return usable, stats


def destination_url(model: str, source: Path, ordinal: int) -> tuple[str, Path]:
    digest = hashlib.sha1(source.read_bytes()).hexdigest()[:12]
    safe_model = re.sub(r"[^A-Za-z0-9_.-]+", "_", model.strip())[:80] or "unknown"
    extension = source.suffix.lower() or ".jpg"
    relative = Path("uploads") / "goods" / "clock_offline" / safe_model / f"{ordinal:02d}-{digest}{extension}"
    return "/" + relative.as_posix(), relative


def build_updates(
    *,
    legacy_root: Path,
    goods_by_model: dict[str, GoodsRow],
    legacy_by_model: dict[str, LegacyClockImage],
    stage_root: Path | None,
    replace_existing: bool,
) -> tuple[list[dict[str, object]], Counter]:
    updates: list[dict[str, object]] = []
    stats: Counter = Counter()
    for normalized_model, goods in goods_by_model.items():
        legacy = legacy_by_model.get(normalized_model)
        if not legacy:
            continue
        if goods.cover_image and not replace_existing:
            stats["skipped_existing_images"] += 1
            continue
        urls: list[str] = []
        relative_paths: list[Path] = []
        for ordinal, legacy_image in enumerate(legacy.images, start=1):
            source = existing_legacy_image(legacy_root, legacy_image)
            if not source:
                stats["missing_files"] += 1
                continue
            url, relative = destination_url(goods.model, source, ordinal)
            urls.append(url)
            relative_paths.append(relative)
            if stage_root:
                target = stage_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                stats["copied_files"] += 1
        if not urls:
            stats["skipped_no_existing_files"] += 1
            continue
        stats["matched_models"] += 1
        updates.append(
            {
                "goods_id": goods.goods_id,
                "model": goods.model,
                "legacy_model": legacy.model,
                "cover_image": urls[0],
                "image_list": json.dumps(urls, ensure_ascii=False),
                "files": [path.as_posix() for path in relative_paths],
            }
        )
    stats["updates"] = len(updates)
    return updates, stats


def write_sql(path: Path, updates: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("START TRANSACTION;\n")
        for update in updates:
            handle.write(
                "UPDATE aqc_goods_items SET "
                f"cover_image = {sql_quote(str(update['cover_image']))}, "
                f"image_list = {sql_quote(str(update['image_list']))} "
                f"WHERE id = {int(update['goods_id'])};\n"
            )
        handle.write("COMMIT;\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely match old clock_offline images to existing AQC-N goods.")
    parser.add_argument("--legacy-root", required=True, type=Path, help="Old wx.whaqc.cn project directory.")
    parser.add_argument("--goods-tsv", required=True, type=Path, help="TSV: id, model_name, cover_image, image_list.")
    parser.add_argument("--stage-root", type=Path, help="Copy matched upload files into this staging directory.")
    parser.add_argument("--sql-output", type=Path, help="Write UPDATE-only SQL file.")
    parser.add_argument("--manifest-output", type=Path, help="Write JSON manifest.")
    parser.add_argument("--replace-existing", action="store_true", help="Also replace goods that already have cover_image.")
    parser.add_argument("--sample", type=int, default=10, help="Number of matched samples to print.")
    args = parser.parse_args()

    if not (args.legacy_root / "whaqc_data.sql").is_file():
        print(f"Legacy SQL not found: {args.legacy_root / 'whaqc_data.sql'}", file=sys.stderr)
        return 2
    if not args.goods_tsv.is_file():
        print(f"Goods TSV not found: {args.goods_tsv}", file=sys.stderr)
        return 2

    legacy_by_model, legacy_stats = collect_legacy_clock_images(args.legacy_root)
    goods_by_model, goods_stats = load_goods_tsv(args.goods_tsv)
    updates, update_stats = build_updates(
        legacy_root=args.legacy_root,
        goods_by_model=goods_by_model,
        legacy_by_model=legacy_by_model,
        stage_root=args.stage_root,
        replace_existing=args.replace_existing,
    )

    if args.sql_output:
        write_sql(args.sql_output, updates)
    if args.manifest_output:
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            json.dumps({"stats": {**legacy_stats, **goods_stats, **update_stats}, "updates": updates}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    combined = Counter()
    combined.update(legacy_stats)
    combined.update(goods_stats)
    combined.update(update_stats)
    print(json.dumps(dict(combined), ensure_ascii=False, indent=2, sort_keys=True))
    print("samples:")
    for update in updates[: max(0, args.sample)]:
        print(f"- id={update['goods_id']} model={update['model']} cover={update['cover_image']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

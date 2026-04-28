from __future__ import annotations


GOODS_ATTRIBUTE_NONE = "-"
GOODS_ATTRIBUTE_BAO = "保"
GOODS_ATTRIBUTE_CHANG = "畅"
GOODS_ATTRIBUTE_VALUES = (
    GOODS_ATTRIBUTE_NONE,
    GOODS_ATTRIBUTE_BAO,
    GOODS_ATTRIBUTE_CHANG,
)


def clean_goods_text(value: str | None, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def normalize_goods_attribute(value: str | None) -> str:
    clean_value = clean_goods_text(value, 8)
    if clean_value in {GOODS_ATTRIBUTE_BAO, GOODS_ATTRIBUTE_CHANG}:
        return clean_value
    return GOODS_ATTRIBUTE_NONE


def split_model_attribute(
    model: str | None,
    attribute: str | None = None,
    *,
    max_length: int = 191,
) -> tuple[str, str]:
    clean_model = clean_goods_text(model, max_length)
    explicit_attribute = normalize_goods_attribute(attribute)
    inferred_attribute = GOODS_ATTRIBUTE_NONE

    if clean_model and clean_model[-1] in {GOODS_ATTRIBUTE_BAO, GOODS_ATTRIBUTE_CHANG}:
        stripped_model = clean_model[:-1].rstrip()
        if stripped_model:
            clean_model = stripped_model[:max_length]
            inferred_attribute = str(model or "")[-1]

    final_attribute = explicit_attribute if explicit_attribute != GOODS_ATTRIBUTE_NONE else inferred_attribute
    return clean_model, final_attribute


def compose_goods_name(brand: str | None, series: str | None, model: str | None, fallback: str = "") -> str:
    parts = [
        clean_goods_text(brand, 120),
        clean_goods_text(series, 120),
        clean_goods_text(model, 191),
    ]
    name = " ".join(part for part in parts if part).strip() or clean_goods_text(fallback, 191) or "未命名商品"
    return name[:191]

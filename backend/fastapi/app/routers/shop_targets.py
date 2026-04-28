from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from os.path import commonprefix

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import SHANGHAI_TZ, get_aqc_role_key, require_permissions, scoped_shop_conditions, to_iso, user_shop_ids
from ..models import AqcSaleRecord, AqcShop, AqcShopTargetLog, AqcShopTargetMonth, AqcShopTargetPreset, AqcUser
from ..schemas import (
    ShopScheduleShopOut,
    ShopTargetContributionOut,
    ShopTargetLogItemOut,
    ShopTargetLogListResponse,
    ShopTargetModelGoalOut,
    ShopTargetModelSaleOut,
    ShopTargetMonthOut,
    ShopTargetPageResponse,
    ShopTargetPresetCreateRequest,
    ShopTargetPresetListResponse,
    ShopTargetPresetOut,
    ShopTargetSaveRequest,
    ShopTargetSaveResponse,
    ShopTargetStageOut,
)
from .sales import _sale_metric_snapshot


router = APIRouter(prefix="/shop-targets", tags=["shop-targets"])

SHOP_TARGET_LOG_LIMIT = 20


def _store_condition():
    return or_(
        AqcShop.legacy_id.is_not(None),
        AqcShop.shop_type.is_(None),
        AqcShop.shop_type == 0,
    )


def _clean_text(value: object | None, limit: int = 255) -> str:
    return str(value or "").strip()[:limit]


def _to_decimal(value: object | None, default: str = "0.00") -> Decimal:
    try:
        return Decimal(str(value if value is not None and str(value).strip() != "" else default)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    except Exception:
        return Decimal(default).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_float(value: object | None) -> float:
    return float(_to_decimal(value))


def _load_target_shop(db: Session, user: AqcUser, shop_id: int) -> AqcShop:
    stmt = (
        select(AqcShop)
        .options(selectinload(AqcShop.manager_user))
        .where(AqcShop.id == shop_id, _store_condition())
        .limit(1)
    )
    scope_conditions = scoped_shop_conditions(user)
    if scope_conditions:
        stmt = stmt.where(*scope_conditions)
    shop = db.execute(stmt).scalars().first()
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在或当前账号无权访问")
    if not bool(getattr(shop, "target_enabled", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前店铺未开启目标功能")
    role_key = get_aqc_role_key(user)
    if role_key != "aqc_admin" and int(shop.id) not in user_shop_ids(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权查看该店铺目标")
    return shop


def _can_edit_target(user: AqcUser) -> bool:
    return get_aqc_role_key(user) == "aqc_admin"


def _month_key(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _month_label(year: int, month: int) -> str:
    return f"{year} 年 {month} 月"


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _json_loads(raw_value: str | None, fallback):
    try:
        parsed = json.loads(raw_value or "")
    except Exception:
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _coerce_mapping(item: object | None) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        try:
            payload = item.model_dump()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    if item is None:
        return {}
    payload: dict[str, object] = {}
    for key in dir(item):
        if key.startswith("_"):
            continue
        try:
            value = getattr(item, key)
        except Exception:
            continue
        if callable(value):
            continue
        payload[key] = value
    return payload


def _normalize_models(values: list[object] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values or []:
        text = _clean_text(item, 80)
        if not text:
            continue
        key = text.upper()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _infer_preset_name(models: list[str]) -> str:
    normalized = [item.strip() for item in models if item and item.strip()]
    if not normalized:
        return "未命名型号组"
    if len(normalized) == 1:
        return normalized[0][:120]
    prefix = commonprefix([item.upper() for item in normalized]).strip(" -_/")
    if prefix:
        for item in normalized:
            if item.upper().startswith(prefix):
                return item[:len(prefix)].strip(" -_/")[:120] or item[:120]
    return normalized[0][:120]


def _normalize_stage_items(items: list[object] | None) -> list[dict]:
    normalized: list[dict] = []
    for item in items or []:
        payload = _coerce_mapping(item)
        if not payload:
            continue
        target_amount = _to_decimal(payload.get("targetAmount"))
        reward_amount = _to_decimal(payload.get("rewardAmount"))
        if target_amount <= 0:
            continue
        normalized.append({
            "targetAmount": float(target_amount),
            "rewardAmount": float(reward_amount if reward_amount >= 0 else Decimal("0.00")),
        })
    normalized.sort(key=lambda row: (float(row["targetAmount"]), float(row["rewardAmount"])))
    deduped: list[dict] = []
    seen_targets: set[float] = set()
    for index, item in enumerate(normalized, start=1):
        target_amount = float(item["targetAmount"])
        if target_amount in seen_targets:
            continue
        seen_targets.add(target_amount)
        deduped.append({
            "level": index,
            "targetAmount": target_amount,
            "rewardAmount": float(item["rewardAmount"]),
        })
    for index, item in enumerate(deduped, start=1):
        item["level"] = index
    return deduped


def _normalize_model_goals(items: list[object] | None) -> list[dict]:
    normalized: list[dict] = []
    for item in items or []:
        payload = _coerce_mapping(item)
        if not payload:
            continue
        goods_id = int(payload.get("goodsId") or 0)
        models = _normalize_models(payload.get("models") if isinstance(payload.get("models"), list) else [])
        target_quantity = int(payload.get("targetQuantity") or 0)
        reward_amount = _to_decimal(payload.get("rewardAmount"))
        model_display = _clean_text(payload.get("modelDisplay"), 120)
        brand = _clean_text(payload.get("brand"), 120)
        series = _clean_text(payload.get("series"), 120)
        barcode = _clean_text(payload.get("barcode"), 120)
        if not model_display and len(models) == 1:
            model_display = models[0]
        if model_display and not models:
            models = [model_display]
        name = _clean_text(payload.get("name"), 120) or _infer_preset_name(models)
        if not name and not models and target_quantity <= 0 and reward_amount <= 0 and goods_id <= 0:
            continue
        normalized.append({
            "goodsId": goods_id if goods_id > 0 else None,
            "name": name or (models[0] if models else "未命名型号"),
            "modelDisplay": model_display,
            "brand": brand,
            "series": series,
            "barcode": barcode,
            "models": models,
            "targetQuantity": max(target_quantity, 0),
            "rewardAmount": float(reward_amount if reward_amount >= 0 else Decimal("0.00")),
        })
    return normalized


def _serialize_target_month_config(item: AqcShopTargetMonth | None) -> dict:
    if item is None:
        return {
            "targetAmount": 0.0,
            "stages": [],
            "modelGoals": [],
        }
    stages = _normalize_stage_items(_json_loads(item.stages_json, []))
    model_goals = _normalize_model_goals(_json_loads(item.model_goals_json, []))
    target_amount = float(_to_decimal(item.target_amount))
    if stages:
        target_amount = max(target_amount, max(float(stage.get("targetAmount") or 0) for stage in stages))
    if target_amount > 0 and not stages:
        stages = [{
            "level": 1,
            "targetAmount": target_amount,
            "rewardAmount": 0.0,
        }]
    return {
        "targetAmount": target_amount,
        "stages": stages,
        "modelGoals": model_goals,
    }


def _match_model_goal(goods_model: str, models: list[str]) -> bool:
    normalized_model = _clean_text(goods_model, 191).upper()
    if not normalized_model:
        return False
    for item in models:
        token = _clean_text(item, 80).upper()
        if token and (normalized_model == token or normalized_model.startswith(token)):
            return True
    return False


def _build_month_sales_metrics(rows: list[AqcSaleRecord], config: dict, *, month: str, month_label: str) -> ShopTargetMonthOut:
    actual_amount = 0.0
    contribution_map: dict[str, float] = {}
    model_quantities: list[int] = [0 for _ in config["modelGoals"]]
    model_sales_map: dict[str, int] = {}
    for row in rows:
        receivable_amount, received_amount, _coupon_amount, quantity, _sale_status = _sale_metric_snapshot(row)
        actual_amount = round(actual_amount + received_amount, 2)
        contributor = _clean_text(row.salesperson, 80) or "未登记人员"
        contribution_map[contributor] = round(contribution_map.get(contributor, 0.0) + received_amount, 2)
        model_label = _clean_text(row.goods_model, 191)
        if model_label:
            model_sales_map[model_label] = model_sales_map.get(model_label, 0) + int(quantity or 0)
        for index, goal in enumerate(config["modelGoals"]):
            if _match_model_goal(row.goods_model, goal["models"]):
                model_quantities[index] += int(quantity or 0)

    stages = config["stages"] or (
        [{
            "level": 1,
            "targetAmount": float(config["targetAmount"]),
            "rewardAmount": 0.0,
        }]
        if float(config["targetAmount"] or 0) > 0 else []
    )
    target_amount = float(config["targetAmount"] or 0)
    completion_ratio = round(actual_amount / target_amount, 4) if target_amount > 0 else 0.0
    stage_items: list[ShopTargetStageOut] = []
    achieved_stage_level = 0
    total_stage_reward = 0.0
    current_stage_target_amount = float(target_amount or 0)
    current_stage_reward_amount = 0.0
    if stages:
        current_stage_target_amount = float(stages[-1]["targetAmount"])
        current_stage_reward_amount = float(stages[-1]["rewardAmount"])
    for item in stages:
        achieved = actual_amount >= float(item["targetAmount"])
        if achieved:
            achieved_stage_level = max(achieved_stage_level, int(item["level"]))
            total_stage_reward = float(item["rewardAmount"])
        elif current_stage_target_amount == float(stages[-1]["targetAmount"]) or achieved_stage_level + 1 == int(item["level"]):
            current_stage_target_amount = float(item["targetAmount"])
            current_stage_reward_amount = float(item["rewardAmount"])
        stage_items.append(ShopTargetStageOut(
            level=int(item["level"]),
            targetAmount=float(item["targetAmount"]),
            rewardAmount=float(item["rewardAmount"]),
            achieved=achieved,
        ))

    if not stages and target_amount > 0:
        current_stage_target_amount = target_amount

    if not stages and target_amount <= 0:
        current_stage_label = "未设目标"
    elif achieved_stage_level >= len(stages) and stages:
        current_stage_label = f"已完成阶段 {achieved_stage_level}"
    else:
        current_stage_label = f"进行中 · 阶段 {max(1, achieved_stage_level + 1)}"

    contribution_items = [
        ShopTargetContributionOut(
            label=label,
            amount=round(amount, 2),
            ratio=round(amount / actual_amount, 4) if actual_amount > 0 else 0.0,
        )
        for label, amount in sorted(contribution_map.items(), key=lambda item: (-item[1], item[0]))
    ]

    model_goal_items: list[ShopTargetModelGoalOut] = []
    total_model_reward = 0.0
    for index, item in enumerate(config["modelGoals"]):
        completed_quantity = int(model_quantities[index] if index < len(model_quantities) else 0)
        achieved = completed_quantity > 0
        total_model_reward += completed_quantity * float(item["rewardAmount"] or 0)
        model_goal_items.append(ShopTargetModelGoalOut(
            goodsId=int(item["goodsId"]) if item.get("goodsId") else None,
            name=item["name"],
            modelDisplay=str(item.get("modelDisplay") or ""),
            brand=str(item.get("brand") or ""),
            series=str(item.get("series") or ""),
            barcode=str(item.get("barcode") or ""),
            models=list(item["models"]),
            targetQuantity=int(item["targetQuantity"] or 0),
            completedQuantity=completed_quantity,
            rewardAmount=float(item["rewardAmount"] or 0),
            achieved=achieved,
        ))

    return ShopTargetMonthOut(
        month=month,
        monthLabel=month_label,
        targetAmount=round(target_amount, 2),
        actualAmount=round(actual_amount, 2),
        completionRatio=completion_ratio,
        currentStageLevel=achieved_stage_level,
        currentStageLabel=current_stage_label,
        currentStageTargetAmount=round(current_stage_target_amount, 2),
        currentStageRewardAmount=round(current_stage_reward_amount, 2),
        totalStageReward=round(total_stage_reward, 2),
        totalModelReward=round(total_model_reward, 2),
        stages=stage_items,
        modelGoals=model_goal_items,
        contributions=contribution_items,
        modelSales=[
            ShopTargetModelSaleOut(label=label, quantity=quantity)
            for label, quantity in sorted(model_sales_map.items(), key=lambda item: (-item[1], item[0]))[:60]
        ],
    )


def _load_year_sales_rows(db: Session, *, shop: AqcShop, year: int) -> list[AqcSaleRecord]:
    year_start = datetime(year, 1, 1)
    year_end = datetime(year + 1, 1, 1)
    shop_name = _clean_text(shop.name, 255)
    return (
        db.execute(
            select(AqcSaleRecord)
            .where(
                AqcSaleRecord.sale_kind == "goods",
                AqcSaleRecord.sold_at >= year_start,
                AqcSaleRecord.sold_at < year_end,
                or_(
                    AqcSaleRecord.shop_id == int(shop.id),
                    AqcSaleRecord.shop_name == shop_name,
                ),
            )
            .order_by(AqcSaleRecord.sold_at.asc(), AqcSaleRecord.id.asc())
        )
        .scalars()
        .all()
    )


def _load_target_months(db: Session, *, shop_id: int, year: int) -> list[AqcShopTargetMonth]:
    return (
        db.execute(
            select(AqcShopTargetMonth)
            .where(AqcShopTargetMonth.shop_id == shop_id, AqcShopTargetMonth.year == year)
            .order_by(AqcShopTargetMonth.month_key.asc(), AqcShopTargetMonth.id.asc())
        )
        .scalars()
        .all()
    )


def _serialize_target_log(item: AqcShopTargetLog) -> ShopTargetLogItemOut:
    payload = _json_loads(item.details_json, {})
    highlights = payload.get("highlights") if isinstance(payload, dict) else []
    normalized = [str(line or "").strip() for line in (highlights if isinstance(highlights, list) else []) if str(line or "").strip()]
    return ShopTargetLogItemOut(
        id=int(item.id),
        operatorName=_clean_text(item.operator_name, 80),
        createdAt=to_iso(item.created_at) or "",
        summary=_clean_text(item.summary, 255),
        highlights=normalized[:12],
    )


def _load_recent_logs(db: Session, *, shop_id: int) -> list[ShopTargetLogItemOut]:
    rows = (
        db.execute(
            select(AqcShopTargetLog)
            .where(AqcShopTargetLog.shop_id == shop_id)
            .order_by(AqcShopTargetLog.created_at.desc(), AqcShopTargetLog.id.desc())
            .limit(SHOP_TARGET_LOG_LIMIT)
        )
        .scalars()
        .all()
    )
    return [_serialize_target_log(item) for item in rows]


def _serialize_preset(item: AqcShopTargetPreset) -> ShopTargetPresetOut:
    return ShopTargetPresetOut(
        id=int(item.id),
        name=_clean_text(item.name, 120) or "未命名型号组",
        models=_normalize_models(_json_loads(item.models_json, [])),
        createdAt=to_iso(item.created_at) or "",
        updatedAt=to_iso(item.updated_at) or "",
    )


def _build_month_rows_map(rows: list[AqcSaleRecord]) -> dict[str, list[AqcSaleRecord]]:
    grouped: dict[str, list[AqcSaleRecord]] = {}
    for row in rows:
        month = row.sold_at.strftime("%Y-%m") if row.sold_at else ""
        if not month:
            continue
        grouped.setdefault(month, []).append(row)
    return grouped


def _normalize_save_month(item) -> dict:
    month = _clean_text(item.month, 7)
    stages = _normalize_stage_items(item.stages)
    model_goals = _normalize_model_goals(item.modelGoals)
    target_amount = max(
        float(_to_decimal(item.targetAmount)),
        max((float(stage.get("targetAmount") or 0) for stage in stages), default=0.0),
    )
    return {
        "month": month,
        "targetAmount": target_amount,
        "stages": stages,
        "modelGoals": model_goals,
    }


def _build_month_config_snapshot(config: dict) -> dict:
    return {
        "targetAmount": round(float(config.get("targetAmount") or 0), 2),
        "stages": [
            {
                "targetAmount": round(float(item.get("targetAmount") or 0), 2),
                "rewardAmount": round(float(item.get("rewardAmount") or 0), 2),
            }
            for item in config.get("stages") or []
        ],
        "modelGoals": [
            {
                "goodsId": int(item.get("goodsId") or 0) or None,
                "name": _clean_text(item.get("name"), 120),
                "modelDisplay": _clean_text(item.get("modelDisplay"), 120),
                "brand": _clean_text(item.get("brand"), 120),
                "series": _clean_text(item.get("series"), 120),
                "barcode": _clean_text(item.get("barcode"), 120),
                "models": list(item.get("models") or []),
                "targetQuantity": int(item.get("targetQuantity") or 0),
                "rewardAmount": round(float(item.get("rewardAmount") or 0), 2),
            }
            for item in config.get("modelGoals") or []
        ],
    }


def _config_has_content(config: dict) -> bool:
    return bool(
        float(config.get("targetAmount") or 0) > 0
        or (config.get("stages") or [])
        or (config.get("modelGoals") or [])
    )


def _build_change_highlights(before_map: dict[str, dict], after_map: dict[str, dict]) -> list[str]:
    highlights: list[str] = []
    all_months = sorted(set(before_map) | set(after_map))
    for month in all_months:
        before = before_map.get(month)
        after = after_map.get(month)
        if before == after:
            continue
        month_label = f"{month[5:7]}月"
        if before and not after:
            highlights.append(f"{month_label} 已清空目标配置")
            continue
        if after and not before:
            highlights.append(
                f"{month_label} 新增目标，阶段 {len(after.get('stages') or [])} 档，型号 {len(after.get('modelGoals') or [])} 个"
            )
            continue
        highlights.append(
            f"{month_label} 更新目标，阶段 {len(after.get('stages') or [])} 档，型号 {len(after.get('modelGoals') or [])} 个"
        )
    return highlights[:20]


def _collect_changed_months(before_map: dict[str, dict], after_map: dict[str, dict]) -> list[str]:
    result: list[str] = []
    for month in sorted(set(before_map) | set(after_map)):
        if before_map.get(month) == after_map.get(month):
            continue
        result.append(month)
    return result


def _parse_log_filter_datetime(value: str | None, *, end: bool = False) -> datetime | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        try:
            parsed = datetime.strptime(clean, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
    if len(clean) <= 10 and end:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


@router.get("/{shop_id}", response_model=ShopTargetPageResponse)
def get_shop_targets(
    shop_id: int,
    year: int | None = Query(default=None, ge=2000, le=2100),
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    if year is None:
        year = datetime.now(SHANGHAI_TZ).year
    shop = _load_target_shop(db, user, shop_id)
    rows = _load_target_months(db, shop_id=int(shop.id), year=year)
    row_map = {str(item.month_key): item for item in rows}
    sale_rows = _load_year_sales_rows(db, shop=shop, year=year)
    month_sales_map = _build_month_rows_map(sale_rows)
    months: list[ShopTargetMonthOut] = []
    for month in range(1, 13):
        month_token = _month_key(year, month)
        config = _serialize_target_month_config(row_map.get(month_token))
        months.append(
            _build_month_sales_metrics(
                month_sales_map.get(month_token, []),
                config,
                month=month_token,
                month_label=_month_label(year, month),
            )
        )

    return ShopTargetPageResponse(
        success=True,
        shop=ShopScheduleShopOut(
            id=int(shop.id),
            name=_clean_text(shop.name, 255),
            managerName=_clean_text(shop.manager_name, 120) or None,
            staffCount=len(getattr(shop, "assigned_users", []) or []),
        ),
        year=year,
        yearLabel=f"{year} 年",
        canEdit=_can_edit_target(user),
        months=months,
        presets=[],
        logs=_load_recent_logs(db, shop_id=int(shop.id)),
    )


@router.put("/{shop_id}", response_model=ShopTargetSaveResponse)
def save_shop_targets(
    shop_id: int,
    payload: ShopTargetSaveRequest,
    user: AqcUser = Depends(require_permissions("shops.write")),
    db: Session = Depends(get_db),
):
    shop = _load_target_shop(db, user, shop_id)
    if not _can_edit_target(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权编辑店铺目标")

    existing_rows = _load_target_months(db, shop_id=int(shop.id), year=int(payload.year))
    existing_map = {str(item.month_key): item for item in existing_rows}
    before_map: dict[str, dict] = {}
    normalized_payload_map: dict[str, dict | None] = {}
    for item in payload.months:
        normalized = _normalize_save_month(item)
        month = normalized["month"]
        if not month.startswith(f"{payload.year}-"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"目标月份超出当前年份：{month}")
        current = existing_map.get(month)
        before_map[month] = _build_month_config_snapshot(_serialize_target_month_config(current)) if current else {}
        normalized_payload_map[month] = normalized if _config_has_content(normalized) else None

    for month, next_config in normalized_payload_map.items():
        current = existing_map.get(month)
        if next_config is None:
            if current is not None:
                db.delete(current)
            continue
        if current is None:
            current = AqcShopTargetMonth(
                shop_id=int(shop.id),
                year=int(payload.year),
                month_key=month,
            )
            db.add(current)
        current.target_amount = _to_decimal(next_config["targetAmount"])
        current.stages_json = json.dumps(_build_month_config_snapshot(next_config)["stages"], ensure_ascii=False)
        current.model_goals_json = json.dumps(_build_month_config_snapshot(next_config)["modelGoals"], ensure_ascii=False)
        current.updated_by = user.id

    db.flush()

    refreshed_rows = _load_target_months(db, shop_id=int(shop.id), year=int(payload.year))
    refreshed_map = {str(item.month_key): item for item in refreshed_rows}
    after_map = {
        month_key: (
            _build_month_config_snapshot(_serialize_target_month_config(refreshed_map.get(month_key)))
            if refreshed_map.get(month_key) is not None else {}
        )
        for month_key in normalized_payload_map
    }
    highlights = _build_change_highlights(before_map, after_map)
    changed_months = _collect_changed_months(before_map, after_map)
    if highlights:
        log = AqcShopTargetLog(
            shop_id=int(shop.id),
            year=int(payload.year),
            operator_id=user.id,
            operator_name=_clean_text(user.display_name or user.username, 80),
            summary=f"保存 {payload.year} 目标，调整 {len(highlights)} 个月",
            details_json=json.dumps({
                "highlights": highlights,
                "year": int(payload.year),
                "months": changed_months,
            }, ensure_ascii=False),
        )
        db.add(log)

    db.commit()
    return ShopTargetSaveResponse(
        success=True,
        message="目标已保存",
        logs=_load_recent_logs(db, shop_id=int(shop.id)),
    )


@router.get("/{shop_id}/logs", response_model=ShopTargetLogListResponse)
def list_shop_target_logs(
    shop_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    month: str | None = Query(default=None),
    date_start: str | None = Query(default=None),
    date_end: str | None = Query(default=None),
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    shop = _load_target_shop(db, user, shop_id)
    stmt = select(AqcShopTargetLog).where(AqcShopTargetLog.shop_id == shop.id)
    count_stmt = select(func.count(AqcShopTargetLog.id)).where(AqcShopTargetLog.shop_id == shop.id)

    clean_keyword = str(q or "").strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        condition = or_(
            AqcShopTargetLog.summary.like(like),
            AqcShopTargetLog.operator_name.like(like),
            AqcShopTargetLog.details_json.like(like),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    clean_month = str(month or "").strip()
    if clean_month:
        month_label = f"{clean_month[5:7]}月" if len(clean_month) == 7 and clean_month[4] == "-" else clean_month
        month_condition = or_(
            AqcShopTargetLog.details_json.like(f'%"{clean_month}"%'),
            AqcShopTargetLog.details_json.like(f"%{month_label}%"),
        )
        stmt = stmt.where(month_condition)
        count_stmt = count_stmt.where(month_condition)

    parsed_date_start = _parse_log_filter_datetime(date_start)
    if parsed_date_start is not None:
        stmt = stmt.where(AqcShopTargetLog.created_at >= parsed_date_start)
        count_stmt = count_stmt.where(AqcShopTargetLog.created_at >= parsed_date_start)

    parsed_date_end = _parse_log_filter_datetime(date_end, end=True)
    if parsed_date_end is not None:
        stmt = stmt.where(AqcShopTargetLog.created_at < parsed_date_end)
        count_stmt = count_stmt.where(AqcShopTargetLog.created_at < parsed_date_end)

    total = int(db.execute(count_stmt).scalar() or 0)
    rows = (
        db.execute(
            stmt.order_by(AqcShopTargetLog.created_at.desc(), AqcShopTargetLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return ShopTargetLogListResponse(
        success=True,
        total=total,
        logs=[_serialize_target_log(item) for item in rows],
    )


@router.get("/{shop_id}/presets", response_model=ShopTargetPresetListResponse)
def list_shop_target_presets(
    shop_id: int,
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    shop = _load_target_shop(db, user, shop_id)
    rows = (
        db.execute(
            select(AqcShopTargetPreset)
            .where(AqcShopTargetPreset.shop_id == int(shop.id))
            .order_by(AqcShopTargetPreset.updated_at.desc(), AqcShopTargetPreset.id.desc())
        )
        .scalars()
        .all()
    )
    return ShopTargetPresetListResponse(
        success=True,
        presets=[_serialize_preset(item) for item in rows],
    )


@router.post("/{shop_id}/presets", response_model=ShopTargetPresetListResponse)
def save_shop_target_preset(
    shop_id: int,
    payload: ShopTargetPresetCreateRequest,
    user: AqcUser = Depends(require_permissions("shops.write")),
    db: Session = Depends(get_db),
):
    shop = _load_target_shop(db, user, shop_id)
    if not _can_edit_target(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权编辑店铺目标")
    models = _normalize_models(payload.models)
    if not models:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请至少填写一个型号")
    name = _clean_text(payload.name, 120) or _infer_preset_name(models)
    preset = (
        db.execute(
            select(AqcShopTargetPreset)
            .where(AqcShopTargetPreset.shop_id == int(shop.id), AqcShopTargetPreset.name == name)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if preset is None:
        preset = AqcShopTargetPreset(
            shop_id=int(shop.id),
            name=name,
            created_by=user.id,
        )
        db.add(preset)
    preset.models_json = json.dumps(models, ensure_ascii=False)
    db.commit()
    return list_shop_target_presets(shop_id=shop_id, user=user, db=db)


@router.delete("/{shop_id}/presets/{preset_id}", response_model=ShopTargetPresetListResponse)
def delete_shop_target_preset(
    shop_id: int,
    preset_id: int,
    user: AqcUser = Depends(require_permissions("shops.write")),
    db: Session = Depends(get_db),
):
    shop = _load_target_shop(db, user, shop_id)
    if not _can_edit_target(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权编辑店铺目标")
    preset = (
        db.execute(
            select(AqcShopTargetPreset)
            .where(AqcShopTargetPreset.shop_id == int(shop.id), AqcShopTargetPreset.id == preset_id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标型号组不存在")
    db.execute(delete(AqcShopTargetPreset).where(AqcShopTargetPreset.id == int(preset.id)))
    db.commit()
    return list_shop_target_presets(shop_id=shop_id, user=user, db=db)

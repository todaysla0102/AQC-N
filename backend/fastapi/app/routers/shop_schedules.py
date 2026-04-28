from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import AQC_ROLE_LABELS, SHANGHAI_TZ, get_aqc_role_key, require_permissions, scoped_shop_conditions, to_iso, user_shop_ids
from ..models import AqcShop, AqcShopScheduleEntry, AqcShopScheduleLog, AqcUser
from ..schemas import (
    MyScheduleSummaryResponse,
    MyScheduleTomorrowShiftOut,
    ShopScheduleAssignmentOut,
    ShopScheduleConflictWarningOut,
    ShopScheduleDayOut,
    ShopScheduleLogItemOut,
    ShopScheduleLogListResponse,
    ShopSchedulePageResponse,
    ShopScheduleSaveRequest,
    ShopScheduleSaveResponse,
    ShopScheduleShiftSlotOut,
    ShopScheduleShopOut,
    ShopScheduleStaffOut,
    ShopScheduleStaffGroupOut,
    ShopScheduleStaffStatOut,
    ShopScheduleStatEntryOut,
)


router = APIRouter(prefix="/shop-schedules", tags=["shop-schedules"])

SHIFT_ITEMS = [
    ("morning", "早班"),
    ("extra", "插班"),
    ("night", "晚班"),
]
SHIFT_LABELS = {key: label for key, label in SHIFT_ITEMS}
SHIFT_KEYS = tuple(SHIFT_LABELS.keys())
REQUIRED_SHIFT_KEYS = {"morning", "night"}
SCHEDULE_LOG_RETENTION_DAYS = 92
PERIOD_LABELS = {
    "today": "今日",
    "yesterday": "昨日",
    "this_week": "本周",
    "last_week": "上周",
    "this_month": "本月",
    "last_month": "上月",
    "this_year": "本年",
    "last_year": "去年",
}


def _store_condition():
    return or_(
        AqcShop.legacy_id.is_not(None),
        AqcShop.shop_type.is_(None),
        AqcShop.shop_type == 0,
    )


def _today_local() -> date:
    return datetime.now(SHANGHAI_TZ).date()


def _parse_iso_date(raw_value: str | None) -> date | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_log_filter_datetime(raw_value: str | None, *, end: bool = False) -> datetime | None:
    parsed = _parse_iso_date(raw_value)
    if parsed is None:
        return None
    base = datetime(parsed.year, parsed.month, parsed.day)
    return base + timedelta(days=1) if end else base


def _parse_month_token(raw_value: str | None) -> date:
    text = str(raw_value or "").strip()
    if not text:
        today = _today_local()
        return date(today.year, today.month, 1)
    try:
        parsed = datetime.strptime(text, "%Y-%m").date()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="月份格式应为 YYYY-MM") from exc
    return date(parsed.year, parsed.month, 1)


def _month_bounds(month_start: date) -> tuple[date, date]:
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)
    return month_start, next_month_start - timedelta(days=1)


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _month_key(month_start: date) -> str:
    return month_start.strftime("%Y-%m")


def _month_label(month_start: date) -> str:
    return f"{month_start.year} 年 {month_start.month} 月"


def _grid_bounds(month_start: date, month_end: date) -> tuple[date, date]:
    month_start_weekday = (month_start.weekday() + 1) % 7
    month_end_weekday = (month_end.weekday() + 1) % 7
    grid_start = month_start - timedelta(days=month_start_weekday)
    grid_end = month_end + timedelta(days=6 - month_end_weekday)
    return grid_start, grid_end


def _iter_dates(date_from: date, date_to: date):
    cursor = date_from
    while cursor <= date_to:
        yield cursor
        cursor += timedelta(days=1)


def _role_name_for_user(user: AqcUser | None) -> str:
    if user is None:
        return ""
    return AQC_ROLE_LABELS.get(get_aqc_role_key(user), AQC_ROLE_LABELS["aqc_sales"])


def _is_schedule_editor(user: AqcUser, shop_id: int) -> bool:
    role_key = get_aqc_role_key(user)
    if role_key == "aqc_admin":
        return True
    if role_key != "aqc_manager":
        return False
    return shop_id in user_shop_ids(user)


def _load_schedule_shop(db: Session, user: AqcUser, shop_id: int) -> AqcShop:
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
    if not bool(getattr(shop, "schedule_enabled", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前店铺未开启排班功能")
    return shop


def _load_month_entries(db: Session, *, shop_id: int, month_key: str) -> list[AqcShopScheduleEntry]:
    return (
        db.execute(
            select(AqcShopScheduleEntry)
            .where(AqcShopScheduleEntry.shop_id == shop_id, AqcShopScheduleEntry.month_key == month_key)
            .order_by(
                AqcShopScheduleEntry.work_date.asc(),
                AqcShopScheduleEntry.shift_type.asc(),
                AqcShopScheduleEntry.id.asc(),
            )
        )
        .scalars()
        .all()
    )


def _load_recent_logs(db: Session, *, shop_id: int, limit: int = 20) -> list[AqcShopScheduleLog]:
    return (
        db.execute(
            select(AqcShopScheduleLog)
            .where(AqcShopScheduleLog.shop_id == shop_id)
            .order_by(AqcShopScheduleLog.created_at.desc(), AqcShopScheduleLog.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def _load_schedule_group_shops(db: Session) -> list[AqcShop]:
    return (
        db.execute(
            select(AqcShop)
            .where(_store_condition(), AqcShop.schedule_enabled.is_(True))
            .order_by(AqcShop.id.asc())
        )
        .scalars()
        .all()
    )


def _serialize_schedule_log(item: AqcShopScheduleLog) -> ShopScheduleLogItemOut:
    return ShopScheduleLogItemOut(
        id=int(item.id),
        operatorName=str(item.operator_name or ""),
        createdAt=to_iso(item.created_at) or "",
        summary=str(item.summary or ""),
        highlights=_parse_log_highlights(item.details_json)[:12],
    )


def _prune_expired_logs(db: Session, *, reference_time: datetime | None = None) -> None:
    cutoff = (reference_time or datetime.now(SHANGHAI_TZ)).replace(tzinfo=None) - timedelta(days=SCHEDULE_LOG_RETENTION_DAYS)
    db.execute(delete(AqcShopScheduleLog).where(AqcShopScheduleLog.created_at < cutoff))


def _staff_payload(
    *,
    user_id: int,
    username: str,
    display_name: str,
    role_name: str,
    is_manager: bool,
    is_active: bool,
    is_assigned: bool,
) -> dict:
    return {
        "id": int(user_id),
        "username": str(username or "").strip(),
        "displayName": str(display_name or "").strip() or str(username or "").strip() or f"账户 {user_id}",
        "roleName": str(role_name or "").strip(),
        "isManager": bool(is_manager),
        "isActive": bool(is_active),
        "isAssigned": bool(is_assigned),
    }


def _is_schedule_staff_role(role_key: str) -> bool:
    return role_key in {"aqc_admin", "aqc_sales", "aqc_manager"}


def _ordered_schedule_shops(schedule_shops: list[AqcShop], *, current_shop_id: int) -> list[AqcShop]:
    return sorted(
        schedule_shops,
        key=lambda item: (
            0 if int(item.id or 0) == int(current_shop_id) else 1,
            str(item.name or ""),
            int(item.id or 0),
        ),
    )


def _build_staff_map(
    db: Session,
    *,
    shop: AqcShop,
    entries: list[AqcShopScheduleEntry],
    schedule_shops: list[AqcShop],
) -> tuple[dict[int, dict], dict[int, list[int]]]:
    staff_map: dict[int, dict] = {}
    user_shop_map: dict[int, list[int]] = {}
    schedule_shop_ids = {int(item.id) for item in schedule_shops if int(item.id or 0) > 0}

    active_users = db.execute(
        select(AqcUser).where(AqcUser.is_active.is_(True))
    ).scalars().all()
    for user in active_users:
        role_key = get_aqc_role_key(user)
        if not _is_schedule_staff_role(role_key):
            continue
        assigned_shop_ids = [shop_id for shop_id in user_shop_ids(user) if shop_id in schedule_shop_ids]
        if not assigned_shop_ids:
            continue
        user_id = int(user.id)
        user_shop_map[user_id] = assigned_shop_ids
        staff_map[user_id] = _staff_payload(
            user_id=int(user.id),
            username=user.username or "",
            display_name=user.display_name or user.username or "",
            role_name=_role_name_for_user(user),
            is_manager=role_key == "aqc_manager",
            is_active=bool(user.is_active),
            is_assigned=shop.id in assigned_shop_ids,
        )

    existing_user_ids = {int(item.salesperson_id) for item in entries if int(item.salesperson_id or 0) > 0}
    missing_user_ids = sorted(user_id for user_id in existing_user_ids if user_id not in staff_map)
    if missing_user_ids:
        users = db.execute(select(AqcUser).where(AqcUser.id.in_(missing_user_ids))).scalars().all()
        loaded_user_map = {int(user.id): user for user in users}
        for user_id in missing_user_ids:
            user = loaded_user_map.get(user_id)
            if user is not None:
                role_key = get_aqc_role_key(user)
                assigned_shop_ids = [shop_id for shop_id in user_shop_ids(user) if shop_id in schedule_shop_ids]
                user_shop_map[user_id] = assigned_shop_ids or [shop.id]
                staff_map[user_id] = _staff_payload(
                    user_id=user_id,
                    username=user.username or "",
                    display_name=user.display_name or user.username or "",
                    role_name=_role_name_for_user(user),
                    is_manager=role_key == "aqc_manager",
                    is_active=bool(user.is_active) and role_key != "aqc_departed",
                    is_assigned=shop.id in assigned_shop_ids,
                )
                continue
            snapshot = next((item for item in entries if int(item.salesperson_id or 0) == user_id), None)
            if snapshot is None:
                continue
            user_shop_map[user_id] = [shop.id]
            staff_map[user_id] = _staff_payload(
                user_id=user_id,
                username=snapshot.salesperson_username or "",
                display_name=snapshot.salesperson_name or snapshot.salesperson_username or f"账户 {user_id}",
                role_name="历史排班",
                is_manager=False,
                is_active=False,
                is_assigned=False,
            )

    return staff_map, user_shop_map


def _load_entries_for_staff_stats(
    db: Session,
    *,
    staff_user_ids: list[int],
    month_start: date,
    month_end: date,
) -> list[AqcShopScheduleEntry]:
    normalized_ids = sorted({int(user_id) for user_id in staff_user_ids if int(user_id) > 0})
    if not normalized_ids:
        return []
    start_dt = datetime(month_start.year, month_start.month, month_start.day)
    end_dt = datetime(month_end.year, month_end.month, month_end.day, 23, 59, 59)
    return (
        db.execute(
            select(AqcShopScheduleEntry)
            .where(
                AqcShopScheduleEntry.salesperson_id.in_(normalized_ids),
                AqcShopScheduleEntry.work_date >= start_dt,
                AqcShopScheduleEntry.work_date <= end_dt,
            )
            .order_by(
                AqcShopScheduleEntry.work_date.asc(),
                AqcShopScheduleEntry.shift_type.asc(),
                AqcShopScheduleEntry.id.asc(),
            )
        )
        .scalars()
        .all()
    )


def _sorted_staff_rows(staff_map: dict[int, dict]) -> list[dict]:
    return sorted(
        staff_map.values(),
        key=lambda item: (
            0 if item.get("isAssigned") else 1,
            0 if item.get("isManager") else 1,
            0 if item.get("isActive") else 1,
            str(item.get("displayName") or item.get("username") or ""),
            int(item.get("id") or 0),
        ),
    )


def _build_staff_groups(
    staff_map: dict[int, dict],
    *,
    user_shop_map: dict[int, list[int]],
    schedule_shops: list[AqcShop],
    current_shop_id: int,
) -> list[ShopScheduleStaffGroupOut]:
    sorted_staff_rows = _sorted_staff_rows(staff_map)
    groups: list[ShopScheduleStaffGroupOut] = []
    for shop in _ordered_schedule_shops(schedule_shops, current_shop_id=current_shop_id):
        shop_id = int(shop.id or 0)
        members = [
            ShopScheduleStaffOut(
                id=int(item["id"]),
                username=item["username"],
                displayName=item["displayName"],
                roleName=item["roleName"],
                isManager=item["isManager"],
                isActive=item["isActive"],
                isAssigned=item["isAssigned"],
            )
            for item in sorted_staff_rows
            if shop_id in user_shop_map.get(int(item["id"]), [])
        ]
        if not members and shop_id != current_shop_id:
            continue
        groups.append(
            ShopScheduleStaffGroupOut(
                shopId=shop_id,
                shopName=str(shop.name or ""),
                isCurrentShop=shop_id == current_shop_id,
                staff=members,
            )
        )
    return groups


def _empty_shift_map() -> dict[str, list[int]]:
    return {key: [] for key in SHIFT_KEYS}


def _build_schedule_map(entries: list[AqcShopScheduleEntry]) -> dict[str, dict[str, list[int]]]:
    result: dict[str, dict[str, list[int]]] = {}
    for item in entries:
        work_day = item.work_date.date().isoformat()
        day_map = result.setdefault(work_day, _empty_shift_map())
        shift_key = str(item.shift_type or "").strip()
        if shift_key not in SHIFT_LABELS:
            continue
        salesperson_id = int(item.salesperson_id or 0)
        if salesperson_id <= 0 or salesperson_id in day_map[shift_key]:
            continue
        day_map[shift_key].append(salesperson_id)
    return result


def _build_day_slots(day_map: dict[str, list[int]], staff_map: dict[int, dict]) -> list[ShopScheduleShiftSlotOut]:
    slots: list[ShopScheduleShiftSlotOut] = []
    for shift_key, shift_label in SHIFT_ITEMS:
        assignments: list[ShopScheduleAssignmentOut] = []
        for user_id in day_map.get(shift_key, []):
            staff = staff_map.get(int(user_id))
            if staff is None:
                continue
            assignments.append(
                ShopScheduleAssignmentOut(
                    userId=int(staff["id"]),
                    displayName=staff["displayName"],
                    username=staff["username"],
                    roleName=staff["roleName"],
                    isManager=staff["isManager"],
                    isActive=staff["isActive"],
                    isAssigned=staff["isAssigned"],
                )
            )
        slots.append(
            ShopScheduleShiftSlotOut(
                key=shift_key,
                label=shift_label,
                assignments=assignments,
            )
        )
    return slots


def _collect_incomplete_days(schedule_map: dict[str, dict[str, list[int]]], month_start: date, month_end: date) -> list[str]:
    result: list[str] = []
    for current_day in _iter_dates(month_start, month_end):
        date_key = current_day.isoformat()
        day_map = schedule_map.get(date_key, _empty_shift_map())
        if not day_map.get("morning") or not day_map.get("night"):
            result.append(date_key)
    return result


def _build_staff_stats(
    staff_map: dict[int, dict],
    *,
    entries: list[AqcShopScheduleEntry],
    month_start: date,
    month_end: date,
) -> list[ShopScheduleStaffStatOut]:
    total_days = (month_end - month_start).days + 1
    shift_count_map = {user_id: 0 for user_id in staff_map}
    double_shift_map = {user_id: 0 for user_id in staff_map}
    work_day_map = {user_id: set() for user_id in staff_map}
    date_shift_map: dict[str, dict[str, set[int]]] = {}

    for item in entries:
        user_id = int(item.salesperson_id or 0)
        if user_id not in shift_count_map:
            continue
        shift_key = str(item.shift_type or "").strip()
        if shift_key not in SHIFT_LABELS:
            continue
        date_key = item.work_date.date().isoformat()
        shift_count_map[user_id] += 1
        work_day_map[user_id].add(date_key)
        day_map = date_shift_map.setdefault(date_key, {key: set() for key in SHIFT_KEYS})
        day_map.setdefault(shift_key, set()).add(user_id)

    for current_day in _iter_dates(month_start, month_end):
        date_key = current_day.isoformat()
        day_map = date_shift_map.get(date_key, {key: set() for key in SHIFT_KEYS})
        morning_users = set(day_map.get("morning", set()))
        night_users = set(day_map.get("night", set()))
        for user_id in morning_users.intersection(night_users):
            if user_id in double_shift_map:
                double_shift_map[user_id] += 1

    rows: list[ShopScheduleStaffStatOut] = []
    for staff in _sorted_staff_rows(staff_map):
        user_id = int(staff["id"])
        work_days = len(work_day_map.get(user_id, set()))
        rows.append(
            ShopScheduleStaffStatOut(
                userId=user_id,
                displayName=staff["displayName"],
                username=staff["username"],
                roleName=staff["roleName"],
                isManager=staff["isManager"],
                isActive=staff["isActive"],
                isAssigned=staff["isAssigned"],
                shiftCount=int(shift_count_map.get(user_id, 0)),
                doubleShiftDays=int(double_shift_map.get(user_id, 0)),
                workDays=work_days,
                restDays=max(total_days - work_days, 0),
            )
        )
    return rows


def _serialize_staff_stat_entries(
    entries: list[AqcShopScheduleEntry],
    *,
    shop_name_map: dict[int, str],
) -> list[ShopScheduleStatEntryOut]:
    result: list[ShopScheduleStatEntryOut] = []
    for item in entries:
        shift_key = str(item.shift_type or "").strip()
        if shift_key not in SHIFT_LABELS:
            continue
        result.append(
            ShopScheduleStatEntryOut(
                shopId=int(item.shop_id or 0),
                shopName=str(shop_name_map.get(int(item.shop_id or 0), "") or ""),
                userId=int(item.salesperson_id or 0),
                date=item.work_date.date().isoformat(),
                shiftKey=shift_key,
            )
        )
    return result


def _build_conflict_warnings(
    db: Session,
    *,
    current_shop_id: int,
    month_start: date,
    month_end: date,
    next_map: dict[str, dict[str, list[int]]],
    staff_map: dict[int, dict],
) -> list[ShopScheduleConflictWarningOut]:
    next_assignments = {
        (date_key, shift_key, int(user_id))
        for date_key, day_map in next_map.items()
        for shift_key in SHIFT_KEYS
        for user_id in day_map.get(shift_key, [])
        if int(user_id) > 0
    }
    if not next_assignments:
        return []

    user_ids = sorted({user_id for _, _, user_id in next_assignments})
    start_dt = datetime(month_start.year, month_start.month, month_start.day)
    end_dt = datetime(month_end.year, month_end.month, month_end.day, 23, 59, 59)
    rows = db.execute(
        select(AqcShopScheduleEntry, AqcShop)
        .join(AqcShop, AqcShop.id == AqcShopScheduleEntry.shop_id)
        .where(
            AqcShopScheduleEntry.shop_id != int(current_shop_id),
            AqcShopScheduleEntry.salesperson_id.in_(user_ids),
            AqcShopScheduleEntry.work_date >= start_dt,
            AqcShopScheduleEntry.work_date <= end_dt,
        )
        .order_by(
            AqcShopScheduleEntry.work_date.asc(),
            AqcShopScheduleEntry.shift_type.asc(),
            AqcShopScheduleEntry.shop_id.asc(),
            AqcShopScheduleEntry.salesperson_id.asc(),
        )
    ).all()

    warnings: list[ShopScheduleConflictWarningOut] = []
    seen: set[tuple[int, str, str, int]] = set()
    for item, other_shop in rows:
        shift_key = str(item.shift_type or "").strip()
        if shift_key not in SHIFT_LABELS:
            continue
        date_key = item.work_date.date().isoformat()
        user_id = int(item.salesperson_id or 0)
        if (date_key, shift_key, user_id) not in next_assignments:
            continue
        warning_key = (user_id, date_key, shift_key, int(other_shop.id or 0))
        if warning_key in seen:
            continue
        seen.add(warning_key)
        staff = staff_map.get(user_id, {})
        warnings.append(
            ShopScheduleConflictWarningOut(
                userId=user_id,
                displayName=str(staff.get("displayName") or item.salesperson_name or item.salesperson_username or f"账户 {user_id}"),
                roleName=str(staff.get("roleName") or ""),
                date=date_key,
                shiftKey=shift_key,
                shiftLabel=SHIFT_LABELS.get(shift_key, "班次"),
                shopId=int(other_shop.id or 0),
                shopName=str(other_shop.name or ""),
            )
        )
    return warnings


def _normalize_schedule_payload(
    payload: ShopScheduleSaveRequest,
    *,
    month_start: date,
    month_end: date,
) -> dict[str, dict[str, list[int]]]:
    result: dict[str, dict[str, list[int]]] = {}
    for item in payload.days:
        work_day = _parse_iso_date(item.date)
        if work_day is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"排班日期格式无效：{item.date}")
        if work_day < month_start or work_day > month_end:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"排班日期超出当前月份：{item.date}")
        date_key = work_day.isoformat()
        result[date_key] = {
            "morning": list(item.morning),
            "extra": list(item.extra),
            "night": list(item.night),
        }

    for current_day in _iter_dates(month_start, month_end):
        date_key = current_day.isoformat()
        result.setdefault(date_key, _empty_shift_map())
    return result


def _staff_name_map(staff_map: dict[int, dict]) -> dict[int, str]:
    return {
        int(user_id): str(item.get("displayName") or item.get("username") or f"账户 {user_id}")
        for user_id, item in staff_map.items()
    }


def _build_log_details(
    *,
    month_key: str,
    previous_map: dict[str, dict[str, list[int]]],
    next_map: dict[str, dict[str, list[int]]],
    name_map: dict[int, str],
    incomplete_days: list[str],
) -> tuple[str, list[str], int]:
    highlight_lines: list[str] = []
    changed_days = 0
    added_count = 0
    removed_count = 0

    all_days = sorted(set(previous_map.keys()) | set(next_map.keys()))
    for date_key in all_days:
        day_changed = False
        fragments: list[str] = []
        previous_day = previous_map.get(date_key, _empty_shift_map())
        next_day = next_map.get(date_key, _empty_shift_map())
        for shift_key, shift_label in SHIFT_ITEMS:
            previous_ids = set(previous_day.get(shift_key, []))
            next_ids = set(next_day.get(shift_key, []))
            added_ids = sorted(next_ids - previous_ids)
            removed_ids = sorted(previous_ids - next_ids)
            if not added_ids and not removed_ids:
                continue
            day_changed = True
            added_count += len(added_ids)
            removed_count += len(removed_ids)
            parts: list[str] = []
            if added_ids:
                parts.append(f"+{'、'.join(name_map.get(user_id, f'账户 {user_id}') for user_id in added_ids)}")
            if removed_ids:
                parts.append(f"-{'、'.join(name_map.get(user_id, f'账户 {user_id}') for user_id in removed_ids)}")
            fragments.append(f"{shift_label} {' '.join(parts)}")
        if day_changed:
            changed_days += 1
            highlight_lines.append(f"{date_key[5:]} {'；'.join(fragments)}")

    if changed_days == 0:
        summary = f"保存 {month_key} 排班，未调整班次"
    else:
        summary = f"保存 {month_key} 排班，调整 {changed_days} 天，新增 {added_count} 班次，删除 {removed_count} 班次"
    if incomplete_days:
        summary += f"，其中 {len(incomplete_days)} 天未排满早晚班"
    return summary, highlight_lines, changed_days


def _parse_log_highlights(raw_value: str | None) -> list[str]:
    text = str(raw_value or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception:
        return []
    highlights = payload.get("highlights")
    if not isinstance(highlights, list):
        return []
    return [str(item or "").strip() for item in highlights if str(item or "").strip()]


def _resolve_summary_range(
    *,
    period: str | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, str, str, date, date]:
    custom_start = _parse_iso_date(date_from)
    custom_end = _parse_iso_date(date_to)
    if custom_start and custom_end:
        if custom_start > custom_end:
            custom_start, custom_end = custom_end, custom_start
        return "custom", "自定义", custom_start.isoformat(), custom_end.isoformat(), custom_start, custom_end

    clean_period = str(period or "").strip()
    if clean_period not in PERIOD_LABELS:
        clean_period = "this_month"
    today = _today_local()

    if clean_period == "today":
        start = end = today
    elif clean_period == "yesterday":
        start = end = today - timedelta(days=1)
    elif clean_period == "this_week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif clean_period == "last_week":
        this_week_start = today - timedelta(days=today.weekday())
        end = this_week_start - timedelta(days=1)
        start = end - timedelta(days=end.weekday())
    elif clean_period == "last_month":
        current_month_start = date(today.year, today.month, 1)
        end = current_month_start - timedelta(days=1)
        start = date(end.year, end.month, 1)
    elif clean_period == "this_year":
        start, end = _year_bounds(today.year)
    elif clean_period == "last_year":
        start = date(today.year - 1, 1, 1)
        end = date(today.year - 1, 12, 31)
    else:
        start, end = _month_bounds(date(today.year, today.month, 1))

    return clean_period, PERIOD_LABELS.get(clean_period, "本月"), start.isoformat(), end.isoformat(), start, end


@router.get("/me/summary", response_model=MyScheduleSummaryResponse)
def get_my_schedule_summary(
    period: str | None = Query(default="this_month"),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    resolved_period, period_label, start_text, end_text, range_start, range_end = _resolve_summary_range(
        period=period,
        date_from=date_from,
        date_to=date_to,
    )
    start_dt = datetime(range_start.year, range_start.month, range_start.day)
    end_dt = datetime(range_end.year, range_end.month, range_end.day, 23, 59, 59)

    rows = (
        db.execute(
            select(AqcShopScheduleEntry)
            .where(
                AqcShopScheduleEntry.salesperson_id == int(user.id),
                AqcShopScheduleEntry.work_date >= start_dt,
                AqcShopScheduleEntry.work_date <= end_dt,
            )
            .order_by(AqcShopScheduleEntry.work_date.asc(), AqcShopScheduleEntry.shift_type.asc())
        )
        .scalars()
        .all()
    )
    shift_count = len(rows)
    work_days = len({item.work_date.date().isoformat() for item in rows})

    tomorrow = _today_local() + timedelta(days=1)
    tomorrow_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
    tomorrow_rows = (
        db.execute(
            select(AqcShopScheduleEntry, AqcShop)
            .join(AqcShop, AqcShop.id == AqcShopScheduleEntry.shop_id)
            .where(
                AqcShopScheduleEntry.salesperson_id == int(user.id),
                AqcShopScheduleEntry.work_date == tomorrow_dt,
            )
            .order_by(AqcShopScheduleEntry.shop_id.asc(), AqcShopScheduleEntry.shift_type.asc())
        )
        .all()
    )
    tomorrow_shifts = [
        MyScheduleTomorrowShiftOut(
            shopId=int(shop.id),
            shopName=str(shop.name or ""),
            shiftType=str(item.shift_type or "morning"),
            shiftLabel=SHIFT_LABELS.get(str(item.shift_type or "morning"), "排班"),
        )
        for item, shop in tomorrow_rows
        if str(item.shift_type or "") in SHIFT_LABELS
    ]

    return {
        "success": True,
        "period": resolved_period,
        "periodLabel": period_label,
        "dateFrom": start_text,
        "dateTo": end_text,
        "shiftCount": shift_count,
        "workDays": work_days,
        "tomorrowShifts": tomorrow_shifts,
    }


@router.get("/{shop_id}", response_model=ShopSchedulePageResponse)
def get_shop_schedule_page(
    shop_id: int,
    month: str | None = Query(default=None),
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    shop = _load_schedule_shop(db, user, shop_id)
    schedule_shops = _load_schedule_group_shops(db)
    schedule_shop_name_map = {int(item.id): str(item.name or "") for item in schedule_shops if int(item.id or 0) > 0}
    month_start = _parse_month_token(month)
    month_key = _month_key(month_start)
    _month_start, month_end = _month_bounds(month_start)
    grid_start, grid_end = _grid_bounds(month_start, month_end)
    today = _today_local()

    entries = _load_month_entries(db, shop_id=shop.id, month_key=month_key)
    schedule_map = _build_schedule_map(entries)
    staff_map, staff_shop_map = _build_staff_map(db, shop=shop, entries=entries, schedule_shops=schedule_shops)
    staff_stat_entries = _load_entries_for_staff_stats(
        db,
        staff_user_ids=list(staff_map.keys()),
        month_start=month_start,
        month_end=month_end,
    )
    incomplete_days = _collect_incomplete_days(schedule_map, month_start, month_end)

    days: list[ShopScheduleDayOut] = []
    for current_day in _iter_dates(grid_start, grid_end):
        date_key = current_day.isoformat()
        day_map = schedule_map.get(date_key, _empty_shift_map())
        days.append(
            ShopScheduleDayOut(
                date=date_key,
                day=current_day.day,
                weekday=(current_day.weekday() + 1) % 7,
                isCurrentMonth=current_day.month == month_start.month,
                isToday=current_day == today,
                isIncomplete=current_day.month == month_start.month and date_key in incomplete_days,
                shiftSlots=_build_day_slots(day_map, staff_map),
            )
        )

    logs = _load_recent_logs(db, shop_id=shop.id)
    log_rows = [_serialize_schedule_log(item) for item in logs]

    manager_name = None
    if shop.manager_user and shop.manager_user.is_active:
        manager_name = (shop.manager_user.display_name or shop.manager_user.username or "").strip() or None
    if not manager_name:
        manager_name = (shop.manager_name or "").strip() or None

    return {
        "success": True,
        "canEdit": _is_schedule_editor(user, shop.id),
        "month": month_key,
        "monthLabel": _month_label(month_start),
        "shop": ShopScheduleShopOut(
            id=int(shop.id),
            name=str(shop.name or ""),
            managerName=manager_name,
            staffCount=sum(1 for item in staff_map.values() if bool(item.get("isAssigned"))),
        ),
        "staff": [
            ShopScheduleStaffOut(
                id=int(item["id"]),
                username=item["username"],
                displayName=item["displayName"],
                roleName=item["roleName"],
                isManager=item["isManager"],
                isActive=item["isActive"],
                isAssigned=item["isAssigned"],
            )
            for item in _sorted_staff_rows(staff_map)
        ],
        "staffGroups": _build_staff_groups(
            staff_map,
            user_shop_map=staff_shop_map,
            schedule_shops=schedule_shops,
            current_shop_id=int(shop.id),
        ),
        "staffStats": _build_staff_stats(
            staff_map,
            entries=staff_stat_entries,
            month_start=month_start,
            month_end=month_end,
        ),
        "staffStatEntries": _serialize_staff_stat_entries(
            staff_stat_entries,
            shop_name_map=schedule_shop_name_map,
        ),
        "days": days,
        "incompleteDays": incomplete_days,
        "logs": log_rows,
    }


@router.get("/{shop_id}/logs", response_model=ShopScheduleLogListResponse)
def list_shop_schedule_logs(
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
    shop = _load_schedule_shop(db, user, shop_id)

    stmt = select(AqcShopScheduleLog).where(AqcShopScheduleLog.shop_id == shop.id)
    count_stmt = select(func.count(AqcShopScheduleLog.id)).where(AqcShopScheduleLog.shop_id == shop.id)

    clean_keyword = str(q or "").strip()
    if clean_keyword:
        like = f"%{clean_keyword}%"
        condition = or_(
            AqcShopScheduleLog.summary.like(like),
            AqcShopScheduleLog.operator_name.like(like),
            AqcShopScheduleLog.month_key.like(like),
            AqcShopScheduleLog.details_json.like(like),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    clean_month = str(month or "").strip()
    if clean_month:
        stmt = stmt.where(AqcShopScheduleLog.month_key == clean_month)
        count_stmt = count_stmt.where(AqcShopScheduleLog.month_key == clean_month)

    parsed_date_start = _parse_log_filter_datetime(date_start)
    if parsed_date_start is not None:
        stmt = stmt.where(AqcShopScheduleLog.created_at >= parsed_date_start)
        count_stmt = count_stmt.where(AqcShopScheduleLog.created_at >= parsed_date_start)

    parsed_date_end = _parse_log_filter_datetime(date_end, end=True)
    if parsed_date_end is not None:
        stmt = stmt.where(AqcShopScheduleLog.created_at < parsed_date_end)
        count_stmt = count_stmt.where(AqcShopScheduleLog.created_at < parsed_date_end)

    total = int(db.execute(count_stmt).scalar() or 0)
    logs = (
        db.execute(
            stmt.order_by(AqcShopScheduleLog.created_at.desc(), AqcShopScheduleLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return {
        "success": True,
        "total": total,
        "logs": [_serialize_schedule_log(item) for item in logs],
    }


@router.put("/{shop_id}", response_model=ShopScheduleSaveResponse)
def save_shop_schedule(
    shop_id: int,
    payload: ShopScheduleSaveRequest,
    user: AqcUser = Depends(require_permissions("shops.read")),
    db: Session = Depends(get_db),
):
    shop = _load_schedule_shop(db, user, shop_id)
    if not _is_schedule_editor(user, shop.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号无权编辑该店铺排班")

    schedule_shops = _load_schedule_group_shops(db)
    month_start = _parse_month_token(payload.month)
    month_key = _month_key(month_start)
    if payload.month != month_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="排班月份格式无效")
    _month_start, month_end = _month_bounds(month_start)
    existing_entries = _load_month_entries(db, shop_id=shop.id, month_key=month_key)
    previous_map = _build_schedule_map(existing_entries)
    staff_map, _staff_shop_map = _build_staff_map(db, shop=shop, entries=existing_entries, schedule_shops=schedule_shops)
    allowed_user_ids = set(staff_map.keys())

    next_map = _normalize_schedule_payload(payload, month_start=month_start, month_end=month_end)
    invalid_user_ids = sorted(
        {
            int(user_id)
            for day_map in next_map.values()
            for shift_key in SHIFT_KEYS
            for user_id in day_map.get(shift_key, [])
            if int(user_id) not in allowed_user_ids
        }
    )
    if invalid_user_ids:
        return {
            "success": False,
            "message": f"以下账户当前不在本店铺排班名单中：{'、'.join(str(item) for item in invalid_user_ids)}",
        }

    incomplete_days = _collect_incomplete_days(next_map, month_start, month_end)
    conflict_warnings = _build_conflict_warnings(
        db,
        current_shop_id=int(shop.id),
        month_start=month_start,
        month_end=month_end,
        next_map=next_map,
        staff_map=staff_map,
    )
    if conflict_warnings and not bool(payload.confirmConflicts):
        return {
            "success": False,
            "needsConfirm": True,
            "message": f"检测到 {len(conflict_warnings)} 条跨店同班冲突，确认仍然保存吗？",
            "incompleteDays": incomplete_days,
            "changedDays": 0,
            "conflictWarnings": conflict_warnings,
        }

    name_map = _staff_name_map(staff_map)
    summary, highlight_lines, changed_days = _build_log_details(
        month_key=month_key,
        previous_map=previous_map,
        next_map=next_map,
        name_map=name_map,
        incomplete_days=incomplete_days,
    )

    db.execute(
        delete(AqcShopScheduleEntry).where(
            AqcShopScheduleEntry.shop_id == shop.id,
            AqcShopScheduleEntry.month_key == month_key,
        )
    )
    for current_day in _iter_dates(month_start, month_end):
        date_key = current_day.isoformat()
        day_map = next_map.get(date_key, _empty_shift_map())
        for shift_key in SHIFT_KEYS:
            for user_id in day_map.get(shift_key, []):
                staff = staff_map.get(int(user_id))
                if staff is None:
                    continue
                db.add(
                    AqcShopScheduleEntry(
                        shop_id=int(shop.id),
                        work_date=datetime(current_day.year, current_day.month, current_day.day),
                        month_key=month_key,
                        shift_type=shift_key,
                        salesperson_id=int(user_id),
                        salesperson_name=str(staff.get("displayName") or ""),
                        salesperson_username=str(staff.get("username") or ""),
                        created_by=int(user.id) if user.id is not None else None,
                    )
                )

    details_payload = {
        "month": month_key,
        "highlights": highlight_lines[:20],
        "incompleteDays": incomplete_days,
        "changedDays": changed_days,
    }
    log = AqcShopScheduleLog(
        shop_id=int(shop.id),
        month_key=month_key,
        operator_id=int(user.id) if user.id is not None else None,
        operator_name=str(user.display_name or user.username or ""),
        summary=summary[:255],
        details_json=json.dumps(details_payload, ensure_ascii=False),
    )
    db.add(log)
    _prune_expired_logs(db)
    db.commit()
    db.refresh(log)

    return {
        "success": True,
        "message": "排班已保存",
        "incompleteDays": incomplete_days,
        "changedDays": changed_days,
        "logId": int(log.id),
        "conflictWarnings": [],
    }

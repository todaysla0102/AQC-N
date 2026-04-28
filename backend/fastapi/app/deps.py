from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AqcAuthSession, AqcSaleRecord, AqcShop, AqcUser, AqcUserIdentity
from .security import hash_token


@dataclass
class CurrentAuth:
    user: AqcUser
    session: AqcAuthSession


AQC_ROLE_LABELS = {
    "aqc_admin": "管理员",
    "aqc_manager": "店长",
    "aqc_sales": "销售员",
    "aqc_engineer": "工程师",
    "aqc_departed": "离职人员",
}

AQC_ROLE_PERMISSIONS = {
    "aqc_admin": {
        "*",
        "sales.read",
        "sales.write",
        "sales.manage",
        "orders.read",
        "orders.upload",
        "orders.manage",
        "goods.read",
        "goods.write",
        "goods.manage",
        "workorders.read",
        "workorders.write",
        "workorders.approve",
        "shops.read",
        "shops.write",
        "shops.manage",
        "admin.manage_users",
        "admin.manage_roles",
        "admin.import_legacy",
    },
    "aqc_manager": {
        "sales.read",
        "sales.write",
        "orders.read",
        "goods.read",
        "workorders.read",
        "workorders.write",
        "shops.read",
    },
    "aqc_sales": {
        "sales.read",
        "sales.write",
        "orders.read",
        "goods.read",
        "workorders.read",
        "workorders.write",
        "shops.read",
    },
    "aqc_engineer": {
        "sales.read",
        "sales.write",
        "orders.read",
        "goods.read",
        "workorders.read",
        "workorders.write",
        "shops.read",
    },
    "aqc_departed": set(),
}

LEGACY_AQC_ROLE_MAP = {
    "aqc_super_admin": "aqc_admin",
    "aqc_admin": "aqc_admin",
    "aqc_operator": "aqc_manager",
    "aqc_sales": "aqc_sales",
    "aqc_engineer": "aqc_engineer",
    "aqc_viewer": "aqc_departed",
}

LEGACY_MANAGED_ROLE_SLUGS = {
    "admin",
    "sales-manager",
    "sales-entry",
    "sales-viewer",
    "goods-manager",
    "shop-manager",
}

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
UTC_TZ = timezone.utc


def to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    display_value = value
    if display_value.tzinfo is None:
        display_value = display_value.replace(tzinfo=UTC_TZ)
    return display_value.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%dT%H:%M:%S")


def to_local_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%dT%H:%M:%S")
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def sex_name(value: int | None) -> str:
    if value == 1:
        return "男"
    if value == 2:
        return "女"
    return ""


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def serialize_identity(identity: AqcUserIdentity | None, user: AqcUser) -> dict:
    if identity is None:
        return {
            "name": user.display_name,
            "avatar": user.avatar_url,
            "mobile": user.phone,
            "sex": 0,
            "sexName": "",
            "born": None,
            "province": None,
            "city": None,
            "area": None,
            "level": None,
            "vip": user.vip,
        }
    return {
        "name": identity.name or user.display_name,
        "avatar": identity.avatar or user.avatar_url,
        "mobile": identity.mobile or user.phone,
        "sex": identity.sex or 0,
        "sexName": sex_name(identity.sex),
        "born": identity.born,
        "province": identity.province,
        "city": identity.city,
        "area": identity.area,
        "level": identity.level,
        "vip": identity.vip if identity.vip is not None else user.vip,
    }


def parse_shop_ids(raw_value: object) -> list[int]:
    def ordered_unique(items: list[object]) -> list[int]:
        result: list[int] = []
        seen: set[int] = set()
        for item in items:
            if not str(item).isdigit():
                continue
            shop_id = int(item)
            if shop_id <= 0 or shop_id in seen:
                continue
            seen.add(shop_id)
            result.append(shop_id)
        return result

    if raw_value in (None, "", "null"):
        return []
    if isinstance(raw_value, int):
        return [raw_value] if raw_value > 0 else []
    if isinstance(raw_value, (list, tuple, set)):
        return ordered_unique(list(raw_value))

    text = str(raw_value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = [item.strip() for item in text.split(",") if item.strip()]
    if isinstance(parsed, int):
        return [parsed] if parsed > 0 else []
    if not isinstance(parsed, (list, tuple, set)):
        return []
    return ordered_unique(list(parsed))


def user_shop_ids(user: AqcUser) -> list[int]:
    ids = parse_shop_ids(getattr(user, "shop_ids", None))
    if user.shop_id is not None and int(user.shop_id) > 0:
        ids = [int(user.shop_id), *[item for item in ids if item != int(user.shop_id)]]
    return ids


def encode_shop_ids(shop_ids: list[int]) -> str:
    normalized = parse_shop_ids(shop_ids)
    return json.dumps(normalized, ensure_ascii=True)


def assign_user_shops(user: AqcUser, shop_ids: list[int]) -> list[int]:
    normalized = parse_shop_ids(shop_ids)
    user.shop_ids = encode_shop_ids(normalized)
    user.shop_id = normalized[0] if normalized else None
    return normalized


def serialize_user(user: AqcUser, db: Session | None = None) -> dict:
    roles, permissions = collect_user_roles_permissions(user)
    aqc_role_key = get_aqc_role_key(user)
    normalized_shop_ids = user_shop_ids(user)
    assigned_shop = user.assigned_shop
    shop_names = [assigned_shop.name] if assigned_shop and assigned_shop.name else []
    if db is not None and normalized_shop_ids:
        rows = db.execute(
            select(AqcShop.id, AqcShop.name).where(AqcShop.id.in_(normalized_shop_ids)).order_by(AqcShop.id.asc())
        ).all()
        shop_name_map = {int(row[0]): str(row[1] or "") for row in rows if row[1]}
        shop_names = [shop_name_map[shop_id] for shop_id in normalized_shop_ids if shop_id in shop_name_map]
    return {
        "id": user.id,
        "externalUserId": user.external_user_id,
        "username": user.username,
        "email": user.email,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
        "phone": user.phone,
        "role": user.role,
        "vip": user.vip,
        "vipLevel": user.vip_level,
        "userRuleId": user.user_rule_id,
        "authSource": user.auth_source,
        "createdAt": to_iso(user.created_at),
        "updatedAt": to_iso(user.updated_at),
        "lastLoginAt": to_iso(user.last_login_at),
        "aqcRoleKey": aqc_role_key,
        "aqcRoleName": AQC_ROLE_LABELS.get(aqc_role_key, AQC_ROLE_LABELS["aqc_sales"]),
        "shopId": user.shop_id,
        "shopIds": normalized_shop_ids,
        "shopName": assigned_shop.name if assigned_shop else "",
        "shopNames": shop_names,
        "employmentDate": getattr(user, "employment_date", None),
        "dataScope": get_data_scope(user),
        "roles": roles,
        "permissions": permissions,
        "identity": serialize_identity(user.identity, user),
    }


def normalize_aqc_role_key(raw: str | None) -> str:
    key = str(raw or "").strip().lower()
    if key in AQC_ROLE_LABELS:
        return key
    return LEGACY_AQC_ROLE_MAP.get(key, "aqc_sales")


def get_aqc_role_key(user: AqcUser) -> str:
    if user.role == "admin" or int(user.vip or 0) >= 2:
        return "aqc_admin"

    role_key = normalize_aqc_role_key(getattr(user, "aqc_role_key", None))
    if role_key in AQC_ROLE_LABELS:
        return role_key

    role_slugs = {link.role.slug for link in user.role_links or [] if link.role and link.role.slug}
    if "administrator" in role_slugs or "admin" in role_slugs:
        return "aqc_admin"
    if role_slugs.intersection({"sales-manager", "goods-manager", "shop-manager"}):
        return "aqc_manager"
    if "sales-entry" in role_slugs:
        return "aqc_sales"
    if "sales-viewer" in role_slugs:
        return "aqc_departed"
    return "aqc_sales"


def get_data_scope(user: AqcUser) -> str:
    role_key = get_aqc_role_key(user)
    if role_key == "aqc_admin":
        return "all"
    if role_key == "aqc_departed":
        return "none"
    return "shop"


def collect_user_roles_permissions(user: AqcUser) -> tuple[list[str], list[str]]:
    role_slugs: set[str] = set()
    permission_codes: set[str] = set()
    use_aqc_permissions = bool(user.external_user_id or getattr(user, "aqc_role_key", ""))

    for link in user.role_links or []:
        role = link.role
        if role is None:
            continue
        if use_aqc_permissions and role.slug in LEGACY_MANAGED_ROLE_SLUGS:
            continue
        if role.slug:
            role_slugs.add(role.slug)
        for permission_link in role.permission_links or []:
            permission = permission_link.permission
            if permission and permission.code:
                permission_codes.add(permission.code)

    aqc_role_key = get_aqc_role_key(user)
    role_slugs.add(aqc_role_key)
    permission_codes.update(AQC_ROLE_PERMISSIONS.get(aqc_role_key, set()))

    if user.role == "admin" or aqc_role_key == "aqc_admin":
        role_slugs.add("admin")
        permission_codes.add("*")

    return sorted(role_slugs), sorted(permission_codes)


def scoped_sales_conditions(user: AqcUser) -> list:
    role_key = get_aqc_role_key(user)
    if role_key == "aqc_admin":
        return []
    if role_key == "aqc_departed":
        return [false()]
    shop_ids = user_shop_ids(user)
    if shop_ids:
        return [AqcSaleRecord.shop_id.in_(shop_ids)]
    salesperson_candidates = {
        str(user.username or "").strip(),
        str(user.display_name or "").strip(),
        str(user.phone or "").strip(),
    }
    salesperson_candidates = {value for value in salesperson_candidates if value}
    conditions = []
    if salesperson_candidates:
        conditions.append(AqcSaleRecord.salesperson.in_(sorted(salesperson_candidates)))
    if user.id:
        conditions.append(AqcSaleRecord.created_by == user.id)
    return [or_(*conditions)] if conditions else [false()]


def scoped_shop_conditions(user: AqcUser) -> list:
    role_key = get_aqc_role_key(user)
    if role_key == "aqc_admin":
        return []
    if role_key == "aqc_departed":
        return [false()]
    shop_ids = user_shop_ids(user)
    if shop_ids:
        return [AqcShop.id.in_(shop_ids)]
    return [false()]


def can_access_admin_settings(user: AqcUser) -> bool:
    return get_aqc_role_key(user) == "aqc_admin" or is_global_admin(user)


def _get_auth_context(db: Session, token: str) -> CurrentAuth | None:
    now = datetime.utcnow()
    stmt = (
        select(AqcAuthSession, AqcUser)
        .join(AqcUser, AqcUser.id == AqcAuthSession.user_id)
        .where(
            AqcAuthSession.token_hash == hash_token(token),
            AqcAuthSession.revoked_at.is_(None),
            AqcAuthSession.expires_at > now,
            AqcUser.is_active.is_(True),
        )
        .limit(1)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None

    session_obj, user = row
    session_obj.last_used_at = now
    db.commit()
    db.refresh(session_obj)
    db.refresh(user)

    if user.identity is None:
        identity = db.execute(select(AqcUserIdentity).where(AqcUserIdentity.user_id == user.id).limit(1)).scalars().first()
        user.identity = identity

    return CurrentAuth(user=user, session=session_obj)


def get_current_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> CurrentAuth:
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    auth = _get_auth_context(db, token)
    if auth is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已过期")
    return auth


def get_current_auth_optional(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> CurrentAuth | None:
    token = extract_bearer_token(authorization)
    if not token:
        return None
    return _get_auth_context(db, token)


def get_current_user(auth: CurrentAuth = Depends(get_current_auth)) -> AqcUser:
    return auth.user


def get_admin_user(user: AqcUser = Depends(get_current_user)) -> AqcUser:
    if not is_global_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def is_global_admin(user: AqcUser) -> bool:
    if user.role == "admin" or user.vip == 2 or get_aqc_role_key(user) == "aqc_admin":
        return True

    role_slugs, permission_codes = collect_user_roles_permissions(user)
    if "administrator" in role_slugs:
        return True
    return "*" in permission_codes or "admin.manage_users" in permission_codes


def require_permissions(*required_codes: str) -> Callable[[AqcUser], AqcUser]:
    required = [code.strip() for code in required_codes if code.strip()]

    def dependency(user: AqcUser = Depends(get_current_user)) -> AqcUser:
        if is_global_admin(user):
            return user
        _roles, codes = collect_user_roles_permissions(user)
        if "*" in codes:
            return user
        if any(code in codes for code in required):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

    return dependency

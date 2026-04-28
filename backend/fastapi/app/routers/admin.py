from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import _sync_user_roles_from_aqc_role
from ..config import settings
from ..database import get_db
from ..deps import (
    AQC_ROLE_LABELS,
    assign_user_shops,
    collect_user_roles_permissions,
    normalize_aqc_role_key,
    require_permissions,
    to_iso,
    user_shop_ids,
)
from ..importers import (
    check_aqco_full_mirror_data,
    import_aqco_admin_data,
    import_aqco_full_mirror_data,
    import_aqco_goods_shop_data,
    import_aqco_sales_data,
)
from ..models import AqcPermission, AqcRole, AqcRolePermission, AqcSaleRecord, AqcShop, AqcUser, AqcUserIdentity, AqcUserRole
from ..schemas import (
    AccountAqcUserListResponse,
    AccountAqcUserRemoveRequest,
    AccountAqcUserUpsertRequest,
    AdminImportAqcORequest,
    AdminImportAqcOResponse,
    AdminSetUserRolesRequest,
    AdminUserCreateRequest,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserUpdateRequest,
    MessageResponse,
    PermissionListResponse,
    PermissionOut,
    RoleListResponse,
    RoleOut,
    AdminRoleCreateRequest,
    AdminRoleUpdateRequest,
)
from ..security import (
    generate_token,
    hash_password,
    normalize_email,
    normalize_username,
    validate_email,
    validate_password,
    validate_username,
)


router = APIRouter(prefix="/admin", tags=["admin"])


ROLE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._\-*]{0,79}$")
DEFAULT_AQCO_SQL_PATH = settings.aqco_sql_path or "/legacy-data/whaqc_data.sql"
DEFAULT_AQCO_MIRROR_PREFIX = settings.aqco_full_prefix or "aqco_"

ADMINISH_ROLE_SLUGS = {"administrator", "admin", "sales-manager", "goods-manager", "shop-manager"}
PHONE_PATTERN = re.compile(r"^1\d{10}$")
ACCOUNT_USERNAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._\-]+")
ACCOUNT_ADMIN_TOKEN_CACHE: dict[str, Any] = {
    "token": None,
    "expires_at": None,
}


def _http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    body = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update({str(key): str(value) for key, value in extra_headers.items() if str(value).strip()})

    req = UrlRequest(url=url, data=body, method=method.upper(), headers=headers)
    try:
        with urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                return None, "账号服务返回格式无效"
            return parsed, None
    except HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return None, parsed.get("message") or f"账号服务错误({exc.code})"
        except Exception:
            pass
        return None, f"账号服务错误({exc.code})"
    except URLError:
        return None, "无法连接账号服务"
    except Exception:
        return None, "账号服务响应异常"


def _build_account_internal_login_headers() -> dict[str, str]:
    return {
        "X-Symuse-Client-Id": settings.symuse_client_id,
        "X-Symuse-Client-Secret": settings.symuse_client_secret,
    }


def _normalize_phone_candidate(value: str | None) -> str:
    compact = "".join(ch for ch in str(value or "").strip() if ch.isdigit())
    if compact.startswith("86") and len(compact) > 11:
        compact = compact[-11:]
    return compact[:20]


def _normalize_local_phone(username: str, phone: str | None = None) -> tuple[str | None, str | None]:
    raw_phone = str(phone or "").strip()
    candidate = _normalize_phone_candidate(raw_phone or username)
    if raw_phone and not PHONE_PATTERN.fullmatch(candidate):
        return None, "手机号格式不正确"
    if PHONE_PATTERN.fullmatch(candidate):
        return candidate, None
    return None, None


def _normalize_employment_date(raw_value: str | None) -> tuple[str | None, str | None]:
    text = str(raw_value or "").strip()
    if not text:
        return None, None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y-%m-%d"), None
    except Exception:
        return None, "入职时间格式不正确"


def _pick_top_shop_id(rows: list[tuple[int, int]]) -> int | None:
    if not rows:
        return None
    top_shop_id, top_count = rows[0]
    if len(rows) == 1:
        return int(top_shop_id)
    second_count = rows[1][1]
    if top_count > second_count:
        return int(top_shop_id)
    return None


def _load_shop(db: Session, shop_id: int | None) -> AqcShop | None:
    if shop_id is None or shop_id <= 0:
        return None
    return db.execute(select(AqcShop).where(AqcShop.id == shop_id).limit(1)).scalars().first()


def _suggest_shop_for_user(
    db: Session,
    *,
    username: str,
    phone: str | None,
    display_name: str,
    exclude_user_id: int | None = None,
) -> dict[str, Any] | None:
    normalized_username = normalize_username(username)
    normalized_phone = _normalize_phone_candidate(phone or username)
    normalized_display_name = (display_name or "").strip()
    candidate_user_ids: set[int] = set()
    if exclude_user_id is not None:
        candidate_user_ids.add(int(exclude_user_id))

    user_conditions = []
    if normalized_username:
        user_conditions.append(AqcUser.username == normalized_username)
    if normalized_phone and PHONE_PATTERN.fullmatch(normalized_phone):
        user_conditions.append(AqcUser.phone == normalized_phone)
        user_conditions.append(AqcUser.username == normalized_phone)
    if normalized_display_name:
        user_conditions.append(AqcUser.display_name == normalized_display_name)

    if user_conditions:
        stmt = (
            select(AqcUser.shop_id, func.count(AqcUser.id))
            .where(
                AqcUser.shop_id.is_not(None),
                or_(*user_conditions),
            )
            .group_by(AqcUser.shop_id)
            .order_by(func.count(AqcUser.id).desc(), AqcUser.shop_id.asc())
        )
        if exclude_user_id is not None:
            stmt = stmt.where(AqcUser.id != exclude_user_id)
        matched_users_stmt = select(AqcUser.id).where(or_(*user_conditions))
        if exclude_user_id is not None:
            matched_users_stmt = matched_users_stmt.where(AqcUser.id != exclude_user_id)
        candidate_user_ids.update(int(item[0]) for item in db.execute(matched_users_stmt).all() if item[0] is not None)
        matched_rows = [
            (int(shop_id), int(count))
            for shop_id, count in db.execute(stmt).all()
            if shop_id is not None
        ]
        matched_shop_id = _pick_top_shop_id(matched_rows)
        matched_shop = _load_shop(db, matched_shop_id)
        if matched_shop is not None:
            return {"shop": matched_shop, "source": "旧账户门店"}

    if candidate_user_ids:
        direct_sales_rows = [
            (int(shop_id), int(count))
            for shop_id, count in db.execute(
                select(AqcSaleRecord.shop_id, func.count(AqcSaleRecord.id))
                .where(
                    AqcSaleRecord.shop_id.is_not(None),
                    AqcSaleRecord.created_by.in_(sorted(candidate_user_ids)),
                )
                .group_by(AqcSaleRecord.shop_id)
                .order_by(func.count(AqcSaleRecord.id).desc(), AqcSaleRecord.shop_id.asc())
            ).all()
            if shop_id is not None
        ]
        direct_sales_shop_id = _pick_top_shop_id(direct_sales_rows)
        direct_sales_shop = _load_shop(db, direct_sales_shop_id)
        if direct_sales_shop is not None:
            return {"shop": direct_sales_shop, "source": "历史销售归属"}

    candidate_names: set[str] = set()
    if normalized_display_name:
        candidate_names.add(normalized_display_name)

    if not candidate_names and normalized_username:
        name_rows = db.execute(
            select(AqcUser.display_name)
            .where(
                or_(
                    AqcUser.username == normalized_username,
                    AqcUser.phone == normalized_phone,
                )
            )
        ).all()
        candidate_names.update(
            str(item[0] or "").strip()
            for item in name_rows
            if str(item[0] or "").strip()
        )

    if candidate_names:
        sales_rows = [
            (int(shop_id), int(count))
            for shop_id, count in db.execute(
                select(AqcSaleRecord.shop_id, func.count(AqcSaleRecord.id))
                .where(
                    AqcSaleRecord.shop_id.is_not(None),
                    AqcSaleRecord.salesperson.in_(sorted(candidate_names)),
                )
                .group_by(AqcSaleRecord.shop_id)
                .order_by(func.count(AqcSaleRecord.id).desc(), AqcSaleRecord.shop_id.asc())
            ).all()
            if shop_id is not None
        ]
        sales_shop_id = _pick_top_shop_id(sales_rows)
        sales_shop = _load_shop(db, sales_shop_id)
        if sales_shop is not None:
            return {"shop": sales_shop, "source": "历史销售记录"}

    if normalized_display_name:
        manager_shops = db.execute(
            select(AqcShop).where(AqcShop.manager_name == normalized_display_name).limit(2)
        ).scalars().all()
        if len(manager_shops) == 1:
            return {"shop": manager_shops[0], "source": "店长信息"}

    return None


def _append_shop_match_message(message: str, shop_match: dict[str, Any] | None) -> str:
    if not shop_match or not isinstance(shop_match.get("shop"), AqcShop):
        return message
    shop: AqcShop = shop_match["shop"]
    source = str(shop_match.get("source") or "旧数据")
    return f"{message}，已按{source}匹配门店：{shop.name}"


def _sync_legacy_user_shops(db: Session, users: list[AqcUser]) -> dict[str, int]:
    stats = {
        "scanned": 0,
        "matched": 0,
        "updated": 0,
        "skippedExisting": 0,
        "skippedUnmatched": 0,
    }
    for user in users:
        stats["scanned"] += 1
        if user.shop_id is not None:
            stats["skippedExisting"] += 1
            continue
        suggestion = _suggest_shop_for_user(
            db,
            username=user.username,
            phone=user.phone,
            display_name=user.display_name,
            exclude_user_id=user.id,
        )
        if suggestion is None:
            stats["skippedUnmatched"] += 1
            continue
        assign_user_shops(user, [suggestion["shop"].id])
        stats["matched"] += 1
        stats["updated"] += 1
    return stats


def _resolve_account_aqc_role_key(user: AqcUser, role_slugs: list[str]) -> str:
    aqc_role_key = normalize_aqc_role_key(user.aqc_role_key)
    if aqc_role_key in AQC_ROLE_LABELS:
        return aqc_role_key
    slug_set = set(role_slugs)
    if "administrator" in slug_set or user.role == "admin" or "admin" in slug_set:
        return "aqc_admin"
    if slug_set.intersection(ADMINISH_ROLE_SLUGS):
        return "aqc_manager"
    if "sales-entry" in slug_set:
        return "aqc_sales"
    if "sales-viewer" in slug_set:
        return "aqc_departed"
    if slug_set:
        return "aqc_manager"
    return "aqc_departed"


def _normalize_account_role_key(raw_role_key: str | None) -> str:
    return normalize_aqc_role_key(raw_role_key)


def _normalize_account_role_name(raw_role_key: str | None, raw_role_name: str | None = None) -> str:
    normalized_role_key = _normalize_account_role_key(raw_role_key)
    if normalized_role_key in AQC_ROLE_LABELS:
        return AQC_ROLE_LABELS[normalized_role_key]
    return str(raw_role_name or "").strip() or AQC_ROLE_LABELS["aqc_sales"]


def _sync_local_user_aqc_role(user: AqcUser, aqc_role_key: str) -> None:
    normalized_role = normalize_aqc_role_key(aqc_role_key)
    user.aqc_role_key = normalized_role
    if normalized_role == "aqc_admin":
        user.role = "admin"
        user.vip = max(int(user.vip or 0), 2)
        return
    user.role = "user"
    user.vip = 0


def _sync_local_user_roles_from_aqc_role(db: Session, user: AqcUser, aqc_role_key: str) -> None:
    _sync_user_roles_from_aqc_role(db, user, aqc_role_key)
    _sync_local_user_aqc_role(user, aqc_role_key)


def _sync_users_to_account_aqc_group(db: Session, users: list[AqcUser]) -> dict[str, int]:
    stats = {
        "syncCandidates": len(users),
        "syncEnsuredAccountUser": 0,
        "syncCreatedAccountUser": 0,
        "syncUpdatedAccountProfile": 0,
        "syncSkippedInactive": 0,
        "syncByExternal": 0,
        "syncByMatch": 0,
        "syncSkippedNoAccountUser": 0,
        "syncSuccess": 0,
        "syncFailed": 0,
    }
    if not users:
        return stats
    if not settings.symuse_aqc_sync_enabled:
        return stats

    account = settings.symuse_admin_account.strip()
    password = settings.symuse_admin_password
    if not account or not password:
        stats["syncFailed"] = len(users)
        return stats

    login_result, login_error = _http_json(
        "POST",
        f"{settings.symuse_api_base}/auth/login",
        payload={"account": account, "password": password},
        extra_headers=_build_account_internal_login_headers(),
    )
    if login_error or not login_result or not login_result.get("success"):
        stats["syncFailed"] = len(users)
        return stats

    token = str(login_result.get("token") or "").strip()
    if not token:
        stats["syncFailed"] = len(users)
        return stats

    users_result, users_error = _http_json(
        "GET",
        f"{settings.symuse_api_base}/admin/users",
        token=token,
    )
    if users_error or not users_result or not users_result.get("success"):
        stats["syncFailed"] = len(users)
        return stats

    account_users = users_result.get("users")
    if not isinstance(account_users, list):
        stats["syncFailed"] = len(users)
        return stats

    by_username: dict[str, int] = {}
    by_email: dict[str, int] = {}
    for item in account_users:
        if not isinstance(item, dict):
            continue
        try:
            user_id = int(item.get("id"))
        except Exception:
            continue
        username = normalize_username(str(item.get("username") or ""))
        email = normalize_email(str(item.get("email") or ""))
        if username:
            by_username[username] = user_id
        if email:
            by_email[email] = user_id

    for user in users:
        ensure_ok, ensure_detail = _ensure_account_link_for_local_user(db, user)
        if not ensure_ok:
            stats["syncFailed"] += 1
            if user.external_user_id is None:
                stats["syncSkippedNoAccountUser"] += 1
            continue
        stats["syncEnsuredAccountUser"] += 1
        if ensure_detail.get("created"):
            stats["syncCreatedAccountUser"] += 1
        if ensure_detail.get("updated"):
            stats["syncUpdatedAccountProfile"] += 1
        if not user.is_active:
            stats["syncSkippedInactive"] += 1
            continue

        target_user_id = user.external_user_id
        if target_user_id is None:
            matched_id = by_username.get(normalize_username(user.username or ""))
            if matched_id is None and user.email:
                matched_id = by_email.get(normalize_email(user.email))
            if matched_id is None:
                stats["syncSkippedNoAccountUser"] += 1
                continue
            user.external_user_id = matched_id
            target_user_id = matched_id
            stats["syncByMatch"] += 1
        else:
            stats["syncByExternal"] += 1

        role_slugs, _permissions = collect_user_roles_permissions(user)
        payload = {
            "userId": int(target_user_id),
            "roleKey": _resolve_account_aqc_role_key(user, role_slugs),
            "isEnabled": bool(user.is_active),
        }
        result, error = _http_json(
            "POST",
            f"{settings.symuse_api_base}/admin/aqc/users/upsert",
            payload=payload,
            token=token,
        )
        if error or not result or not result.get("success"):
            stats["syncFailed"] += 1
            continue
        stats["syncSuccess"] += 1

    return stats


def _get_account_admin_token(force_refresh: bool = False) -> tuple[str | None, str | None]:
    cached_token = str(ACCOUNT_ADMIN_TOKEN_CACHE.get("token") or "").strip()
    cached_expires_at = ACCOUNT_ADMIN_TOKEN_CACHE.get("expires_at")
    if (
        not force_refresh
        and cached_token
        and isinstance(cached_expires_at, datetime)
        and cached_expires_at > datetime.utcnow()
    ):
        return cached_token, None

    account = settings.symuse_admin_account.strip()
    password = settings.symuse_admin_password
    if not account or not password:
        return None, "未配置 account.symuse.com 管理员账号"

    login_result, login_error = _http_json(
        "POST",
        f"{settings.symuse_api_base}/auth/login",
        payload={"account": account, "password": password},
        extra_headers=_build_account_internal_login_headers(),
    )
    if login_error or not login_result or not login_result.get("success"):
        return None, login_error or (login_result or {}).get("message") or "账号服务登录失败"

    token = str(login_result.get("token") or "").strip()
    if not token:
        return None, "账号服务未返回 token"
    ACCOUNT_ADMIN_TOKEN_CACHE["token"] = token
    ACCOUNT_ADMIN_TOKEN_CACHE["expires_at"] = datetime.utcnow() + timedelta(minutes=20)
    return token, None


def _call_account_admin_api(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    token, token_error = _get_account_admin_token()
    if token_error:
        return None, token_error
    result, error = _http_json(method, f"{settings.symuse_api_base}{path}", payload=payload, token=token)
    if error and "401" in error:
        token, token_error = _get_account_admin_token(force_refresh=True)
        if token_error:
            return None, token_error
        return _http_json(method, f"{settings.symuse_api_base}{path}", payload=payload, token=token)
    return result, error


def _build_account_email(username: str, email: str | None = None) -> str:
    normalized = normalize_email(email or "")
    if normalized and validate_email(normalized) is None:
        return normalized
    safe_username = normalize_username(username).replace(" ", "").lower() or "aqc_user"
    return f"{safe_username}@aqc.symuse.local"


def _sanitize_account_username(value: str | None) -> str:
    cleaned = ACCOUNT_USERNAME_SANITIZE_PATTERN.sub("-", normalize_username(value or "")).strip("._-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:50]


def _build_account_username_for_user(user: AqcUser) -> str:
    phone = _normalize_phone_candidate(user.phone or user.username)
    if PHONE_PATTERN.fullmatch(phone):
        return phone

    for candidate in (
        user.username,
        user.display_name,
        (normalize_email(user.email or "").split("@", 1)[0] if user.email else ""),
    ):
        safe_candidate = _sanitize_account_username(candidate)
        if validate_username(safe_candidate) is None:
            return safe_candidate

    return f"aqc-user-{int(user.id)}"


def _find_account_user_id(*, username: str, email: str | None = None, phone: str | None = None) -> tuple[int | None, str | None]:
    result, error = _call_account_admin_api("GET", "/admin/users")
    if error or not result or not result.get("success"):
        return None, error or (result or {}).get("message") or "加载账号中心用户列表失败"

    users = result.get("users")
    if not isinstance(users, list):
        return None, "账号中心返回用户列表格式无效"

    normalized_username = normalize_username(username)
    normalized_email = normalize_email(email or "")
    normalized_phone = _normalize_phone_candidate(phone or "")
    for item in users:
        if not isinstance(item, dict):
            continue
        candidate_username = normalize_username(str(item.get("username") or ""))
        candidate_email = normalize_email(str(item.get("email") or ""))
        candidate_phone = _normalize_phone_candidate(str(item.get("phone") or ""))
        if (
            candidate_username == normalized_username
            or (normalized_email and candidate_email == normalized_email)
            or (normalized_phone and candidate_phone == normalized_phone)
        ):
            try:
                return int(item.get("id")), None
            except Exception:
                return None, "账号中心返回用户ID无效"
    return None, "账号中心未找到对应用户"


def _ensure_account_user(
    *,
    username: str,
    email: str | None,
    phone: str | None,
    display_name: str,
    password: str,
) -> tuple[int | None, str | None]:
    normalized_email = _build_account_email(username, email)
    result, error = _call_account_admin_api(
        "POST",
        "/admin/users/create",
        payload={
            "username": username,
            "email": normalized_email,
            "phone": (phone or "").strip() or None,
            "displayName": display_name,
            "password": password,
        },
    )
    if error or not result or not result.get("success"):
        return None, error or (result or {}).get("message") or "账号中心用户创建失败"
    return _find_account_user_id(username=username, email=normalized_email, phone=phone)


def _update_account_user(
    *,
    external_user_id: int,
    username: str,
    email: str | None,
    phone: str | None,
    display_name: str,
    is_active: bool,
) -> str | None:
    result, error = _call_account_admin_api(
        "POST",
        "/admin/users/update",
        payload={
            "userId": int(external_user_id),
            "username": username,
            "email": _build_account_email(username, email),
            "phone": (phone or "").strip() or None,
            "displayName": display_name,
            "isActive": bool(is_active),
        },
    )
    if error or not result or not result.get("success"):
        return error or (result or {}).get("message") or "账号中心用户更新失败"
    return None


def _ensure_account_link_for_local_user(
    db: Session,
    user: AqcUser,
    *,
    default_password: str = "aq123456",
) -> tuple[bool, dict[str, Any]]:
    preferred_username = _build_account_username_for_user(user)
    preferred_email = _build_account_email(preferred_username, user.email)
    display_name = (user.display_name or user.username or preferred_username).strip()[:80] or preferred_username
    phone = _normalize_phone_candidate(user.phone or user.username)
    if not PHONE_PATTERN.fullmatch(phone):
        phone = None

    detail: dict[str, Any] = {
        "userId": int(user.id),
        "username": user.username,
        "displayName": user.display_name,
        "accountUsername": preferred_username,
        "created": False,
        "linked": False,
        "updated": False,
    }

    target_user_id = user.external_user_id
    if target_user_id is None:
        for candidate_username, candidate_email in (
            (normalize_username(user.username), normalize_email(user.email or "") or None),
            (preferred_username, preferred_email),
        ):
            if not candidate_username and not candidate_email and not phone:
                continue
            matched_id, _match_error = _find_account_user_id(
                username=candidate_username or preferred_username,
                email=candidate_email,
                phone=phone,
            )
            if matched_id is not None:
                user.external_user_id = matched_id
                target_user_id = matched_id
                detail["linked"] = True
                break

    if target_user_id is None:
        created_user_id, create_error = _ensure_account_user(
            username=preferred_username,
            email=preferred_email,
            phone=phone,
            display_name=display_name,
            password=default_password,
        )
        if create_error or created_user_id is None:
            detail["error"] = create_error or "账号中心用户创建失败"
            return False, detail
        user.external_user_id = created_user_id
        target_user_id = created_user_id
        detail["created"] = True

    update_error = _update_account_user(
        external_user_id=int(target_user_id),
        username=preferred_username,
        email=preferred_email,
        phone=phone,
        display_name=display_name,
        is_active=bool(user.is_active),
    )
    if update_error:
        if not user.is_active and "已停用" in update_error:
            return True, detail
        detail["error"] = update_error
        return False, detail

    detail["updated"] = True
    return True, detail


def _reset_account_user_password(*, external_user_id: int, password: str) -> str | None:
    result, error = _call_account_admin_api(
        "POST",
        "/admin/users/reset-password",
        payload={"userId": int(external_user_id), "newPassword": password},
    )
    if error or not result or not result.get("success"):
        return error or (result or {}).get("message") or "账号中心密码更新失败"
    return None


def _delete_account_user(*, external_user_id: int) -> str | None:
    result, error = _call_account_admin_api(
        "POST",
        "/admin/users/delete",
        payload={"userId": int(external_user_id)},
    )
    if error or not result or not result.get("success"):
        return error or (result or {}).get("message") or "账号中心用户删除失败"
    return None


def _sync_local_user_from_account_membership(
    db: Session,
    *,
    external_user_id: int,
    role_key: str,
    is_enabled: bool,
) -> AqcUser | None:
    user = (
        db.execute(select(AqcUser).where(AqcUser.external_user_id == external_user_id).limit(1))
        .scalars()
        .first()
    )
    if user is None:
        return None

    user.is_active = bool(is_enabled)
    _sync_local_user_roles_from_aqc_role(db, user, role_key if is_enabled else "aqc_departed")
    return user


def _resolve_shop_names(db: Session, shop_ids: list[int]) -> list[str]:
    if not shop_ids:
        return []
    rows = db.execute(
        select(AqcShop.id, AqcShop.name).where(AqcShop.id.in_(shop_ids)).order_by(AqcShop.id.asc())
    ).all()
    shop_name_map = {int(row[0]): str(row[1] or "") for row in rows if row[1]}
    return [shop_name_map[shop_id] for shop_id in shop_ids if shop_id in shop_name_map]


def _normalize_requested_shop_ids(shop_ids: list[int] | None, shop_id: int | None = None) -> list[int]:
    ordered: list[int] = []
    if shop_id is not None and int(shop_id) > 0:
        ordered.append(int(shop_id))
    ordered.extend(int(item) for item in (shop_ids or []) if int(item) > 0)
    deduped: list[int] = []
    seen: set[int] = set()
    for item in ordered:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _validate_shop_ids(db: Session, shop_ids: list[int]) -> tuple[list[int], str | None]:
    normalized = [int(item) for item in shop_ids if int(item) > 0]
    if not normalized:
        return [], None
    existing = {
        int(item)
        for item in db.execute(select(AqcShop.id).where(AqcShop.id.in_(normalized))).scalars().all()
    }
    if len(existing) != len(normalized):
        return [], "门店不存在"
    return [item for item in normalized if item in existing], None


def _to_admin_user_item(db: Session, user: AqcUser) -> AdminUserItem:
    roles, permissions = collect_user_roles_permissions(user)
    aqc_role_key = normalize_aqc_role_key(user.aqc_role_key)
    shop_ids = user_shop_ids(user)
    shop_names = _resolve_shop_names(db, shop_ids)
    phone = user.phone
    if not phone:
        derived_phone, _phone_error = _normalize_local_phone(user.username)
        phone = derived_phone
    return AdminUserItem(
        id=user.id,
        externalUserId=user.external_user_id,
        username=user.username,
        email=user.email,
        displayName=user.display_name,
        phone=phone,
        role=user.role,
        vip=user.vip,
        vipLevel=user.vip_level,
        userRuleId=user.user_rule_id,
        authSource=user.auth_source,
        isActive=user.is_active,
        createdAt=to_iso(user.created_at) or "",
        updatedAt=to_iso(user.updated_at) or "",
        lastLoginAt=to_iso(user.last_login_at),
        aqcRoleKey=aqc_role_key,
        aqcRoleName=AQC_ROLE_LABELS.get(aqc_role_key, AQC_ROLE_LABELS["aqc_sales"]),
        shopId=user.shop_id,
        shopName=shop_names[0] if shop_names else (user.assigned_shop.name if user.assigned_shop else None),
        shopIds=shop_ids,
        shopNames=shop_names,
        employmentDate=user.employment_date,
        roles=roles,
        permissions=permissions,
    )


def _to_role_out(db: Session, role: AqcRole) -> RoleOut:
    permission_codes = [
        row[0]
        for row in db.execute(
            select(AqcPermission.code)
            .join(AqcRolePermission, AqcRolePermission.permission_id == AqcPermission.id)
            .where(AqcRolePermission.role_id == role.id)
            .order_by(AqcPermission.code.asc())
        ).all()
    ]
    user_count = db.execute(select(AqcUserRole.id).where(AqcUserRole.role_id == role.id)).all()
    return RoleOut(
        id=role.id,
        name=role.name,
        slug=role.slug,
        description=role.description,
        isSystem=role.is_system,
        permissions=permission_codes,
        userCount=len(user_count),
    )


def _sync_user_roles(db: Session, user: AqcUser, role_ids: list[int], assigned_by: int | None) -> None:
    normalized_role_ids = sorted({int(item) for item in role_ids if int(item) > 0})
    valid_roles = db.execute(select(AqcRole).where(AqcRole.id.in_(normalized_role_ids))).scalars().all() if normalized_role_ids else []
    valid_role_id_set = {role.id for role in valid_roles}

    existing_links = db.execute(select(AqcUserRole).where(AqcUserRole.user_id == user.id)).scalars().all()
    existing_role_map = {link.role_id: link for link in existing_links}

    for role_id, link in existing_role_map.items():
        if role_id not in valid_role_id_set:
            db.delete(link)

    for role in valid_roles:
        if role.id not in existing_role_map:
            db.add(AqcUserRole(user_id=user.id, role_id=role.id, assigned_by=assigned_by))

    role_slugs = {role.slug for role in valid_roles}
    if "administrator" in role_slugs or "admin" in role_slugs:
        user.role = "admin"
        user.vip = max(user.vip or 0, 2)
    elif user.role != "admin":
        user.role = "user"


def _sync_role_permissions(db: Session, role: AqcRole, permission_codes: list[str]) -> None:
    normalized_codes = sorted({str(code).strip() for code in permission_codes if str(code).strip()})
    permissions = (
        db.execute(select(AqcPermission).where(AqcPermission.code.in_(normalized_codes))).scalars().all()
        if normalized_codes
        else []
    )
    permission_id_set = {item.id for item in permissions}

    existing_links = db.execute(select(AqcRolePermission).where(AqcRolePermission.role_id == role.id)).scalars().all()
    existing_permission_map = {link.permission_id: link for link in existing_links}

    for permission_id, link in existing_permission_map.items():
        if permission_id not in permission_id_set:
            db.delete(link)

    for permission in permissions:
        if permission.id not in existing_permission_map:
            db.add(AqcRolePermission(role_id=role.id, permission_id=permission.id))


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    q: str | None = None,
    _user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    stmt = select(AqcUser).order_by(AqcUser.created_at.desc(), AqcUser.id.desc())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AqcUser.username.like(like),
                AqcUser.display_name.like(like),
                AqcUser.email.like(like),
                AqcUser.phone.like(like),
            )
        )
    users = db.execute(stmt).scalars().all()
    return {"success": True, "users": [_to_admin_user_item(db, item) for item in users]}


@router.post("/users")
def create_user(
    payload: AdminUserCreateRequest,
    current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    username = normalize_username(payload.username)
    username_error = validate_username(username)
    if username_error:
        return {"success": False, "message": username_error}
    phone, phone_error = _normalize_local_phone(username, payload.phone)
    if phone_error:
        return {"success": False, "message": phone_error}

    exists = db.execute(select(AqcUser.id).where(AqcUser.username == username).limit(1)).scalar()
    if exists is not None:
        return {"success": False, "message": "用户名已存在"}
    if phone:
        phone_exists = db.execute(select(AqcUser.id).where(AqcUser.phone == phone).limit(1)).scalar()
        if phone_exists is not None:
            return {"success": False, "message": "手机号已存在"}

    email = normalize_email(payload.email or "")
    email = email or None
    if email:
        email_error = validate_email(email)
        if email_error:
            return {"success": False, "message": email_error}
        email_exists = db.execute(select(AqcUser.id).where(AqcUser.email == email).limit(1)).scalar()
        if email_exists is not None:
            return {"success": False, "message": "邮箱已存在"}

    account_user_id = payload.externalUserId
    generated_password = payload.password
    if payload.externalUserId is not None:
        ext_exists = db.execute(select(AqcUser.id).where(AqcUser.external_user_id == payload.externalUserId).limit(1)).scalar()
        if ext_exists is not None:
            return {"success": False, "message": "externalUserId 已被占用"}
    employment_date, employment_date_error = _normalize_employment_date(payload.employmentDate)
    if employment_date_error:
        return {"success": False, "message": employment_date_error}
    requested_shop_ids, shop_id_error = _validate_shop_ids(
        db,
        _normalize_requested_shop_ids(payload.shopIds, payload.shopId),
    )
    if shop_id_error:
        return {"success": False, "message": shop_id_error}
    auto_shop_match = None
    if not requested_shop_ids:
        auto_shop_match = _suggest_shop_for_user(
            db,
            username=username,
            phone=phone,
            display_name=(payload.displayName or username).strip()[:80] or username,
        )

    password = payload.password
    if password is not None:
        pwd_error = validate_password(password)
        if pwd_error:
            return {"success": False, "message": pwd_error}
    else:
        password = generate_token()
    generated_password = password

    if account_user_id is None and settings.symuse_aqc_sync_enabled:
        account_user_id, account_error = _ensure_account_user(
            username=username,
            email=email,
            phone=phone,
            display_name=(payload.displayName or username).strip()[:80] or username,
            password=generated_password,
        )
        if account_error:
            return {"success": False, "message": account_error}

    user = AqcUser(
        external_user_id=account_user_id,
        username=username,
        email=email,
        password_hash=hash_password(password),
        display_name=(payload.displayName or username).strip()[:80],
        avatar_url="",
        phone=phone,
        role="user",
        aqc_role_key=normalize_aqc_role_key(payload.aqcRoleKey),
        shop_id=payload.shopId or (auto_shop_match["shop"].id if auto_shop_match else None),
        employment_date=employment_date,
        vip=payload.vip,
        vip_level=payload.vipLevel,
        user_rule_id=payload.userRuleId,
        auth_source=(payload.authSource or "local").strip()[:30],
        is_active=payload.isActive,
    )
    db.add(user)
    db.flush()
    final_shop_ids = requested_shop_ids or ([auto_shop_match["shop"].id] if auto_shop_match else [])
    assign_user_shops(user, final_shop_ids)
    _sync_local_user_roles_from_aqc_role(db, user, user.aqc_role_key)

    db.add(
        AqcUserIdentity(
            user_id=user.id,
            name=user.display_name,
            avatar=user.avatar_url,
            mobile=user.phone,
            sex=0,
            vip=user.vip,
        )
    )

    _sync_user_roles(db, user, payload.roleIds, assigned_by=current_user.id)
    db.commit()
    db.refresh(user)
    sync_stats = _sync_users_to_account_aqc_group(db, [user])
    db.commit()
    db.refresh(user)

    message = _append_shop_match_message("用户创建成功", auto_shop_match)
    if sync_stats["syncFailed"] > 0:
        message = _append_shop_match_message("用户创建成功，但 account 用户组同步部分失败", auto_shop_match)
    elif sync_stats["syncSuccess"] > 0:
        message = _append_shop_match_message("用户创建成功，已同步到 account AQC 用户组", auto_shop_match)

    return {
        "success": True,
        "message": message,
        "syncStats": sync_stats,
        "user": _to_admin_user_item(db, user),
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    user = db.execute(select(AqcUser).where(AqcUser.id == user_id).limit(1)).scalars().first()
    if user is None:
        return {"success": False, "message": "用户不存在"}
    provided_fields = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    next_username = user.username
    auto_shop_match = None

    if payload.email is not None:
        email = normalize_email(payload.email or "")
        if email:
            email_error = validate_email(email)
            if email_error:
                return {"success": False, "message": email_error}
            email_exists = db.execute(
                select(AqcUser.id).where(AqcUser.email == email, AqcUser.id != user.id).limit(1)
            ).scalar()
            if email_exists is not None:
                return {"success": False, "message": "邮箱已存在"}
            user.email = email
        else:
            user.email = None

    if payload.username is not None:
        username = normalize_username(payload.username)
        username_error = validate_username(username)
        if username_error:
            return {"success": False, "message": username_error}
        username_exists = db.execute(
            select(AqcUser.id).where(AqcUser.username == username, AqcUser.id != user.id).limit(1)
        ).scalar()
        if username_exists is not None:
            return {"success": False, "message": "用户名已存在"}
        user.username = username
        next_username = username

    phone_input = payload.phone if "phone" in provided_fields else user.phone
    phone, phone_error = _normalize_local_phone(next_username, phone_input)
    if phone_error:
        return {"success": False, "message": phone_error}
    if phone:
        phone_exists = db.execute(
            select(AqcUser.id).where(AqcUser.phone == phone, AqcUser.id != user.id).limit(1)
        ).scalar()
        if phone_exists is not None:
            return {"success": False, "message": "手机号已存在"}
    user.phone = phone

    if payload.externalUserId is not None:
        external_exists = db.execute(
            select(AqcUser.id).where(AqcUser.external_user_id == payload.externalUserId, AqcUser.id != user.id).limit(1)
        ).scalar()
        if external_exists is not None:
            return {"success": False, "message": "externalUserId 已被占用"}
        user.external_user_id = payload.externalUserId
    if payload.employmentDate is not None:
        employment_date, employment_date_error = _normalize_employment_date(payload.employmentDate)
        if employment_date_error:
            return {"success": False, "message": employment_date_error}
        user.employment_date = employment_date
    if "shopId" in provided_fields or "shopIds" in provided_fields:
        requested_shop_ids, shop_id_error = _validate_shop_ids(
            db,
            _normalize_requested_shop_ids(payload.shopIds, payload.shopId),
        )
        if shop_id_error:
            return {"success": False, "message": shop_id_error}
        assign_user_shops(user, requested_shop_ids)
    elif not user_shop_ids(user):
        auto_shop_match = _suggest_shop_for_user(
            db,
            username=user.username,
            phone=user.phone,
            display_name=payload.displayName if payload.displayName is not None else user.display_name,
            exclude_user_id=user.id,
        )
        if auto_shop_match is not None:
            assign_user_shops(user, [auto_shop_match["shop"].id])

    if payload.displayName is not None:
        user.display_name = payload.displayName.strip()[:80]
    if payload.vip is not None:
        user.vip = payload.vip
    if payload.vipLevel is not None:
        user.vip_level = payload.vipLevel
    if payload.userRuleId is not None:
        user.user_rule_id = payload.userRuleId
    if payload.isActive is not None:
        user.is_active = payload.isActive
    if payload.aqcRoleKey is not None:
        _sync_local_user_roles_from_aqc_role(db, user, payload.aqcRoleKey)

    if payload.password is not None:
        pwd_error = validate_password(payload.password)
        if pwd_error:
            return {"success": False, "message": pwd_error}
        user.password_hash = hash_password(payload.password)

    if user.external_user_id is not None and settings.symuse_aqc_sync_enabled:
        account_error = _update_account_user(
            external_user_id=int(user.external_user_id),
            username=user.username,
            email=user.email,
            phone=user.phone,
            display_name=user.display_name,
            is_active=user.is_active,
        )
        if account_error:
            return {"success": False, "message": account_error}
        if payload.password is not None:
            password_error = _reset_account_user_password(
                external_user_id=int(user.external_user_id),
                password=payload.password,
            )
            if password_error:
                return {"success": False, "message": password_error}

    if user.identity is None:
        db.add(
            AqcUserIdentity(
                user_id=user.id,
                name=user.display_name,
                avatar=user.avatar_url,
                mobile=user.phone,
                sex=0,
                vip=user.vip,
            )
        )
    else:
        user.identity.name = user.display_name or user.identity.name
        user.identity.mobile = user.phone or user.identity.mobile
        user.identity.vip = user.vip

    if payload.roleIds is not None:
        _sync_user_roles(db, user, payload.roleIds, assigned_by=current_user.id)

    db.commit()
    db.refresh(user)
    sync_stats = _sync_users_to_account_aqc_group(db, [user])
    db.commit()
    db.refresh(user)

    message = _append_shop_match_message("用户更新成功", auto_shop_match)
    if sync_stats["syncFailed"] > 0:
        message = _append_shop_match_message("用户更新成功，但 account 用户组同步部分失败", auto_shop_match)
    elif sync_stats["syncSuccess"] > 0:
        message = _append_shop_match_message("用户更新成功，已同步到 account AQC 用户组", auto_shop_match)

    return {
        "success": True,
        "message": message,
        "syncStats": sync_stats,
        "user": _to_admin_user_item(db, user),
    }


@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        return {"success": False, "message": "不能删除当前登录账号"}

    user = db.execute(select(AqcUser).where(AqcUser.id == user_id).limit(1)).scalars().first()
    if user is None:
        return {"success": False, "message": "用户不存在"}

    if user.external_user_id is not None and settings.symuse_aqc_sync_enabled:
        account_error = _delete_account_user(external_user_id=int(user.external_user_id))
        if account_error:
            return {"success": False, "message": account_error}

    user.is_active = False
    user.aqc_role_key = "aqc_departed"
    db.commit()
    return {"success": True, "message": "账户已删除"}


@router.post("/users/{user_id}/roles", response_model=MessageResponse)
def set_user_roles(
    user_id: int,
    payload: AdminSetUserRolesRequest,
    current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    user = db.execute(select(AqcUser).where(AqcUser.id == user_id).limit(1)).scalars().first()
    if user is None:
        return {"success": False, "message": "用户不存在"}

    _sync_user_roles(db, user, payload.roleIds, assigned_by=current_user.id)
    db.commit()
    sync_stats = _sync_users_to_account_aqc_group(db, [user])
    db.commit()
    if sync_stats["syncFailed"] > 0:
        return {"success": True, "message": "角色更新成功，但 account 用户组同步部分失败"}
    return {"success": True, "message": "角色更新成功"}


@router.get("/roles", response_model=RoleListResponse)
def list_roles(
    _user: AqcUser = Depends(require_permissions("admin.manage_roles")),
    db: Session = Depends(get_db),
):
    rows = db.execute(select(AqcRole).order_by(AqcRole.is_system.desc(), AqcRole.id.asc())).scalars().all()
    return {"success": True, "roles": [_to_role_out(db, role) for role in rows]}


@router.post("/roles")
def create_role(
    payload: AdminRoleCreateRequest,
    _user: AqcUser = Depends(require_permissions("admin.manage_roles")),
    db: Session = Depends(get_db),
):
    slug = (payload.slug or "").strip().lower()
    if not ROLE_SLUG_PATTERN.match(slug):
        return {"success": False, "message": "slug 格式不正确，仅允许小写字母、数字、点、下划线、中划线和*"}

    exists = db.execute(select(AqcRole.id).where(AqcRole.slug == slug).limit(1)).scalar()
    if exists is not None:
        return {"success": False, "message": "角色 slug 已存在"}

    role = AqcRole(
        name=payload.name.strip()[:80],
        slug=slug,
        description=(payload.description or "").strip()[:255],
        is_system=False,
    )
    db.add(role)
    db.flush()
    _sync_role_permissions(db, role, payload.permissionCodes)
    db.commit()
    db.refresh(role)
    return {"success": True, "message": "角色创建成功", "role": _to_role_out(db, role)}


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    payload: AdminRoleUpdateRequest,
    _user: AqcUser = Depends(require_permissions("admin.manage_roles")),
    db: Session = Depends(get_db),
):
    role = db.execute(select(AqcRole).where(AqcRole.id == role_id).limit(1)).scalars().first()
    if role is None:
        return {"success": False, "message": "角色不存在"}

    if payload.name is not None:
        role.name = payload.name.strip()[:80]

    if payload.slug is not None:
        next_slug = payload.slug.strip().lower()
        if not ROLE_SLUG_PATTERN.match(next_slug):
            return {"success": False, "message": "slug 格式不正确"}
        exists = db.execute(select(AqcRole.id).where(AqcRole.slug == next_slug, AqcRole.id != role.id).limit(1)).scalar()
        if exists is not None:
            return {"success": False, "message": "角色 slug 已存在"}
        if role.is_system and next_slug != role.slug:
            return {"success": False, "message": "系统角色不允许修改 slug"}
        role.slug = next_slug

    if payload.description is not None:
        role.description = payload.description.strip()[:255]

    if payload.permissionCodes is not None:
        _sync_role_permissions(db, role, payload.permissionCodes)

    db.commit()
    db.refresh(role)
    return {"success": True, "message": "角色更新成功", "role": _to_role_out(db, role)}


@router.get("/permissions", response_model=PermissionListResponse)
def list_permissions(
    _user: AqcUser = Depends(require_permissions("admin.manage_roles")),
    db: Session = Depends(get_db),
):
    rows = db.execute(select(AqcPermission).order_by(AqcPermission.code.asc())).scalars().all()
    permissions = [
        PermissionOut(
            id=item.id,
            code=item.code,
            name=item.name,
            description=item.description,
        )
        for item in rows
    ]
    return {"success": True, "permissions": permissions}


@router.get("/account-aqc/users", response_model=AccountAqcUserListResponse)
def list_account_aqc_users(
    _user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    result, error = _call_account_admin_api("GET", "/admin/aqc/users")
    if error or not result or not result.get("success"):
        return {
            "success": False,
            "message": error or (result or {}).get("message") or "加载 account AQC 用户失败",
            "users": [],
        }

    account_users = result.get("users")
    if not isinstance(account_users, list):
        return {"success": False, "message": "账号服务返回格式无效", "users": []}

    local_users = {
        int(user.external_user_id): user
        for user in db.execute(select(AqcUser).where(AqcUser.external_user_id.is_not(None))).scalars().all()
        if user.external_user_id is not None
    }

    users: list[dict[str, Any]] = []
    for item in account_users:
        if not isinstance(item, dict):
            continue
        try:
            user_id = int(item.get("userId"))
        except Exception:
            continue

        local_user = local_users.get(user_id)
        local_roles, _local_permissions = collect_user_roles_permissions(local_user) if local_user else ([], [])
        users.append(
            {
                "userId": user_id,
                "username": str(item.get("username") or ""),
                "email": str(item.get("email") or "") or None,
                "displayName": str(item.get("displayName") or item.get("username") or ""),
                "aqcRoleKey": _normalize_account_role_key(item.get("aqcRoleKey") or item.get("roleKey")),
                "aqcRoleName": _normalize_account_role_name(item.get("aqcRoleKey") or item.get("roleKey"), item.get("aqcRoleName")),
                "isEnabled": bool(item.get("isEnabled")),
                "lastLoginAt": item.get("lastLoginAt"),
                "updatedAt": str(item.get("updatedAt") or ""),
                "localUserId": local_user.id if local_user else None,
                "localDisplayName": local_user.display_name if local_user else None,
                "localRoles": local_roles,
                "localIsActive": bool(local_user.is_active) if local_user else None,
            }
        )

    return {"success": True, "users": users}


@router.post("/account-aqc/users/upsert", response_model=MessageResponse)
def upsert_account_aqc_user(
    payload: AccountAqcUserUpsertRequest,
    _current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    result, error = _call_account_admin_api(
        "POST",
        "/admin/aqc/users/upsert",
        payload={
            "userId": payload.userId,
            "roleKey": normalize_aqc_role_key(payload.roleKey),
            "isEnabled": payload.isEnabled,
        },
    )
    if error or not result or not result.get("success"):
        return {"success": False, "message": error or (result or {}).get("message") or "更新 account AQC 用户失败"}

    _sync_local_user_from_account_membership(
        db,
        external_user_id=int(payload.userId),
        role_key=normalize_aqc_role_key(payload.roleKey),
        is_enabled=bool(payload.isEnabled),
    )
    db.commit()
    return {"success": True, "message": str(result.get("message") or "AQC 用户组已更新")}


@router.post("/account-aqc/users/remove", response_model=MessageResponse)
def remove_account_aqc_user(
    payload: AccountAqcUserRemoveRequest,
    _current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    result, error = _call_account_admin_api(
        "POST",
        "/admin/aqc/users/remove",
        payload={"userId": payload.userId},
    )
    if error or not result or not result.get("success"):
        return {"success": False, "message": error or (result or {}).get("message") or "移出 AQC 用户组失败"}

    local_user = (
        db.execute(select(AqcUser).where(AqcUser.external_user_id == payload.userId).limit(1))
        .scalars()
        .first()
    )
    if local_user is not None:
        local_user.is_active = False
    db.commit()
    return {"success": True, "message": str(result.get("message") or "已移出 AQC 用户组")}


@router.post("/import/aqc-o", response_model=AdminImportAqcOResponse)
def import_aqco_accounts(
    payload: AdminImportAqcORequest,
    current_user: AqcUser = Depends(require_permissions("admin.import_legacy")),
    db: Session = Depends(get_db),
):
    sql_path = (payload.sqlPath or "").strip() or DEFAULT_AQCO_SQL_PATH
    try:
        stats = import_aqco_admin_data(db, sql_path=sql_path, assigned_by=current_user.id)
        shop_match_stats = _sync_legacy_user_shops(
            db,
            db.execute(select(AqcUser).where(AqcUser.is_active.is_(True))).scalars().all(),
        )
        sync_users = db.execute(select(AqcUser)).scalars().all()
        sync_stats = _sync_users_to_account_aqc_group(db, sync_users)
        stats.update({f"shopMatch.{key}": value for key, value in shop_match_stats.items()})
        stats.update(sync_stats)
        db.commit()
    except FileNotFoundError as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "stats": None}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"导入失败: {exc}", "stats": None}

    return {
        "success": True,
        "message": "AQC-O 账号导入完成",
        "stats": stats,
    }


@router.post("/sync/account-aqc", response_model=AdminImportAqcOResponse)
def sync_account_aqc_group(
    _payload: AdminImportAqcORequest,
    _current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    try:
        users = db.execute(select(AqcUser)).scalars().all()
        sync_stats = _sync_users_to_account_aqc_group(db, users)
        db.commit()
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"同步失败: {exc}", "stats": None}

    message = "已完成 account 账户与 AQC 用户组同步"
    if sync_stats["syncFailed"] > 0:
        message = "同步完成，但存在部分失败"
    return {
        "success": True,
        "message": message,
        "stats": sync_stats,
    }


@router.post("/import/aqc-o-commerce", response_model=AdminImportAqcOResponse)
def import_aqco_commerce(
    payload: AdminImportAqcORequest,
    current_user: AqcUser = Depends(require_permissions("admin.import_legacy")),
    db: Session = Depends(get_db),
):
    sql_path = (payload.sqlPath or "").strip() or DEFAULT_AQCO_SQL_PATH
    try:
        stats = import_aqco_goods_shop_data(db, sql_path=sql_path, assigned_by=current_user.id)
        shop_match_stats = _sync_legacy_user_shops(
            db,
            db.execute(select(AqcUser).where(AqcUser.is_active.is_(True))).scalars().all(),
        )
        stats.update({f"shopMatch.{key}": value for key, value in shop_match_stats.items()})
        db.commit()
    except FileNotFoundError as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "stats": None}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"导入失败: {exc}", "stats": None}

    return {
        "success": True,
        "message": "AQC-O 商品与店铺导入完成",
        "stats": stats,
    }


@router.post("/import/aqc-o-sales", response_model=AdminImportAqcOResponse)
def import_aqco_sales(
    payload: AdminImportAqcORequest,
    current_user: AqcUser = Depends(require_permissions("admin.import_legacy")),
    db: Session = Depends(get_db),
):
    sql_path = (payload.sqlPath or "").strip() or DEFAULT_AQCO_SQL_PATH
    try:
        stats = import_aqco_sales_data(db, sql_path=sql_path, assigned_by=current_user.id)
        db.commit()
    except FileNotFoundError as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "stats": None}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"导入失败: {exc}", "stats": None}

    return {
        "success": True,
        "message": "AQC-O 销售数据导入完成",
        "stats": stats,
    }


@router.post("/import/aqc-o-full", response_model=AdminImportAqcOResponse)
def import_aqco_full(
    payload: AdminImportAqcORequest,
    current_user: AqcUser = Depends(require_permissions("admin.import_legacy")),
    db: Session = Depends(get_db),
):
    sql_path = (payload.sqlPath or "").strip() or DEFAULT_AQCO_SQL_PATH
    try:
        commerce_stats = import_aqco_goods_shop_data(db, sql_path=sql_path, assigned_by=current_user.id)
        admin_stats = import_aqco_admin_data(db, sql_path=sql_path, assigned_by=current_user.id)
        shop_match_stats = _sync_legacy_user_shops(
            db,
            db.execute(select(AqcUser).where(AqcUser.is_active.is_(True))).scalars().all(),
        )
        sales_stats = import_aqco_sales_data(db, sql_path=sql_path, assigned_by=current_user.id)
        sync_users = db.execute(select(AqcUser)).scalars().all()
        sync_stats = _sync_users_to_account_aqc_group(db, sync_users)
        db.commit()

        mirror_stats = import_aqco_full_mirror_data(
            db=db,
            sql_path=sql_path,
            table_prefix=DEFAULT_AQCO_MIRROR_PREFIX,
        )
        verify_stats = check_aqco_full_mirror_data(
            db=db,
            sql_path=sql_path,
            table_prefix=DEFAULT_AQCO_MIRROR_PREFIX,
        )
    except FileNotFoundError as exc:
        db.rollback()
        return {"success": False, "message": str(exc), "stats": None}
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"完整迁移失败: {exc}", "stats": None}

    stats: dict[str, Any] = {}
    for section_name, section_stats in (
        ("admin", admin_stats),
        ("commerce", commerce_stats),
        ("shopMatch", shop_match_stats),
        ("sales", sales_stats),
        ("sync", sync_stats),
        ("mirror", mirror_stats),
        ("verify", verify_stats),
    ):
        for key, value in section_stats.items():
            stats[f"{section_name}.{key}"] = value

    message = "AQC-O 完整迁移完成（业务表 + 全量镜像表）"
    if int(verify_stats.get("checkTablesMismatch", 0) or 0) > 0:
        message = "AQC-O 完整迁移完成，但镜像表存在对账差异"
    return {
        "success": True,
        "message": message,
        "stats": stats,
    }


@router.get("/check/aqc-o-full", response_model=AdminImportAqcOResponse)
def check_aqco_full(
    sqlPath: str | None = None,
    _current_user: AqcUser = Depends(require_permissions("admin.import_legacy")),
    db: Session = Depends(get_db),
):
    sql_path = (sqlPath or "").strip() or DEFAULT_AQCO_SQL_PATH
    try:
        verify_stats = check_aqco_full_mirror_data(
            db=db,
            sql_path=sql_path,
            table_prefix=DEFAULT_AQCO_MIRROR_PREFIX,
        )
    except FileNotFoundError as exc:
        return {"success": False, "message": str(exc), "stats": None}
    except Exception as exc:
        return {"success": False, "message": f"对账失败: {exc}", "stats": None}

    message = "AQC-O 全量镜像对账通过"
    if int(verify_stats.get("checkTablesMismatch", 0) or 0) > 0:
        message = "AQC-O 全量镜像对账存在差异"
    return {"success": True, "message": message, "stats": verify_stats}


@router.post("/users/sync-legacy-shops", response_model=AdminImportAqcOResponse)
def sync_legacy_user_shops(
    _payload: AdminImportAqcORequest,
    _current_user: AqcUser = Depends(require_permissions("admin.manage_users")),
    db: Session = Depends(get_db),
):
    try:
        users = db.execute(select(AqcUser).where(AqcUser.is_active.is_(True))).scalars().all()
        stats = _sync_legacy_user_shops(db, users)
        db.commit()
    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"门店匹配失败: {exc}", "stats": None}

    message = "旧账户门店匹配完成"
    if stats["updated"] <= 0:
        message = "未找到可自动匹配的旧账户门店"
    return {"success": True, "message": message, "stats": stats}

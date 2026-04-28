from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import CurrentAuth, get_current_auth, get_current_auth_optional, normalize_aqc_role_key, serialize_user, to_iso
from ..models import AqcAuthSession, AqcRole, AqcSymuseState, AqcUser, AqcUserIdentity, AqcUserRole
from ..schemas import (
    AuthCheckResponse,
    LocalLoginRequest,
    LoginResponse,
    MessageResponse,
    SessionListResponse,
    SymuseExchangeRequest,
    SymuseQrSessionApproveRequest,
    SymuseQrSessionInspectResponse,
    SymuseQrSessionRequest,
    SymuseStatePrepareRequest,
    SymuseStatePrepareResponse,
)
from ..security import (
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    normalize_role,
    normalize_username,
    validate_email,
    validate_username,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["auth"])


MANAGED_AQC_ROLE_SLUGS = ["admin", "sales-manager", "sales-entry", "sales-viewer", "goods-manager", "shop-manager"]


def _token_expire_at() -> datetime:
    return datetime.utcnow() + timedelta(days=settings.token_expire_days)


def _symuse_state_expire_at() -> datetime:
    ttl = max(60, settings.symuse_state_expire_seconds)
    return datetime.utcnow() + timedelta(seconds=ttl)


def _remote_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:45]
    if request.client and request.client.host:
        return request.client.host[:45]
    return ""


def _request_json(
    url: str,
    *,
    method: str = "POST",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {
        "Accept": "application/json",
        **(headers or {}),
    }
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    req = UrlRequest(
        url=url,
        data=body,
        method=method.upper(),
        headers=request_headers,
    )

    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw), None
    except HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            parsed = json.loads(raw)
            return None, parsed.get("message") or f"账号服务错误({exc.code})"
        except Exception:
            return None, f"账号服务错误({exc.code})"
    except URLError:
        return None, "无法连接账号服务"
    except Exception:
        return None, "账号服务响应异常"


def _post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    return _request_json(url, method="POST", payload=payload, headers=headers)


def _account_internal_headers() -> dict[str, str]:
    return {
        "X-Symuse-Client-Id": settings.symuse_client_id,
        "X-Symuse-Client-Secret": settings.symuse_client_secret,
    }


def _email_conflict_user_id(db: Session, email: str, exclude_user_id: int | None = None) -> int | None:
    stmt = select(AqcUser.id).where(AqcUser.email == email)
    if exclude_user_id is not None:
        stmt = stmt.where(AqcUser.id != exclude_user_id)
    return db.execute(stmt.limit(1)).scalar()


def _ensure_identity(user: AqcUser) -> None:
    if user.identity is None:
        user.identity = AqcUserIdentity(
            user_id=user.id,
            name=user.display_name,
            avatar=user.avatar_url,
            mobile=user.phone,
            sex=0,
            vip=user.vip,
        )
        return

    user.identity.name = user.display_name or user.identity.name
    user.identity.avatar = user.avatar_url or user.identity.avatar
    if user.phone and not user.identity.mobile:
        user.identity.mobile = user.phone
    user.identity.vip = user.vip


def _extract_aqc_role_from_symuse(symuse_user: dict[str, Any]) -> tuple[bool, str]:
    profile = symuse_user.get("aqcProfile")
    if not isinstance(profile, dict):
        return False, "aqc_departed"

    enabled = bool(profile.get("enabled"))
    role_key = normalize_aqc_role_key(profile.get("roleKey") or profile.get("role"))
    return enabled, role_key


def _resolve_unique_username(db: Session, base_username: str, exclude_user_id: int | None = None) -> str:
    base = normalize_username(base_username)[:50] or "symuse_user"
    if validate_username(base) is not None:
        base = "symuse_user"

    candidate = base
    index = 1
    while True:
        stmt = select(AqcUser.id).where(AqcUser.username == candidate)
        if exclude_user_id is not None:
            stmt = stmt.where(AqcUser.id != exclude_user_id)
        conflict_id = db.execute(stmt.limit(1)).scalar()
        if conflict_id is None:
            return candidate

        suffix = f"_{index}"
        trimmed = base[: max(2, 50 - len(suffix))]
        candidate = f"{trimmed}{suffix}"
        index += 1


def _sync_user_roles_from_aqc_role(db: Session, user: AqcUser, aqc_role_key: str) -> None:
    normalized_role = normalize_aqc_role_key(aqc_role_key)
    user.aqc_role_key = normalized_role
    roles = db.execute(select(AqcRole).where(AqcRole.slug.in_(MANAGED_AQC_ROLE_SLUGS))).scalars().all()
    managed_role_ids = {item.id for item in roles}
    existing_links = db.execute(select(AqcUserRole).where(AqcUserRole.user_id == user.id)).scalars().all()

    for link in existing_links:
        if link.role_id in managed_role_ids:
            db.delete(link)

    if normalized_role == "aqc_admin":
        user.role = "admin"
        user.vip = max(int(user.vip or 0), 2)
    elif user.role != "admin":
        user.role = "user"
        user.vip = 0


def _sync_symuse_user(db: Session, symuse_user: dict[str, Any], aqc_role_key: str) -> AqcUser:
    ext_user_id_raw = symuse_user.get("id")
    try:
        ext_user_id = int(ext_user_id_raw)
    except (TypeError, ValueError):
        raise ValueError("账号服务返回的用户ID无效")

    source_username = normalize_username(str(symuse_user.get("username") or f"symuse_{ext_user_id}"))
    if validate_username(source_username) is not None:
        source_username = f"symuse_{ext_user_id}"

    source_email = normalize_email(str(symuse_user.get("email") or ""))
    if validate_email(source_email) is not None:
        source_email = ""

    display_name = str(symuse_user.get("displayName") or source_username).strip()[:80] or source_username
    avatar_url = str(symuse_user.get("avatarUrl") or symuse_user.get("avatar") or "")[:500]
    phone = str(symuse_user.get("phone") or "").strip()[:20] or None
    role = normalize_role(symuse_user.get("role"))

    user = db.execute(select(AqcUser).where(AqcUser.external_user_id == ext_user_id).limit(1)).scalars().first()
    if user is None and source_email:
        user = db.execute(select(AqcUser).where(AqcUser.email == source_email).limit(1)).scalars().first()
    if user is None:
        user = db.execute(select(AqcUser).where(AqcUser.username == source_username).limit(1)).scalars().first()

    now = datetime.utcnow()
    if user is None:
        username = _resolve_unique_username(db, source_username)
        email = source_email or None
        if email:
            conflict_id = _email_conflict_user_id(db, email)
            if conflict_id is not None:
                email = None

        user = AqcUser(
            external_user_id=ext_user_id,
            username=username,
            email=email,
            password_hash=None,
            display_name=display_name,
            avatar_url=avatar_url,
            phone=phone,
            role=role,
            aqc_role_key=normalize_aqc_role_key(aqc_role_key),
            vip=2 if role == "admin" else 0,
            vip_level=0,
            user_rule_id=5,
            auth_source="symuse_account",
            is_active=True,
            last_login_at=now,
        )
        db.add(user)
        db.flush()
    else:
        user.external_user_id = ext_user_id
        user.auth_source = "symuse_account"
        user.display_name = display_name
        user.avatar_url = avatar_url
        user.phone = phone or user.phone
        user.last_login_at = now
        user.aqc_role_key = normalize_aqc_role_key(aqc_role_key)

        if user.role != "admin":
            user.role = role

        if source_email:
            conflict_id = _email_conflict_user_id(db, source_email, exclude_user_id=user.id)
            if conflict_id is None:
                user.email = source_email

    _sync_user_roles_from_aqc_role(db, user, aqc_role_key)
    _ensure_identity(user)
    return user


def _serialize_session(
    session_obj: AqcAuthSession,
    current_session_id: int | None = None,
    *,
    session_count: int = 1,
) -> dict[str, Any]:
    return {
        "id": session_obj.id,
        "userAgent": session_obj.user_agent,
        "ipAddress": session_obj.ip_address,
        "createdAt": to_iso(session_obj.created_at) or "",
        "lastUsedAt": to_iso(session_obj.last_used_at) or "",
        "expiresAt": to_iso(session_obj.expires_at) or "",
        "revokedAt": to_iso(session_obj.revoked_at),
        "isCurrent": current_session_id is not None and session_obj.id == current_session_id,
        "sessionCount": max(1, int(session_count)),
    }


def _session_group_key(session_obj: AqcAuthSession) -> tuple[str, str]:
    return (
        str(session_obj.user_agent or "").strip(),
        str(session_obj.ip_address or "").strip(),
    )


def _group_sessions(
    sessions: list[AqcAuthSession],
    current_session_id: int | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[AqcAuthSession]] = {}
    for row in sessions:
        grouped.setdefault(_session_group_key(row), []).append(row)

    payloads: list[dict[str, Any]] = []
    for rows in grouped.values():
        rows.sort(
            key=lambda item: (
                item.id == current_session_id,
                item.last_used_at or datetime.min,
                item.created_at or datetime.min,
                item.id,
            ),
            reverse=True,
        )
        representative = rows[0]
        payload = _serialize_session(representative, current_session_id, session_count=len(rows))
        created_values = [item.created_at for item in rows if item.created_at is not None]
        last_used_values = [item.last_used_at for item in rows if item.last_used_at is not None]
        expire_values = [item.expires_at for item in rows if item.expires_at is not None]
        revoked_values = [item.revoked_at for item in rows if item.revoked_at is not None]
        if created_values:
            payload["createdAt"] = to_iso(min(created_values)) or payload["createdAt"]
        if last_used_values:
            payload["lastUsedAt"] = to_iso(max(last_used_values)) or payload["lastUsedAt"]
        if expire_values:
            payload["expiresAt"] = to_iso(max(expire_values)) or payload["expiresAt"]
        payload["revokedAt"] = to_iso(max(revoked_values)) if revoked_values and len(revoked_values) == len(rows) else None
        payloads.append(payload)

    payloads.sort(
        key=lambda item: (
            bool(item.get("isCurrent")),
            str(item.get("lastUsedAt") or ""),
            int(item.get("id") or 0),
        ),
        reverse=True,
    )
    return payloads


def _build_symuse_auth_url(state: str, redirect_uri: str | None) -> str:
    params = {
        "client_id": settings.symuse_client_id,
        "state": state,
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri

    query = urlencode(params)
    sep = "&" if "?" in settings.symuse_auth_page else "?"
    return f"{settings.symuse_auth_page}{sep}{query}"


def _sanitize_return_path(value: str | None) -> str | None:
    clean = (value or "").strip()[:500]
    if not clean or clean.startswith("//"):
        return None
    if clean.startswith("/"):
        return clean
    return None


def _validate_state(
    db: Session,
    request: Request,
    raw_state: str | None,
) -> tuple[bool, str, AqcSymuseState | None]:
    if not raw_state:
        return False, "缺少 state 参数，请重新发起登录", None

    now = datetime.utcnow()
    state = (
        db.execute(
            select(AqcSymuseState)
            .where(
                AqcSymuseState.state_hash == hash_token(raw_state),
                AqcSymuseState.consumed_at.is_(None),
                AqcSymuseState.expires_at > now,
            )
            .limit(1)
        )
        .scalars()
        .first()
    )
    if state is None:
        return False, "登录回调校验失败，state 无效或已过期", None

    if settings.symuse_state_ip_strict:
        source_ip = _remote_ip(request)
        if state.ip_address and source_ip and source_ip != state.ip_address:
            return False, "登录回调来源异常，请重新发起登录", None

    return True, "ok", state


def _issue_session(
    db: Session,
    request: Request,
    user: AqcUser,
    *,
    message: str = "登录成功",
    consume_state: AqcSymuseState | None = None,
    redirect_to: str | None = None,
) -> dict[str, Any]:
    token = generate_token()
    expires_at = _token_expire_at()
    now = datetime.utcnow()

    user.last_login_at = now
    session = AqcAuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=(request.headers.get("user-agent") or "")[:255],
        ip_address=_remote_ip(request),
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()

    if consume_state is not None:
        consume_state.consumed_at = now
        consume_state.consumed_ip = _remote_ip(request)

    _ensure_identity(user)
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": message,
        "user": serialize_user(user, db),
        "token": token,
        "tokenType": "Bearer",
        "expiresAt": to_iso(expires_at),
        "sessionId": session.id,
        "redirectTo": redirect_to,
    }


@router.post("/symuse/state", response_model=SymuseStatePrepareResponse)
def prepare_symuse_state(
    payload: SymuseStatePrepareRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    raw_state = generate_token()
    expires_at = _symuse_state_expire_at()
    redirect_uri = (payload.redirectUri or "").strip()[:500] or None
    return_path = _sanitize_return_path(payload.returnPath)

    db.add(
        AqcSymuseState(
            state_hash=hash_token(raw_state),
            redirect_uri=redirect_uri,
            return_path=return_path,
            user_agent=(request.headers.get("user-agent") or "")[:255],
            ip_address=_remote_ip(request),
            expires_at=expires_at,
        )
    )
    db.commit()

    return {
        "success": True,
        "message": "登录 state 已生成",
        "state": raw_state,
        "expiresAt": to_iso(expires_at),
        "authPage": settings.symuse_auth_page,
        "authUrl": _build_symuse_auth_url(raw_state, redirect_uri),
    }


@router.post("/local-login", response_model=LoginResponse)
def local_login(
    payload: LocalLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not settings.enable_local_login:
        return {
            "success": False,
            "message": "当前环境已禁用本地登录，请使用 account.symuse.com 统一登录",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    account = payload.account.strip()
    username_account = normalize_username(account)
    email_account = normalize_email(account)

    stmt = (
        select(AqcUser)
        .where(
            or_(AqcUser.username == username_account, AqcUser.email == email_account),
            AqcUser.is_active.is_(True),
        )
        .limit(1)
    )
    user = db.execute(stmt).scalars().first()

    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        return {
            "success": False,
            "message": "账号或密码错误",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    return _issue_session(db, request, user)


@router.post("/symuse/exchange", response_model=LoginResponse)
def symuse_exchange(
    payload: SymuseExchangeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if settings.symuse_client_secret.startswith("replace"):
        return {
            "success": False,
            "message": "服务端未配置 SYMUSE_CLIENT_SECRET",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    symuse_state: AqcSymuseState | None = None
    if settings.symuse_state_required or payload.state:
        state_ok, state_msg, state_obj = _validate_state(db, request, payload.state)
        if not state_ok:
            return {
                "success": False,
                "message": state_msg,
                "user": None,
                "token": None,
                "tokenType": None,
                "expiresAt": None,
                "sessionId": None,
            }
        symuse_state = state_obj

    exchange_url = f"{settings.symuse_api_base}/auth/tickets/exchange"
    exchange_payload = {
        "clientId": settings.symuse_client_id,
        "clientSecret": settings.symuse_client_secret,
        "code": payload.code,
    }

    exchange_result, exchange_error = _post_json(exchange_url, exchange_payload)
    if exchange_error:
        return {
            "success": False,
            "message": exchange_error,
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    if not exchange_result or not exchange_result.get("success"):
        return {
            "success": False,
            "message": (exchange_result or {}).get("message") or "账号服务换取失败",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    symuse_user = exchange_result.get("user")
    if not isinstance(symuse_user, dict):
        return {
            "success": False,
            "message": "账号服务返回数据异常",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    aqc_enabled, aqc_role_key = _extract_aqc_role_from_symuse(symuse_user)
    if not aqc_enabled:
        return {
            "success": False,
            "message": "当前账号未开通 AQC 后台权限，请联系管理员先添加账号",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }

    try:
        user = _sync_symuse_user(db, symuse_user, aqc_role_key)

        if not user.is_active:
            return {
                "success": False,
                "message": "当前账号已被停用，请联系管理员",
                "user": None,
                "token": None,
                "tokenType": None,
                "expiresAt": None,
                "sessionId": None,
            }

        redirect_to = symuse_state.return_path if symuse_state is not None else None
        return _issue_session(db, request, user, consume_state=symuse_state, redirect_to=redirect_to)
    except ValueError as exc:
        db.rollback()
        return {
            "success": False,
            "message": str(exc),
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }
    except Exception:
        db.rollback()
        return {
            "success": False,
            "message": "同步账号失败，请稍后重试",
            "user": None,
            "token": None,
            "tokenType": None,
            "expiresAt": None,
            "sessionId": None,
        }


@router.post("/symuse/qr/inspect", response_model=SymuseQrSessionInspectResponse)
def inspect_symuse_qr_session(
    payload: SymuseQrSessionRequest,
):
    inspect_url = f"{settings.symuse_api_base}/auth/qr/sessions/inspect"
    inspect_result, inspect_error = _post_json(inspect_url, {"sessionToken": payload.sessionToken})
    if inspect_error:
        return {
            "success": False,
            "message": inspect_error,
            "status": "expired",
            "expiresAt": None,
            "serviceLabel": "",
            "deviceLabel": "",
            "scannedAt": None,
            "approvedAt": None,
            "isExpired": True,
        }
    if not inspect_result:
        return {
            "success": False,
            "message": "账号服务响应异常",
            "status": "expired",
            "expiresAt": None,
            "serviceLabel": "",
            "deviceLabel": "",
            "scannedAt": None,
            "approvedAt": None,
            "isExpired": True,
        }
    return {
        "success": bool(inspect_result.get("success")),
        "message": str(inspect_result.get("message") or "二维码状态已获取"),
        "status": str(inspect_result.get("status") or "pending"),
        "expiresAt": inspect_result.get("expiresAt"),
        "serviceLabel": str(inspect_result.get("serviceLabel") or ""),
        "deviceLabel": str(inspect_result.get("deviceLabel") or ""),
        "scannedAt": inspect_result.get("scannedAt"),
        "approvedAt": inspect_result.get("approvedAt"),
        "isExpired": bool(inspect_result.get("isExpired")),
    }


@router.post("/symuse/qr/scan", response_model=SymuseQrSessionInspectResponse)
def scan_symuse_qr_session(
    payload: SymuseQrSessionRequest,
):
    scan_url = f"{settings.symuse_api_base}/auth/qr/sessions/scan-internal"
    scan_result, scan_error = _post_json(
        scan_url,
        {"sessionToken": payload.sessionToken},
        headers=_account_internal_headers(),
    )
    if scan_error:
        return {
            "success": False,
            "message": scan_error,
            "status": "expired",
            "expiresAt": None,
            "serviceLabel": "",
            "deviceLabel": "",
            "scannedAt": None,
            "approvedAt": None,
            "isExpired": True,
        }
    if not scan_result:
        return {
            "success": False,
            "message": "账号服务响应异常",
            "status": "expired",
            "expiresAt": None,
            "serviceLabel": "",
            "deviceLabel": "",
            "scannedAt": None,
            "approvedAt": None,
            "isExpired": True,
        }
    return {
        "success": bool(scan_result.get("success")),
        "message": str(scan_result.get("message") or "二维码状态已更新"),
        "status": str(scan_result.get("status") or "pending"),
        "expiresAt": scan_result.get("expiresAt"),
        "serviceLabel": str(scan_result.get("serviceLabel") or ""),
        "deviceLabel": str(scan_result.get("deviceLabel") or ""),
        "scannedAt": scan_result.get("scannedAt"),
        "approvedAt": scan_result.get("approvedAt"),
        "isExpired": bool(scan_result.get("isExpired")),
    }


@router.post("/symuse/qr/approve", response_model=MessageResponse)
def approve_symuse_qr_session(
    payload: SymuseQrSessionApproveRequest,
    auth: CurrentAuth = Depends(get_current_auth),
):
    if auth.user.external_user_id is None:
        return {"success": False, "message": "当前 AQC 账号未绑定统一账号，无法确认扫码登录"}

    approve_url = f"{settings.symuse_api_base}/auth/qr/sessions/approve-internal"
    approve_result, approve_error = _post_json(
        approve_url,
        {
            "sessionToken": payload.sessionToken,
            "externalUserId": int(auth.user.external_user_id),
            "loginOnceOnly": bool(payload.loginOnceOnly),
        },
        headers=_account_internal_headers(),
    )
    if approve_error:
        return {"success": False, "message": approve_error}
    if not approve_result:
        return {"success": False, "message": "账号服务响应异常"}
    return {
        "success": bool(approve_result.get("success")),
        "message": str(approve_result.get("message") or "桌面端登录请求已确认"),
    }


@router.post("/symuse/qr/cancel", response_model=MessageResponse)
def cancel_symuse_qr_session(
    payload: SymuseQrSessionRequest,
):
    cancel_url = f"{settings.symuse_api_base}/auth/qr/sessions/cancel"
    cancel_result, cancel_error = _post_json(cancel_url, {"sessionToken": payload.sessionToken})
    if cancel_error:
        return {"success": False, "message": cancel_error}
    if not cancel_result:
        return {"success": False, "message": "账号服务响应异常"}
    return {
        "success": bool(cancel_result.get("success")),
        "message": str(cancel_result.get("message") or "桌面端登录请求已取消"),
    }


@router.post("/logout", response_model=MessageResponse)
def logout(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    auth.session.revoked_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "已退出登录"}


@router.post("/refresh", response_model=LoginResponse)
def refresh_auth(
    request: Request,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    auth.session.revoked_at = datetime.utcnow()
    return _issue_session(db, request, auth.user, message="登录状态已刷新")


@router.get("/check", response_model=AuthCheckResponse)
def check_auth(
    auth: CurrentAuth | None = Depends(get_current_auth_optional),
    db: Session = Depends(get_db),
):
    if auth is None:
        return {
            "success": True,
            "isAuthenticated": False,
            "user": None,
            "session": None,
        }
    return {
        "success": True,
        "isAuthenticated": True,
        "user": serialize_user(auth.user, db),
        "session": _serialize_session(auth.session, auth.session.id),
    }


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    sessions = (
        db.execute(
            select(AqcAuthSession)
            .where(AqcAuthSession.user_id == auth.user.id)
            .order_by(AqcAuthSession.created_at.desc(), AqcAuthSession.id.desc())
        )
        .scalars()
        .all()
    )
    return {
        "success": True,
        "sessions": _group_sessions(sessions, auth.session.id),
        "currentSessionId": auth.session.id,
    }


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
def revoke_session(
    session_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    target = (
        db.execute(
            select(AqcAuthSession)
            .where(
                AqcAuthSession.id == session_id,
                AqcAuthSession.user_id == auth.user.id,
            )
            .limit(1)
        )
        .scalars()
        .first()
    )
    if target is None:
        return {"success": False, "message": "会话不存在"}

    related_sessions = (
        db.execute(
            select(AqcAuthSession)
            .where(
                AqcAuthSession.user_id == auth.user.id,
                AqcAuthSession.user_agent == target.user_agent,
                AqcAuthSession.ip_address == target.ip_address,
                AqcAuthSession.revoked_at.is_(None),
            )
            .order_by(AqcAuthSession.id.desc())
        )
        .scalars()
        .all()
    )
    if not related_sessions:
        return {"success": True, "message": "会话已失效"}

    now = datetime.utcnow()
    for row in related_sessions:
        row.revoked_at = now
    db.commit()
    return {"success": True, "message": f"会话已下线，共 {len(related_sessions)} 条登录记录"}


@router.post("/sessions/revoke-others", response_model=MessageResponse)
def revoke_other_sessions(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(AqcAuthSession)
            .where(
                AqcAuthSession.user_id == auth.user.id,
                AqcAuthSession.id != auth.session.id,
                AqcAuthSession.revoked_at.is_(None),
            )
            .order_by(AqcAuthSession.id.desc())
        )
        .scalars()
        .all()
    )

    now = datetime.utcnow()
    for row in rows:
        row.revoked_at = now

    db.commit()
    return {"success": True, "message": f"已下线其他会话 {len(rows)} 个"}

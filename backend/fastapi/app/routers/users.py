from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .admin import _reset_account_user_password, _update_account_user
from ..database import get_db
from ..deps import AQC_ROLE_LABELS, CurrentAuth, get_aqc_role_key, get_current_auth, get_current_user, normalize_aqc_role_key, serialize_user, to_iso, user_shop_ids
from ..models import AqcGroup, AqcGroupMember, AqcUser, AqcUserIdentity
from ..schemas import (
    AccountPasswordChangeRequest,
    AccountProfileUpdateRequest,
    GroupOut,
    IdentityUpdateRequest,
    MeResponse,
    MessageResponse,
    MyGroupsResponse,
    UserOptionListResponse,
    UserOptionOut,
)
from ..security import hash_password, normalize_username, validate_password, validate_username
from ..config import settings


router = APIRouter(prefix="/users", tags=["users"])


def _to_group_out(group: AqcGroup, member_role: str | None = None, *, is_default: bool = False) -> GroupOut:
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        isActive=group.is_active,
        createdBy=group.created_by,
        createdAt=to_iso(group.created_at) or "",
        updatedAt=to_iso(group.updated_at) or "",
        memberRole=member_role,
        isDefault=bool(is_default),
    )


@router.get("/me", response_model=MeResponse)
def get_me(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    return {"success": True, "user": serialize_user(auth.user, db)}


@router.get("/options", response_model=UserOptionListResponse)
def list_user_options(
    q: str | None = None,
    limit: int = Query(default=120, ge=1, le=300),
    _user: AqcUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(AqcUser.id, AqcUser.username, AqcUser.display_name, AqcUser.aqc_role_key).where(AqcUser.is_active.is_(True))
    role_key = get_aqc_role_key(_user)
    if role_key == "aqc_departed":
        return {"success": True, "options": []}
    if role_key != "aqc_admin":
        scoped_shop_ids = user_shop_ids(_user)
        if scoped_shop_ids:
            stmt = stmt.where(AqcUser.shop_id.in_(scoped_shop_ids))
        else:
            stmt = stmt.where(AqcUser.id == _user.id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AqcUser.username.like(like),
                AqcUser.display_name.like(like),
            )
        )

    rows = db.execute(
        stmt.order_by(AqcUser.last_login_at.desc(), AqcUser.updated_at.desc(), AqcUser.id.desc()).limit(limit)
    ).all()
    options = []
    for row in rows:
        aqc_role_key = normalize_aqc_role_key(str(row[3] or "aqc_sales"))
        options.append(
            UserOptionOut(
                id=int(row[0]),
                username=str(row[1] or ""),
                displayName=str(row[2] or row[1] or ""),
                aqcRoleKey=aqc_role_key,
                aqcRoleName=AQC_ROLE_LABELS.get(aqc_role_key, AQC_ROLE_LABELS["aqc_sales"]),
            )
        )
    return {"success": True, "options": options}


@router.put("/me/identity")
def update_my_identity(
    payload: IdentityUpdateRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    user = auth.user
    identity = db.execute(select(AqcUserIdentity).where(AqcUserIdentity.user_id == user.id).limit(1)).scalars().first()
    if identity is None:
        identity = AqcUserIdentity(
            user_id=user.id,
            name=user.display_name,
            avatar=user.avatar_url,
            mobile=user.phone,
            sex=0,
            vip=user.vip,
        )
        db.add(identity)

    if payload.displayName is not None:
        user.display_name = payload.displayName.strip()[:80]
    if payload.avatarUrl is not None:
        user.avatar_url = payload.avatarUrl.strip()[:500]
    if payload.mobile is not None:
        mobile = payload.mobile.strip()[:20]
        user.phone = mobile or None
        identity.mobile = mobile or None
    if payload.sex is not None:
        identity.sex = payload.sex
    if payload.born is not None:
        identity.born = payload.born.strip()[:50] or None
    if payload.province is not None:
        identity.province = payload.province.strip()[:100] or None
    if payload.city is not None:
        identity.city = payload.city.strip()[:100] or None
    if payload.area is not None:
        identity.area = payload.area.strip()[:100] or None
    if payload.level is not None:
        identity.level = payload.level.strip()[:50] or None
    if payload.vip is not None:
        user.vip = payload.vip
        identity.vip = payload.vip
    if payload.vipLevel is not None:
        user.vip_level = payload.vipLevel
    if payload.userRuleId is not None:
        user.user_rule_id = payload.userRuleId

    identity.name = user.display_name or identity.name
    identity.avatar = user.avatar_url or identity.avatar

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": "资料更新成功",
        "user": serialize_user(user, db),
    }


@router.put("/me/account-profile", response_model=MessageResponse)
def update_my_account_profile(
    payload: AccountProfileUpdateRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    username = normalize_username(payload.username)
    username_error = validate_username(username)
    if username_error:
        return {"success": False, "message": username_error}

    exists = db.execute(select(AqcUser.id).where(AqcUser.username == username, AqcUser.id != auth.user.id).limit(1)).scalar()
    if exists is not None:
        return {"success": False, "message": "用户名已存在"}

    next_phone = (payload.phone or "").strip()[:20] or None
    next_display_name = payload.displayName.strip()[:80]

    if auth.user.external_user_id is not None and settings.symuse_aqc_sync_enabled:
        account_error = _update_account_user(
            external_user_id=int(auth.user.external_user_id),
            username=username,
            email=auth.user.email,
            phone=next_phone,
            display_name=next_display_name,
            is_active=auth.user.is_active,
        )
        if account_error:
            return {"success": False, "message": account_error}

    auth.user.username = username
    auth.user.phone = next_phone
    auth.user.display_name = next_display_name

    identity = db.execute(select(AqcUserIdentity).where(AqcUserIdentity.user_id == auth.user.id).limit(1)).scalars().first()
    if identity is None:
        identity = AqcUserIdentity(
            user_id=auth.user.id,
            name=auth.user.display_name,
            avatar=auth.user.avatar_url,
            mobile=auth.user.phone,
            sex=0,
            vip=auth.user.vip,
        )
        db.add(identity)
    else:
        identity.name = auth.user.display_name
        identity.mobile = auth.user.phone

    db.commit()
    db.refresh(auth.user)
    return {"success": True, "message": "账户信息已更新"}


@router.post("/me/account-password", response_model=MessageResponse)
def update_my_account_password(
    payload: AccountPasswordChangeRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    password_error = validate_password(payload.password)
    if password_error:
        return {"success": False, "message": password_error}

    if auth.user.external_user_id is not None and settings.symuse_aqc_sync_enabled:
        account_error = _reset_account_user_password(
            external_user_id=int(auth.user.external_user_id),
            password=payload.password,
        )
        if account_error:
            return {"success": False, "message": account_error}
    auth.user.password_hash = hash_password(payload.password)
    db.commit()
    return {"success": True, "message": "密码已更新"}


@router.get("/me/groups", response_model=MyGroupsResponse)
def get_my_groups(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AqcGroupMember, AqcGroup)
        .join(AqcGroup, AqcGroup.id == AqcGroupMember.group_id)
        .where(AqcGroupMember.user_id == auth.user.id, AqcGroup.is_active.is_(True))
        .order_by(AqcGroup.created_at.desc(), AqcGroup.id.desc())
    )
    rows = db.execute(stmt).all()

    groups = [_to_group_out(group, member.member_role) for member, group in rows]
    return {"success": True, "groups": groups}

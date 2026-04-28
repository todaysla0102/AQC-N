from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import CurrentAuth, get_current_auth, to_iso
from ..models import AqcGroup, AqcGroupMember, AqcNotification, AqcUser, AqcWorkOrder
from ..schemas import (
    GroupCreateRequest,
    GroupCreateResponse,
    GroupInviteRequest,
    GroupListResponse,
    GroupMemberAddRequest,
    GroupMembersResponse,
    GroupMemberOut,
    GroupOut,
    GroupUpdateRequest,
)


router = APIRouter(prefix="/groups", tags=["groups"])
DRAFT_STATUSES = {"draft", "rejected"}


def _is_global_admin(user: AqcUser) -> bool:
    return user.role == "admin" or user.vip == 2


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


def _clear_user_default_group(db: Session, user_id: int) -> None:
    rows = db.execute(
        select(AqcGroupMember).where(
            AqcGroupMember.user_id == int(user_id),
            AqcGroupMember.is_default.is_(True),
        )
    ).scalars().all()
    for row in rows:
        row.is_default = False


def _set_user_default_group(db: Session, *, user_id: int, group_id: int) -> None:
    membership = _get_member(db, group_id, user_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前用户不在该群组中")
    _clear_user_default_group(db, int(user_id))
    membership.is_default = True


def _get_group_or_404(db: Session, group_id: int) -> AqcGroup:
    group = db.execute(select(AqcGroup).where(AqcGroup.id == group_id).limit(1)).scalars().first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分组不存在")
    return group


def _get_member(db: Session, group_id: int, user_id: int) -> AqcGroupMember | None:
    stmt = (
        select(AqcGroupMember)
        .where(AqcGroupMember.group_id == group_id, AqcGroupMember.user_id == user_id)
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _can_manage_group(auth: CurrentAuth, membership: AqcGroupMember | None) -> bool:
    if _is_global_admin(auth.user):
        return True
    if membership is None:
        return False
    return membership.member_role in {"owner", "admin"}


def _normalize_invite_ids(user_ids: list[int], current_user_id: int) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for raw_id in user_ids or []:
        user_id = int(raw_id or 0)
        if user_id <= 0 or user_id == int(current_user_id) or user_id in seen:
            continue
        seen.add(user_id)
        result.append(user_id)
    return result


def _create_group_invitation_notifications(
    db: Session,
    *,
    group: AqcGroup,
    inviter: AqcUser,
    invite_user_ids: list[int],
) -> list[int]:
    normalized_ids = _normalize_invite_ids(invite_user_ids, inviter.id)
    if not normalized_ids:
        return []

    users = db.execute(
        select(AqcUser).where(AqcUser.id.in_(normalized_ids), AqcUser.is_active.is_(True))
    ).scalars().all()
    active_user_map = {int(item.id): item for item in users}
    created_ids: list[int] = []

    for user_id in normalized_ids:
        user = active_user_map.get(int(user_id))
        if user is None:
            continue
        if _get_member(db, group.id, int(user.id)) is not None:
            continue

        existing_pending = db.execute(
            select(AqcNotification.id).where(
                AqcNotification.user_id == int(user.id),
                AqcNotification.notification_type == "group_invite",
                AqcNotification.status == "pending",
                AqcNotification.related_type == "group",
                AqcNotification.related_id == int(group.id),
            ).limit(1)
        ).scalar()
        if existing_pending is not None:
            continue

        db.add(
            AqcNotification(
                user_id=int(user.id),
                notification_type="group_invite",
                title="群组邀请",
                content=f"{inviter.display_name or inviter.username} 邀请你加入群组「{group.name}」",
                status="pending",
                related_type="group",
                related_id=int(group.id),
                payload_json=json.dumps(
                    {
                        "groupId": int(group.id),
                        "groupName": group.name,
                        "inviterId": int(inviter.id),
                        "inviterName": inviter.display_name or inviter.username,
                    },
                    ensure_ascii=False,
                ),
                created_by=int(inviter.id),
                created_by_name=inviter.display_name or inviter.username,
            )
        )
        created_ids.append(int(user.id))

    return created_ids


def _attach_user_drafts_to_group(db: Session, *, user: AqcUser, group: AqcGroup) -> int:
    rows = db.execute(
        select(AqcWorkOrder)
        .where(
            AqcWorkOrder.applicant_id == int(user.id),
            AqcWorkOrder.status.in_(sorted(DRAFT_STATUSES)),
            AqcWorkOrder.shared_group_id.is_(None),
        )
    ).scalars().all()
    for order in rows:
        order.shared_group_id = int(group.id)
        order.shared_group_name = str(group.name or "")
        order.shared_by_id = int(user.id)
        order.shared_by_name = user.display_name or user.username or ""
    return len(rows)


@router.get("", response_model=GroupListResponse)
def list_groups(
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    if _is_global_admin(auth.user):
        rows = db.execute(
            select(AqcGroup)
            .where(AqcGroup.is_active.is_(True))
            .order_by(AqcGroup.created_at.desc(), AqcGroup.id.desc())
        ).scalars().all()
        groups = []
        for group in rows:
            member = _get_member(db, group.id, auth.user.id)
            groups.append(_to_group_out(group, member.member_role if member else None, is_default=bool(member.is_default) if member else False))
        return {"success": True, "groups": groups}

    stmt = (
        select(AqcGroupMember, AqcGroup)
        .join(AqcGroup, AqcGroup.id == AqcGroupMember.group_id)
        .where(AqcGroupMember.user_id == auth.user.id, AqcGroup.is_active.is_(True))
        .order_by(AqcGroup.created_at.desc(), AqcGroup.id.desc())
    )
    rows = db.execute(stmt).all()
    groups = [_to_group_out(group, member.member_role, is_default=bool(member.is_default)) for member, group in rows]
    return {"success": True, "groups": groups}


@router.post("", response_model=GroupCreateResponse)
def create_group(
    payload: GroupCreateRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    description = payload.description.strip()
    invite_user_ids = _normalize_invite_ids(payload.inviteUserIds, auth.user.id)

    if len(invite_user_ids) < 1:
        return {"success": False, "message": "群组至少需要邀请 1 名其他成员"}

    exists = db.execute(select(AqcGroup.id).where(AqcGroup.name == name).limit(1)).scalar()
    if exists is not None:
        return {"success": False, "message": "分组名称已存在"}

    group = AqcGroup(
        name=name,
        description=description,
        created_by=auth.user.id,
        is_active=True,
    )
    db.add(group)
    db.flush()
    db.add(
        AqcGroupMember(
            group_id=group.id,
            user_id=auth.user.id,
            member_role="owner",
            is_default=False,
        )
    )
    invited_user_ids = _create_group_invitation_notifications(
        db,
        group=group,
        inviter=auth.user,
        invite_user_ids=invite_user_ids,
    )
    _attach_user_drafts_to_group(db, user=auth.user, group=group)
    has_default = db.execute(
        select(AqcGroupMember.id).where(
            AqcGroupMember.user_id == int(auth.user.id),
            AqcGroupMember.is_default.is_(True),
        ).limit(1)
    ).scalar()
    if has_default is None:
        _set_user_default_group(db, user_id=int(auth.user.id), group_id=int(group.id))
    db.commit()
    db.refresh(group)

    return {
        "success": True,
        "message": "群组创建成功，邀请已发出",
        "group": _to_group_out(group, "owner", is_default=True if has_default is None else False),
        "invitedUserIds": invited_user_ids,
    }


@router.put("/{group_id}")
def update_group(
    group_id: int,
    payload: GroupUpdateRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, group_id)
    my_member = _get_member(db, group_id, auth.user.id)
    if not _can_manage_group(auth, my_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限管理该分组")

    if payload.name is not None:
        next_name = payload.name.strip()
        if next_name != group.name:
            exists = db.execute(
                select(AqcGroup.id).where(AqcGroup.name == next_name, AqcGroup.id != group.id).limit(1)
            ).scalar()
            if exists is not None:
                return {"success": False, "message": "分组名称已存在"}
            group.name = next_name

    if payload.description is not None:
        group.description = payload.description.strip()
    if payload.isActive is not None:
        group.is_active = payload.isActive

    db.commit()
    db.refresh(group)
    return {
        "success": True,
        "message": "分组更新成功",
        "group": _to_group_out(group, my_member.member_role if my_member else None, is_default=bool(my_member.is_default) if my_member else False),
    }


@router.get("/{group_id}/members", response_model=GroupMembersResponse)
def list_group_members(
    group_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, group_id)
    my_member = _get_member(db, group_id, auth.user.id)
    if not _is_global_admin(auth.user) and my_member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问该分组")

    stmt = (
        select(AqcGroupMember, AqcUser)
        .join(AqcUser, AqcUser.id == AqcGroupMember.user_id)
        .where(AqcGroupMember.group_id == group_id)
        .order_by(AqcGroupMember.created_at.asc(), AqcGroupMember.id.asc())
    )
    rows = db.execute(stmt).all()

    members = [
        GroupMemberOut(
            userId=user.id,
            username=user.username,
            displayName=user.display_name,
            avatarUrl=user.avatar_url,
            role=user.role,
            vip=user.vip,
            memberRole=member.member_role,
            joinedAt=to_iso(member.created_at) or "",
        )
        for member, user in rows
    ]

    return {
        "success": True,
        "group": _to_group_out(group, my_member.member_role if my_member else None, is_default=bool(my_member.is_default) if my_member else False),
        "members": members,
    }


@router.post("/{group_id}/members")
def add_group_member(
    group_id: int,
    payload: GroupMemberAddRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    _get_group_or_404(db, group_id)
    my_member = _get_member(db, group_id, auth.user.id)
    if not _can_manage_group(auth, my_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限管理该分组")

    user = db.execute(select(AqcUser).where(AqcUser.id == payload.userId, AqcUser.is_active.is_(True)).limit(1)).scalars().first()
    if user is None:
        return {"success": False, "message": "目标用户不存在或已停用"}

    member = _get_member(db, group_id, payload.userId)
    if member is None:
        member = AqcGroupMember(group_id=group_id, user_id=payload.userId, member_role=payload.memberRole)
        db.add(member)
    else:
        member.member_role = payload.memberRole

    _attach_user_drafts_to_group(db, user=user, group=_get_group_or_404(db, group_id))

    db.commit()
    return {"success": True, "message": "成员设置成功"}


@router.post("/{group_id}/default")
def set_default_group(
    group_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, group_id)
    member = _get_member(db, group_id, auth.user.id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号不在该分组中")
    _set_user_default_group(db, user_id=int(auth.user.id), group_id=int(group.id))
    db.commit()
    return {"success": True, "message": "默认群组已更新"}


@router.post("/{group_id}/invite")
def invite_group_members(
    group_id: int,
    payload: GroupInviteRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, group_id)
    my_member = _get_member(db, group_id, auth.user.id)
    if not _can_manage_group(auth, my_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限管理该分组")

    invited_user_ids = _create_group_invitation_notifications(
        db,
        group=group,
        inviter=auth.user,
        invite_user_ids=payload.userIds,
    )
    if not invited_user_ids:
        return {"success": False, "message": "没有新的可邀请成员"}

    db.commit()
    return {"success": True, "message": "邀请已发出", "invitedUserIds": invited_user_ids}


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    group = _get_group_or_404(db, group_id)
    my_member = _get_member(db, group_id, auth.user.id)
    if not _can_manage_group(auth, my_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限管理该分组")

    group.is_active = False
    draft_orders = db.execute(
        select(AqcWorkOrder).where(
            AqcWorkOrder.shared_group_id == int(group.id),
            AqcWorkOrder.status.in_(sorted(DRAFT_STATUSES)),
        )
    ).scalars().all()
    for order in draft_orders:
        order.shared_group_id = None
        order.shared_group_name = ""
        order.shared_by_id = None
        order.shared_by_name = ""
    db.commit()
    return {"success": True, "message": "群组已删除"}


@router.delete("/{group_id}/members/{user_id}")
def remove_group_member(
    group_id: int,
    user_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    _get_group_or_404(db, group_id)
    my_member = _get_member(db, group_id, auth.user.id)
    if not _can_manage_group(auth, my_member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限管理该分组")

    member = _get_member(db, group_id, user_id)
    if member is None:
        return {"success": False, "message": "成员不存在"}

    if member.member_role == "owner":
        owner_count = db.execute(
            select(func.count(AqcGroupMember.id)).where(
                AqcGroupMember.group_id == group_id,
                AqcGroupMember.member_role == "owner",
            )
        ).scalar_one()
        if owner_count <= 1:
            return {"success": False, "message": "至少需要保留一名 owner"}

    if bool(member.is_default):
        replacement = db.execute(
            select(AqcGroupMember)
            .join(AqcGroup, AqcGroup.id == AqcGroupMember.group_id)
            .where(
                AqcGroupMember.user_id == int(user_id),
                AqcGroupMember.group_id != int(group_id),
                AqcGroup.is_active.is_(True),
            )
            .order_by(AqcGroupMember.created_at.asc(), AqcGroupMember.id.asc())
            .limit(1)
        ).scalars().first()
        _clear_user_default_group(db, int(user_id))
        if replacement is not None:
            replacement.is_default = True

    db.delete(member)
    db.commit()
    return {"success": True, "message": "成员移除成功"}

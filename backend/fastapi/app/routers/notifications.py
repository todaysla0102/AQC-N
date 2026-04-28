from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import CurrentAuth, SHANGHAI_TZ, UTC_TZ, get_current_auth, to_iso
from ..models import AqcGroup, AqcGroupMember, AqcNotification, AqcWorkOrder
from ..schemas import MessageResponse, NotificationListResponse, NotificationOut, NotificationRespondRequest


router = APIRouter(prefix="/notifications", tags=["notifications"])
DRAFT_STATUSES = {"draft", "rejected"}
REPORT_NOTIFICATION_TYPE = "report_delivery"


def _parse_payload(raw: str | None) -> dict:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_notification_out(item: AqcNotification) -> NotificationOut:
    notification_type = str(item.notification_type or "")
    return NotificationOut(
        id=int(item.id),
        notificationType=notification_type,
        title=str(item.title or ""),
        content="" if notification_type == REPORT_NOTIFICATION_TYPE else str(item.content or ""),
        status=str(item.status or ""),
        isPersistent=bool(item.is_persistent),
        isRead=bool(item.is_read),
        relatedType=str(item.related_type or ""),
        relatedId=int(item.related_id) if item.related_id is not None else None,
        createdBy=int(item.created_by) if item.created_by is not None else None,
        createdByName=str(item.created_by_name or ""),
        createdAt=to_iso(item.created_at) or "",
        readAt=to_iso(item.read_at),
        handledAt=to_iso(item.handled_at),
        dismissedAt=to_iso(item.dismissed_at),
        payload=_parse_payload(item.payload_json),
    )


def _today_report_visibility_condition() -> tuple[datetime, datetime]:
    now_local = datetime.now(SHANGHAI_TZ)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(UTC_TZ).replace(tzinfo=None),
        end_local.astimezone(UTC_TZ).replace(tzinfo=None),
    )


def _attach_user_drafts_to_group(db: Session, *, user_id: int, user_name: str, group: AqcGroup) -> int:
    rows = db.execute(
        select(AqcWorkOrder).where(
            AqcWorkOrder.applicant_id == int(user_id),
            AqcWorkOrder.status.in_(sorted(DRAFT_STATUSES)),
            AqcWorkOrder.shared_group_id.is_(None),
        )
    ).scalars().all()
    for order in rows:
        order.shared_group_id = int(group.id)
        order.shared_group_name = str(group.name or "")
        order.shared_by_id = int(user_id)
        order.shared_by_name = str(user_name or "")
    return len(rows)


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None),
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    report_start_at, report_end_at = _today_report_visibility_condition()
    report_visible_condition = and_(
        AqcNotification.notification_type == REPORT_NOTIFICATION_TYPE,
        AqcNotification.created_at >= report_start_at,
        AqcNotification.created_at < report_end_at,
    )
    persistent_visible_condition = and_(
        AqcNotification.is_persistent.is_(True),
        AqcNotification.dismissed_at.is_(None),
        or_(
            AqcNotification.notification_type != REPORT_NOTIFICATION_TYPE,
            report_visible_condition,
        ),
    )
    stmt = select(AqcNotification).where(AqcNotification.user_id == auth.user.id)
    count_stmt = select(func.count(AqcNotification.id)).where(AqcNotification.user_id == auth.user.id)

    clean_status = str(status_filter or "").strip()
    if clean_status:
        if clean_status == "pending":
            filter_condition = and_(
                AqcNotification.is_persistent.is_(False),
                AqcNotification.status == clean_status,
            )
        elif clean_status == "report":
            filter_condition = persistent_visible_condition
        else:
            filter_condition = AqcNotification.status == clean_status
        stmt = stmt.where(filter_condition)
        count_stmt = count_stmt.where(filter_condition)
    else:
        visible_condition = or_(
            persistent_visible_condition,
            and_(
                AqcNotification.is_persistent.is_(False),
                AqcNotification.status == "pending",
            ),
        )
        stmt = stmt.where(visible_condition)
        count_stmt = count_stmt.where(visible_condition)

    rows = (
        db.execute(
            stmt.order_by(AqcNotification.created_at.desc(), AqcNotification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    total = int(db.execute(count_stmt).scalar() or 0)
    unread_count = int(
        db.execute(
            select(func.count(AqcNotification.id)).where(
                AqcNotification.user_id == auth.user.id,
                or_(
                    and_(
                        AqcNotification.is_persistent.is_(False),
                        AqcNotification.status == "pending",
                    ),
                    and_(
                        persistent_visible_condition,
                        AqcNotification.is_read.is_(False),
                    ),
                ),
            )
        ).scalar()
        or 0
    )
    return {
        "success": True,
        "total": total,
        "unreadCount": unread_count,
        "notifications": [_to_notification_out(item) for item in rows],
    }


@router.post("/{notification_id}/respond", response_model=MessageResponse)
def respond_notification(
    notification_id: int,
    payload: NotificationRespondRequest,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    notification = (
        db.execute(
            select(AqcNotification)
            .where(AqcNotification.id == notification_id, AqcNotification.user_id == auth.user.id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    if bool(notification.is_persistent):
        return {"success": False, "message": "该通知不需要审批"}
    if str(notification.status or "") != "pending":
        return {"success": False, "message": "该通知已处理"}

    if str(notification.notification_type or "") == "group_invite":
        group_id = int(notification.related_id or 0)
        group = db.execute(select(AqcGroup).where(AqcGroup.id == group_id).limit(1)).scalars().first()
        if group is None or not bool(group.is_active):
            notification.status = "rejected"
            notification.handled_at = datetime.utcnow()
            db.commit()
            return {"success": False, "message": "群组不存在或已停用"}

        if payload.accepted:
            membership = db.execute(
                select(AqcGroupMember)
                .where(AqcGroupMember.group_id == group_id, AqcGroupMember.user_id == auth.user.id)
                .limit(1)
            ).scalars().first()
            if membership is None:
                db.add(
                    AqcGroupMember(
                        group_id=group_id,
                        user_id=auth.user.id,
                        member_role="member",
                    )
                )
            _attach_user_drafts_to_group(
                db,
                user_id=int(auth.user.id),
                user_name=auth.user.display_name or auth.user.username or "",
                group=group,
            )
            notification.status = "accepted"
            notification.handled_at = datetime.utcnow()
            db.commit()
            return {"success": True, "message": f"已加入群组「{group.name}」"}

        notification.status = "rejected"
        notification.handled_at = datetime.utcnow()
        db.commit()
        return {"success": True, "message": f"已拒绝加入群组「{group.name}」"}

    notification.status = "accepted" if payload.accepted else "rejected"
    notification.handled_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "通知已处理"}


@router.post("/{notification_id}/read", response_model=MessageResponse)
def read_notification(
    notification_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    notification = (
        db.execute(
            select(AqcNotification)
            .where(AqcNotification.id == notification_id, AqcNotification.user_id == auth.user.id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    notification.is_read = True
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "通知已标记为已读"}


@router.post("/{notification_id}/dismiss", response_model=MessageResponse)
def dismiss_notification(
    notification_id: int,
    auth: CurrentAuth = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    notification = (
        db.execute(
            select(AqcNotification)
            .where(AqcNotification.id == notification_id, AqcNotification.user_id == auth.user.id)
            .limit(1)
        )
        .scalars()
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    if not bool(notification.is_persistent):
        return {"success": False, "message": "该通知暂不支持关闭"}
    notification.is_read = True
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
    notification.dismissed_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "通知已关闭"}

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any
from datetime import datetime
from app.database import get_async_session
from app.api.dependencies import get_current_user
from app.models.users import User
from app.models.timelogs import Timelog
from app.models.user_201_files import User201File
from app.models.document_types import DocumentType
from app.models.user_projects import UserProject
from app.models.notifications import Notification
from app.schemas.timelogs import TimelogResponse
from app.schemas.users import UserResponse


router = APIRouter(
    prefix="/notification",
    tags=["Notifications"],
    responses={404: {"description": "Not found"}},
)


@router.post("/record-approval")
async def record_timelog_approval(
    timelog_id: int,
    status_new: str = Query(..., description="'Approved' or 'Rejected'"),
    session: AsyncSession = Depends(get_async_session),
    approver: User = Depends(get_current_user),
):
    """
    Record a timelog approval/rejection action.
    Only Admin or Project Manager for the task's project can approve.
    """
    #print(f"DEBUG record_timelog_approval: timelog_id={timelog_id}, status_new={status_new}, approver_id={approver.id}")
    
    # Get the timelog
    timelog = await session.get(Timelog, timelog_id)
    if not timelog:
        #print(f"DEBUG: Timelog {timelog_id} not found")
        raise HTTPException(status_code=404, detail="Timelog not found")

    # Check authorization
    approver_role = (approver.role or "").lower()
    #print(f"DEBUG: approver_role={approver_role}, timelog.project_id={timelog.project_id}")
    
    # Admin can always approve
    if approver_role != "admin":
        # Check if user is project manager for this timelog's project
        if timelog.project_id:
            pm_check = await session.execute(
                select(UserProject.project_id).where(
                    UserProject.user_id == approver.id,
                    UserProject.project_id == timelog.project_id,
                    UserProject.role_in_project == "project_manager"
                )
            )
            if not pm_check.first():
                #print(f"DEBUG: User {approver.id} is not project manager for project {timelog.project_id}")
                raise HTTPException(status_code=403, detail="Not authorized to approve this timelog")
            #print(f"DEBUG: User {approver.id} is project manager for project {timelog.project_id}")
        else:
            # No project assigned, only admin can approve
            #print(f"DEBUG: Timelog has no project assigned")
            raise HTTPException(status_code=403, detail="Not authorized to approve this timelog")

    # Get timelog owner details
    owner = await session.get(User, timelog.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Timelog owner not found")

    # Create notification in database
    status_str = "Approved" if status_new == "Approved" else "Rejected"
    notification = Notification(
        recipient_id=owner.id,
        approver_id=approver.id,
        action="approved" if status_new == "Approved" else "rejected",
        item_type="timelog",
        item_id=timelog_id,
        item_title=f"{timelog.type.capitalize()} Entry",
        item_description=timelog.description or "No description",
        target_route=f"/tasks?status={status_str}&highlight={timelog_id}",
        is_read=0
    )
    session.add(notification)
    await session.commit()
    #print(f"DEBUG: Notification created - id={notification.id}, recipient={owner.id}, action={notification.action}")

    return {
        "status": "recorded",
        "notification_id": notification.id,
        "recipient_id": owner.id
    }


@router.post("/record-201-approval")
async def record_201_file_approval(
    file_id: int,
    status_new: str = Query(..., description="'Approved' or 'Declined'"),
    session: AsyncSession = Depends(get_async_session),
    approver: User = Depends(get_current_user),
):
    """
    Record a 201 file approval/decline action.
    """
    # Get the 201 file
    file = await session.get(User201File, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="201 file not found")

    # Get file owner details
    owner = await session.get(User, file.user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="File owner not found")

    # Resolve document type name (if available)
    doc_type_name = None
    try:
        if file.document_type_id:
            dt = await session.get(DocumentType, file.document_type_id)
            doc_type_name = dt.name if dt else None
    except Exception:
        doc_type_name = None

    # Create notification in database
    notification = Notification(
        recipient_id=owner.id,
        approver_id=approver.id,
        action="approved" if status_new == "Approved" else "declined",
        item_type="user201",
        item_id=file_id,
        item_title=doc_type_name or file.file_name or "201 File",
        item_description=file.file_name or "No description",
        target_route="/201-files",
        is_read=0
    )
    session.add(notification)
    await session.commit()

    return {
        "status": "recorded",
        "notification_id": notification.id,
        "recipient_id": owner.id
    }


@router.get("/mine")
async def get_my_notifications(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Get all notifications for the current user (that they've received from approval actions).
    """
    try:
        #print(f"DEBUG: Getting notifications for user {user.id}")
        
        stmt = select(Notification).where(
            Notification.recipient_id == user.id
        ).order_by(Notification.created_at.desc()).limit(100)
        
        result = await session.execute(stmt)
        notifications = result.scalars().all()
        #print(f"DEBUG: Found {len(notifications)} notifications")
        
        # Get approver details
        approver_ids = set(n.approver_id for n in notifications if n.approver_id)
        approvers = {}
        if approver_ids:
            stmt_approvers = select(User).where(User.id.in_(approver_ids))
            result_approvers = await session.execute(stmt_approvers)
            for approver in result_approvers.scalars():
                # Generate initials-based avatar URL
                first_initial = (approver.first_name[0] if approver.first_name else 'A').upper()
                last_initial = (approver.last_name[0] if approver.last_name else 'U').upper()
                initials = f"{first_initial}{last_initial}"
                # Use UI Avatars service to generate avatar from initials
                avatar_url = f"https://ui-avatars.com/api/?name={initials}&background=random&color=fff&size=32"
                
                approvers[approver.id] = {
                    "id": approver.id,
                    "name": f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.username,
                    "avatar_url": avatar_url
                }
        
        response_list = []
        for n in notifications:
            approver = approvers.get(n.approver_id, {})
            approver_avatar = approver.get("avatar_url")
            #print(f"DEBUG notification {n.id}: approver_id={n.approver_id}, avatar_url={approver_avatar}")
            try:
                response_list.append({
                    "id": n.id,
                    "recipient_id": n.recipient_id,
                    "approver_id": n.approver_id,
                    "approver_name": approver.get("name", "Unknown"),
                    "approver_avatar": approver_avatar,
                    "action": n.action,
                    "item_type": n.item_type,
                    "item_id": n.item_id,
                    "item_title": n.item_title,
                    "item_description": n.item_description,
                    "target_route": n.target_route,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                    "is_read": n.is_read
                })
            except Exception as e:
                #print(f"ERROR building notification {n.id}: {e}")
                raise
        
        #print(f"DEBUG: Returning {len(response_list)} notifications")
        return {
            "count": len(response_list),
            "notifications": response_list
        }
    except Exception as e:
        import traceback
        #print(f"ERROR in get_my_notifications: {e}")
        #print(traceback.format_exc())
        # Return empty list instead of error to avoid breaking the frontend
        return {
            "count": 0,
            "notifications": []
        }


@router.get("/status-updates")
async def get_timelog_status_updates(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Get recent timelog status updates for the current user (timelogs they submitted that were approved/rejected).
    """
    # Get all timelogs where user is the owner and status recently changed
    stmt = select(Timelog).where(
        Timelog.user_id == user.id,
        Timelog.status.in_(["Approved", "Rejected"])
    ).order_by(Timelog.approved_at.desc()).limit(50)

    result = await session.execute(stmt)
    timelogs = result.scalars().all()

    # Get approver details
    approver_ids = set(t.approver_id for t in timelogs if t.approver_id)
    approvers = {}
    if approver_ids:
        stmt = select(User).where(User.id.in_(approver_ids))
        result = await session.execute(stmt)
        for approver in result.scalars():
            approvers[approver.id] = {
                "id": approver.id,
                "name": f"{approver.first_name or ''} {approver.last_name or ''}".strip() or approver.username,
                "avatar_url": getattr(approver, "avatar_url", None)
            }

    updates = []
    for t in timelogs:
        if t.approver_id:
            approver = approvers.get(t.approver_id, {})
            updates.append({
                "timelog_id": t.id,
                "status": t.status,
                "approved_at": t.approved_at.isoformat() if t.approved_at else None,
                "approver_id": t.approver_id,
                "approver_name": approver.get("name", "Unknown"),
                "approver_avatar": approver.get("avatar_url"),
                "description": t.description or "No description",
                "type": t.type,
                "action": "approved" if t.status == "Approved" else "rejected",
                "target_route": f"/tasks?status={'Approved' if t.status == 'Approved' else 'Rejected'}&highlight={t.id}"
            })

    return {
        "count": len(updates),
        "updates": updates
    }


@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Mark a notification as read.
    """
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Ensure user can only mark their own notifications as read
    if notification.recipient_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    notification.is_read = 1
    await session.commit()
    
    return {"status": "success"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Delete a notification. Only the recipient can delete their own notifications.
    """
    notification = await session.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Ensure user can only delete their own notifications
    if notification.recipient_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    await session.delete(notification)
    await session.commit()
    
    return {"status": "deleted"}

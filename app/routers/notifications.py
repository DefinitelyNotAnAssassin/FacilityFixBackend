"""
Notification Router - API endpoints for notification management

Provides endpoints for:
- Retrieving user notifications
- Marking notifications as read
- Managing notification preferences
- Admin notification management
- Sending test notifications
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from ..auth.dependencies import get_current_user, require_role, require_admin
from ..services.notification_manager import notification_manager
from ..models.notification_models import (
    EnhancedNotification, NotificationType, NotificationPriority,
    NotificationChannel, DeliveryStatus, NotificationPreference
)
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class NotificationCreate(BaseModel):
    notification_type: NotificationType
    recipient_id: str
    title: str
    message: str
    sender_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    building_id: Optional[str] = None
    department: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: Optional[List[NotificationChannel]] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    requires_action: bool = False
    expires_at: Optional[datetime] = None
    custom_data: Optional[Dict[str, Any]] = None


class BulkNotificationCreate(BaseModel):
    notification_type: NotificationType
    recipient_ids: List[str]
    title: str
    message: str
    sender_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    building_id: Optional[str] = None
    department: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: Optional[List[NotificationChannel]] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    requires_action: bool = False
    expires_at: Optional[datetime] = None
    custom_data: Optional[Dict[str, Any]] = None


class MarkAsReadRequest(BaseModel):
    notification_ids: List[str]


class PreferenceUpdate(BaseModel):
    notification_type: str
    channels: List[NotificationChannel]


class TestNotificationRequest(BaseModel):
    recipient_id: str
    title: str
    message: str
    notification_type: NotificationType = NotificationType.SYSTEM_MAINTENANCE
    channels: List[NotificationChannel] = [NotificationChannel.IN_APP]


# ═══════════════════════════════════════════════════════════════════════════
# USER NOTIFICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[Dict[str, Any]])
async def get_user_notifications(
    unread_only: bool = Query(False, description="Return only unread notifications"),
    limit: int = Query(50, description="Maximum number of notifications to return"),
    offset: int = Query(0, description="Number of notifications to skip"),
    notification_type: Optional[str] = Query(None, description="Filter by notification type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for the current user"""
    try:
        user_id = current_user["uid"]
        user_role = current_user.get("role", "").lower()
        user_email = current_user.get("email", "")
        print(f"\n[GET_NOTIFICATIONS] USER ID: {user_id}, ROLE: {user_role}, EMAIL: {user_email}")
        
        # All users are stored with their uid as recipient_id in notifications
        recipient_id = user_id
        
        logger.info(f"FETCHING NOTIF: user_id={user_id}, role={user_role}, email={user_email}, recipient_id={recipient_id}, unread_only={unread_only}")
        
        # Build filters
        filters = [("recipient_id", "==", recipient_id)]
        
        if unread_only:
            filters.append(("is_read", "==", False))
        
        if notification_type:
            filters.append(("notification_type", "==", notification_type))
        
        if priority:
            filters.append(("priority", "==", priority))
        
        logger.info(f"FETCHING NOTIF FILTERS: {filters}")
        
        # Query notifications - fetch ALL without limit first, then we'll sort and apply limit
        success, notifications, error = await database_service.query_documents(
            COLLECTIONS['notifications'],
            filters=filters,
            limit=None  # Fetch all, we'll sort and paginate after
        )
        
        logger.info(f"FETCHING NOTIF RESULT: success={success}, count={len(notifications) if notifications else 0}, error={error}")
        print(f"[GET_NOTIFICATIONS] Query result: success={success}, count={len(notifications) if notifications else 0}")
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {error}")
        
        # Sort by created_at descending (newest first)
        if notifications:
            notifications.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Apply offset and limit to sorted results
        notifications = notifications[offset:offset + limit]
        
        logger.info(f"Returning {len(notifications)} notifications after pagination (offset={offset}, limit={limit})")
        print(f"[GET_NOTIFICATIONS] Found {len(notifications)} notifications for recipient_id: {recipient_id}")
        return notifications
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {str(e)}")

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str = Path(..., description="Notification ID"),
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific notification"""
    try:
        user_id = current_user["uid"]
        
        success, notification, error = await database_service.get_document(
            COLLECTIONS['notifications'],
            notification_id
        )
        
        if not success or not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Verify notification belongs to user (unless admin)
        if current_user.get("role") != "admin" and notification.get("recipient_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete the notification
        success, error = await database_service.delete_document(
            COLLECTIONS['notifications'],
            notification_id
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to delete notification: {error}")
        
        return {"message": "Notification deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete notification: {str(e)}")

@router.get("/unread-count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get count of unread notifications for the current user"""
    try:
        user_id = current_user["uid"]
        user_role = current_user.get("role", "").lower()
        
        # All users are stored with their uid as recipient_id in notifications
        recipient_id = user_id
        
        filters = [
            ("recipient_id", "==", recipient_id),
            ("is_read", "==", False)
        ]
        
        success, notifications, error = await database_service.query_documents(
            COLLECTIONS['notifications'],
            filters=filters
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to count notifications: {error}")
        
        return {"unread_count": len(notifications)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error counting unread notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to count notifications: {str(e)}")


@router.post("/mark-read")
async def mark_notifications_read(
    request: MarkAsReadRequest,
    current_user: dict = Depends(get_current_user)
):
    """Mark one or more notifications as read"""
    try:
        user_id = current_user["uid"]
        user_role = current_user.get("role", "").lower()
        
        # All users are stored with their uid as recipient_id in notifications
        recipient_id = user_id
        
        updated_count = 0
        
        for notification_id in request.notification_ids:
            # Verify notification belongs to user
            success, notification, error = await database_service.get_document(
                COLLECTIONS['notifications'],
                notification_id
            )
            
            if not success or not notification:
                logger.warning(f"Notification {notification_id} not found")
                continue
            
            if notification.get("recipient_id") != recipient_id:
                logger.warning(f"User {user_id} (recipient_id: {recipient_id}) attempted to mark notification {notification_id} as read (belongs to {notification.get('recipient_id')})")
                continue
            
            # Mark as read
            update_data = {
                "is_read": True,
                "read_at": datetime.utcnow()
            }
            
            success, error = await database_service.update_document(
                COLLECTIONS['notifications'],
                notification_id,
                update_data
            )
            
            if success:
                updated_count += 1
            else:
                logger.error(f"Failed to mark notification {notification_id} as read: {error}")
        
        return {
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error marking notifications as read: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to mark notifications as read: {str(e)}")


@router.patch("/mark-all-read")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user)
):
    """Mark all notifications as read for the current user"""
    try:
        user_id = current_user["uid"]
        
        # Get all unread notifications
        filters = [
            ("recipient_id", "==", user_id),
            ("is_read", "==", False)
        ]
        
        success, notifications, error = await database_service.query_documents(
            COLLECTIONS['notifications'],
            filters=filters
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {error}")
        
        updated_count = 0
        update_data = {
            "is_read": True,
            "read_at": datetime.utcnow()
        }
        
        for notification in notifications:
            notification_id = notification.get("id") or notification.get("_doc_id")
            if notification_id:
                success, error = await database_service.update_document(
                    COLLECTIONS['notifications'],
                    notification_id,
                    update_data
                )
                
                if success:
                    updated_count += 1
                else:
                    logger.error(f"Failed to mark notification {notification_id} as read: {error}")
        
        return {
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to mark all notifications as read: {str(e)}")


@router.get("/{notification_id}")
async def get_notification(
    notification_id: str = Path(..., description="Notification ID"),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific notification"""
    try:
        user_id = current_user["uid"]
        
        success, notification, error = await database_service.get_document(
            COLLECTIONS['notifications'],
            notification_id
        )
        
        if not success or not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Verify notification belongs to user (unless admin)
        if current_user.get("role") != "admin" and notification.get("recipient_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return notification
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notification: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION CREATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/create")
async def create_notification(
    request: NotificationCreate,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Create a new notification (Admin/Staff only)"""
    try:
        success, notification_id, error = await notification_manager.create_notification(
            notification_type=request.notification_type,
            recipient_id=request.recipient_id,
            title=request.title,
            message=request.message,
            sender_id=request.sender_id or current_user["uid"],
            related_entity_type=request.related_entity_type,
            related_entity_id=request.related_entity_id,
            building_id=request.building_id,
            department=request.department,
            priority=request.priority,
            channels=request.channels,
            action_url=request.action_url,
            action_label=request.action_label,
            requires_action=request.requires_action,
            expires_at=request.expires_at,
            custom_data=request.custom_data,
            send_immediately=True
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to create notification: {error}")
        
        return {
            "success": True,
            "notification_id": notification_id,
            "message": "Notification created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create notification: {str(e)}")


@router.post("/create-bulk")
async def create_bulk_notifications(
    request: BulkNotificationCreate,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Create notifications for multiple recipients (Admin only)"""
    try:
        success, notification_ids, error = await notification_manager.create_bulk_notifications(
            notification_type=request.notification_type,
            recipient_ids=request.recipient_ids,
            title=request.title,
            message=request.message,
            sender_id=request.sender_id or current_user["uid"],
            related_entity_type=request.related_entity_type,
            related_entity_id=request.related_entity_id,
            building_id=request.building_id,
            department=request.department,
            priority=request.priority,
            channels=request.channels,
            action_url=request.action_url,
            action_label=request.action_label,
            requires_action=request.requires_action,
            expires_at=request.expires_at,
            custom_data=request.custom_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to create bulk notifications: {error}")
        
        return {
            "success": True,
            "notification_ids": notification_ids,
            "count": len(notification_ids),
            "message": f"Created {len(notification_ids)} notifications successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating bulk notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create bulk notifications: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/admin/all")
async def get_all_notifications(
    limit: int = Query(100, description="Maximum number of notifications to return"),
    offset: int = Query(0, description="Number of notifications to skip"),
    recipient_id: Optional[str] = Query(None, description="Filter by recipient"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_admin)
):
    """Get all notifications (Admin only)"""
    try:
        filters = []
        
        if recipient_id:
            filters.append(("recipient_id", "==", recipient_id))
        
        if notification_type:
            filters.append(("notification_type", "==", notification_type))
        
        if is_read is not None:
            filters.append(("is_read", "==", is_read))
        
        success, notifications, error = await database_service.query_documents(
            COLLECTIONS['notifications'],
            filters=filters if filters else None,
            limit=limit
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {error}")
        
        # Sort by created_at descending
        notifications.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        
        # Apply offset
        notifications = notifications[offset:]
        
        return {
            "notifications": notifications,
            "count": len(notifications)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving all notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {str(e)}")


@router.get("/admin/stats")
async def get_notification_stats(
    days: int = Query(7, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_admin)
):
    """Get notification statistics (Admin only)"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all notifications from the specified period
        success, notifications, error = await database_service.query_documents(
            COLLECTIONS['notifications']
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve notifications: {error}")
        
        # Filter by date and calculate stats
        recent_notifications = [
            n for n in notifications 
            if n.get('created_at') and n['created_at'] >= start_date
        ]
        
        total_count = len(recent_notifications)
        read_count = len([n for n in recent_notifications if n.get('is_read', False)])
        unread_count = total_count - read_count
        
        # Group by type
        type_stats = {}
        for notification in recent_notifications:
            notif_type = notification.get('notification_type', 'unknown')
            if notif_type not in type_stats:
                type_stats[notif_type] = 0
            type_stats[notif_type] += 1
        
        # Group by priority
        priority_stats = {}
        for notification in recent_notifications:
            priority = notification.get('priority', 'normal')
            if priority not in priority_stats:
                priority_stats[priority] = 0
            priority_stats[priority] += 1
        
        return {
            "period_days": days,
            "total_notifications": total_count,
            "read_notifications": read_count,
            "unread_notifications": unread_count,
            "read_percentage": (read_count / total_count * 100) if total_count > 0 else 0,
            "notifications_by_type": type_stats,
            "notifications_by_priority": priority_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving notification stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notification stats: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
# TEST AND UTILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/test")
async def send_test_notification(
    request: TestNotificationRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_admin)
):
    """Send a test notification (Admin only)"""
    try:
        success, notification_id, error = await notification_manager.create_notification(
            notification_type=request.notification_type,
            recipient_id=request.recipient_id,
            title=request.title,
            message=request.message,
            sender_id=current_user["uid"],
            channels=request.channels,
            send_immediately=True
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to send test notification: {error}")
        
        return {
            "success": True,
            "notification_id": notification_id,
            "message": "Test notification sent successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send test notification: {str(e)}")


@router.get("/types")
async def get_notification_types():
    """Get all available notification types"""
    return {
        "notification_types": [
            {
                "value": nt.value,
                "name": nt.value.replace("_", " ").title(),
                "category": nt.value.split("_")[0].title()
            }
            for nt in NotificationType
        ]
    }


@router.get("/channels")
async def get_notification_channels():
    """Get all available notification channels"""
    return {
        "channels": [
            {
                "value": ch.value,
                "name": ch.value.replace("_", " ").title(),
                "description": _get_channel_description(ch)
            }
            for ch in NotificationChannel
        ]
    }


def _get_channel_description(channel: NotificationChannel) -> str:
    """Get human-readable description for notification channel"""
    descriptions = {
        NotificationChannel.IN_APP: "Show in application notifications panel",
        NotificationChannel.PUSH: "Push notification to mobile/browser",
        NotificationChannel.EMAIL: "Email notification",
        NotificationChannel.SMS: "SMS notification (future)",
        NotificationChannel.WEBSOCKET: "Real-time websocket notification"
    }
    return descriptions.get(channel, "Unknown channel")

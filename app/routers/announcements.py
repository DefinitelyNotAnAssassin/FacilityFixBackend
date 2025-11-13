from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..models.database_models import Announcement
from ..services.announcement_service import announcement_service
from ..services.notification_manager import notification_manager
from ..auth.dependencies import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/announcements", tags=["announcements"])

# Request/Response Models
class CreateAnnouncementRequest(BaseModel):
    building_id: str = Field(..., description="Building ID where announcement applies")
    title: str = Field(..., min_length=1, max_length=200, description="Announcement title")
    content: str = Field(..., min_length=1, description="Full announcement content")
    type: str = Field(default="general", description="Type: maintenance, reminder, event, policy, emergency, general")
    audience: str = Field(default="all", description="Target audience: tenants, staff, admins, all, department, specific_users")
    location_affected: Optional[str] = Field(None, description="Specific location affected")
    send_notifications: bool = Field(default=True, description="Send push/websocket notifications")
    send_email: bool = Field(default=False, description="Send email notifications")
    
    # Enhanced targeting
    target_departments: Optional[List[str]] = Field(None, description="List of department names to target")
    target_user_ids: Optional[List[str]] = Field(None, description="List of specific user IDs to target")
    target_roles: Optional[List[str]] = Field(None, description="List of roles to target: tenant, staff, admin")
    
    # Scheduling and priority
    priority_level: str = Field(default="normal", description="Priority: low, normal, high, urgent, critical")
    scheduled_publish_date: Optional[datetime] = Field(None, description="When to publish (None = now)")
    expiry_date: Optional[datetime] = Field(None, description="When announcement expires")
    is_published: bool = Field(default=True, description="False for drafts, True to publish")
    
    # Additional metadata
    attachments: Optional[List[str]] = Field(None, description="List of attachment URLs")
    tags: Optional[List[str]] = Field(None, description="Searchable tags")

class UpdateAnnouncementRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    type: Optional[str] = Field(None)
    audience: Optional[str] = Field(None)
    location_affected: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    notify_changes: bool = Field(default=False, description="Send notifications about update")
    
    # Enhanced targeting updates
    target_departments: Optional[List[str]] = Field(None)
    target_user_ids: Optional[List[str]] = Field(None)
    target_roles: Optional[List[str]] = Field(None)
    
    # Scheduling and priority updates
    priority_level: Optional[str] = Field(None)
    scheduled_publish_date: Optional[datetime] = Field(None)
    expiry_date: Optional[datetime] = Field(None)
    is_published: Optional[bool] = Field(None)
    
    # Metadata updates
    attachments: Optional[List[str]] = Field(None)
    tags: Optional[List[str]] = Field(None)

class AnnouncementResponse(BaseModel):
    id: str
    formatted_id: Optional[str] = None
    created_by: str
    building_id: str
    title: str
    content: str
    type: str
    audience: str
    location_affected: Optional[str]
    is_active: bool

    # Enhanced targeting
    target_departments: Optional[List[str]] = []
    target_user_ids: Optional[List[str]] = []
    target_roles: Optional[List[str]] = []

    # Scheduling and priority
    priority_level: str = "normal"
    scheduled_publish_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    is_published: bool = True

    # Additional metadata
    attachments: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    view_count: int = 0
    read_by: Optional[List[str]] = []  # List of user IDs who have read this announcement
    is_read: bool = False  # Whether current user has read this announcement

    # Timestamps
    date_added: datetime
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class AnnouncementListResponse(BaseModel):
    announcements: List[AnnouncementResponse]
    total_count: int
    building_id: str
    audience_filter: str

class AnnouncementStatsResponse(BaseModel):
    total_announcements: int
    active_announcements: int
    inactive_announcements: int
    type_breakdown: dict
    audience_breakdown: dict
    building_id: str
    generated_at: str

# API Endpoints

@router.post("/", response_model=dict)
async def create_announcement(
    request: CreateAnnouncementRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create new announcement (Admin only)"""
    # Verify user is admin
    
    logger.info("CURRENT USER: ", current_user)
    print("CURRENT USER: ", current_user)
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can create announcements")
    
    try:
        success, announcement_id, error = await announcement_service.create_announcement(
            created_by=current_user['uid'],
            building_id=request.building_id,
            title=request.title,
            content=request.content,
            announcement_type=request.type,
            audience=request.audience,
            location_affected=request.location_affected,
            send_notifications=request.send_notifications,
            send_email=request.send_email,
            target_departments=request.target_departments,
            target_user_ids=request.target_user_ids,
            target_roles=request.target_roles,
            priority_level=request.priority_level,
            scheduled_publish_date=request.scheduled_publish_date,
            expiry_date=request.expiry_date,
            is_published=request.is_published,
            attachments=request.attachments,
            tags=request.tags
        )
        
        if success:
            logger.info(f"Announcement created: {announcement_id} by {current_user['uid']}")

            # Notification broadcasting is handled inside the AnnouncementService
            # when an announcement is published (immediate or scheduled). Do not
            # call the notification manager here to avoid duplicate notifications.

            return {
                "success": True,
                "announcement_id": announcement_id,
                "message": "Announcement created and broadcast successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=error)
            
    except Exception as e:
        logger.error(f"Error creating announcement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create announcement: {str(e)}")

@router.get("/", response_model=AnnouncementListResponse)
async def get_announcements(
    building_id: str = Query("default_building", description="Building ID to filter by"),
    audience: str = Query("all", description="Audience filter: tenants, staff, admins, all"),
    active_only: bool = Query(True, description="Return only active announcements"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of announcements"),
    announcement_type: Optional[str] = Query(None, description="Filter by type"),
    priority_level: Optional[str] = Query(None, description="Filter by priority"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    published_only: bool = Query(True, description="Return only published announcements"),
    current_user: dict = Depends(get_current_user)
):
    """Get announcements for building with advanced filtering"""
    try:

        print("CURRENT USER: ", current_user)
        logger.info(f"Fetching announcements for building_id: {building_id}")
        # Get user details
        user_role = current_user.get('role', 'tenant')
        user_id = current_user.get('uid')
        user_department = current_user.get('department')

        # Parse tags
        tag_list = [t.strip() for t in tags.split(',')] if tags else None

        # If user is not admin, show only published announcements they have access to
        if user_role != 'admin':
            published_only = True
            # Use their own targeting context
            announcements = await announcement_service.get_announcements(

                limit=limit,

            )
        else:
            # Admin can see all announcements including drafts
            announcements = await announcement_service.get_announcements()

        # Add is_read field based on current user
        for ann in announcements:
            read_by = ann.get('read_by', [])
            ann['is_read'] = user_id in read_by

        return AnnouncementListResponse(
            announcements=[AnnouncementResponse(**ann) for ann in announcements],
            total_count=len(announcements),
            building_id=building_id,
            audience_filter=audience
        )

    except Exception as e:
        logger.error(f"Error getting announcements: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get announcements: {str(e)}")

@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str = Path(..., description="Announcement ID"),
    current_user: dict = Depends(get_current_user)

):
    """Get specific announcement by ID"""
    try:
        print("ANNOUNCEMENT ID: ", announcement_id)
        announcement = await announcement_service.get_announcement_by_id(announcement_id)

        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")

        # Check if user has access to this announcement
        user_role = current_user.get('role', 'tenant')
        user_id = current_user.get('uid')
        announcement_audience = announcement.get('audience', 'all')

        # Allow access if:
        # 1. User is admin (can see all)
        # 2. Announcement is for 'all'
        # 3. Announcement audience matches user role
        if (user_role != 'admin' and
            announcement_audience != 'all' and
            announcement_audience != user_role):
            raise HTTPException(status_code=403, detail="Access denied to this announcement")

        # Add is_read field based on current user
        read_by = announcement.get('read_by', [])
        announcement['is_read'] = user_id in read_by

        return AnnouncementResponse(**announcement)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get announcement: {str(e)}")

@router.put("/{announcement_id}", response_model=dict)
async def update_announcement(
    announcement_id: str = Path(..., description="Announcement ID"),
    request: UpdateAnnouncementRequest = None,
    current_user: dict = Depends(get_current_user)
):
    """Update announcement (Admin only)"""
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can update announcements")
    
    try:
        # Convert request to updates dict, excluding None values
        updates = {}
        for field, value in request.dict().items():
            if field != 'notify_changes' and value is not None:
                updates[field] = value
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        success, error = await announcement_service.update_announcement(
            announcement_id=announcement_id,
            updated_by=current_user['uid'],
            updates=updates,
            notify_changes=request.notify_changes
        )
        
        if success:
            logger.info(f"Announcement {announcement_id} updated by {current_user['uid']}")

            # Send notifications if requested
            if request.notify_changes:
                try:
                    # Get the updated announcement to send notifications
                    announcement = await announcement_service.get_announcement_by_id(announcement_id)
                    if announcement:
                        await notification_manager.notify_announcement_published(
                            announcement_id=announcement_id,
                            title=f"Updated: {announcement.get('title', 'Announcement')}",
                            content=announcement.get('content', ''),
                            target_audience=announcement.get('audience', 'all'),
                            target_roles=announcement.get('target_roles'),
                            target_departments=announcement.get('target_departments'),
                            target_user_ids=announcement.get('target_user_ids'),
                            building_id=announcement.get('building_id'),
                            priority=announcement.get('priority_level', 'normal'),
                            announcement_type=announcement.get('type', 'general')
                        )
                        logger.info(f"Update notifications sent for announcement {announcement_id}")
                except Exception as notif_error:
                    logger.error(f"Failed to send update notifications: {str(notif_error)}")

            return {
                "success": True,
                "message": "Announcement updated successfully",
                "notify_changes": request.notify_changes
            }
        else:
            if "not found" in error.lower():
                raise HTTPException(status_code=404, detail=error)
            else:
                raise HTTPException(status_code=500, detail=error)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update announcement: {str(e)}")

@router.delete("/{announcement_id}", response_model=dict)
async def deactivate_announcement(
    announcement_id: str = Path(..., description="Announcement ID"),
    notify_deactivation: bool = Query(False, description="Send notifications about deactivation"),
    current_user: dict = Depends(get_current_user)
):
    """Deactivate announcement (soft delete) - Admin only"""
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can deactivate announcements")
    
    try:
        success, error = await announcement_service.deactivate_announcement(
            announcement_id=announcement_id,
            deactivated_by=current_user['uid'],
            notify_deactivation=notify_deactivation
        )
        
        if success:
            logger.info(f"Announcement {announcement_id} deactivated by {current_user['uid']}")
            return {
                "success": True,
                "message": "Announcement deactivated successfully",
                "notify_deactivation": notify_deactivation
            }
        else:
            if "not found" in error.lower():
                raise HTTPException(status_code=404, detail=error)
            else:
                raise HTTPException(status_code=500, detail=error)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to deactivate announcement: {str(e)}")


@router.delete("/{announcement_id}/hard", response_model=dict)
async def hard_delete_announcement(
    announcement_id: str = Path(..., description="Announcement ID to permanently delete"),
    current_user: dict = Depends(get_current_user)
):
    """Permanently delete an announcement (Admin only). This performs a hard delete from the database.

    Note: Use with caution as this removes the document and its audit trail.
    """
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can permanently delete announcements")

    try:
        # Ensure announcement exists
        announcement = await announcement_service.get_announcement_by_id(announcement_id)
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")

        # Use the shared database instance on the service to delete the doc.
        success, error = await announcement_service.db.delete_document(
            COLLECTIONS['announcements'],
            announcement_id
        )

        if not success:
            logger.error(f"Failed to hard-delete announcement {announcement_id}: {error}")
            raise HTTPException(status_code=500, detail=f"Failed to delete announcement: {error}")

        logger.info(f"Announcement permanently deleted: {announcement_id} by {current_user.get('uid')}")
        return {"success": True, "message": "Announcement permanently deleted", "announcement_id": announcement_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error hard-deleting announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to permanently delete announcement: {str(e)}")

@router.get("/building/{building_id}/stats", response_model=AnnouncementStatsResponse)
async def get_announcement_statistics(
    building_id: str = Path(..., description="Building ID"),
    current_user: dict = Depends(get_current_user)
):
    """Get announcement statistics for building (Admin only)"""
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can access announcement statistics")
    
    try:
        stats = await announcement_service.get_announcement_statistics(building_id)
        
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])
        
        return AnnouncementStatsResponse(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting announcement statistics for building {building_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

@router.post("/{announcement_id}/rebroadcast", response_model=dict)
async def rebroadcast_announcement(
    announcement_id: str = Path(..., description="Announcement ID"),
    send_email: bool = Query(False, description="Include email in rebroadcast"),
    current_user: dict = Depends(get_current_user)
):
    """Rebroadcast existing announcement (Admin only)"""
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can rebroadcast announcements")
    
    try:
        # Get existing announcement
        announcement = await announcement_service.get_announcement_by_id(announcement_id)
        
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        if not announcement.get('is_active', True):
            raise HTTPException(status_code=400, detail="Cannot rebroadcast inactive announcement")

        # Rebroadcast the announcement using notification manager
        await notification_manager.notify_announcement_published(
            announcement_id=announcement_id,
            title=announcement.get('title', 'Announcement'),
            content=announcement.get('content', ''),
            target_audience=announcement.get('audience', 'all'),
            target_roles=announcement.get('target_roles'),
            target_departments=announcement.get('target_departments'),
            target_user_ids=announcement.get('target_user_ids'),
            building_id=announcement.get('building_id'),
            priority=announcement.get('priority_level', 'normal'),
            announcement_type=announcement.get('type', 'general')
        )

        logger.info(f"Announcement {announcement_id} rebroadcast by {current_user['uid']}")

        return {
            "success": True,
            "message": "Announcement rebroadcast successfully",
            "announcement_id": announcement_id,
            "included_email": send_email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rebroadcasting announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to rebroadcast announcement: {str(e)}")

@router.post("/{announcement_id}/view", response_model=dict)
async def mark_announcement_viewed(
    announcement_id: str = Path(..., description="Announcement ID"),
    current_user: dict = Depends(get_current_user)
):
    """Mark announcement as viewed by user (increments view count)"""
    try:
        user_id = current_user.get('uid')
        success = await announcement_service.increment_view_count(announcement_id, user_id)
        
        if success:
            return {
                "success": True,
                "message": "View count incremented"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to increment view count")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking announcement viewed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/targeted", response_model=AnnouncementListResponse)
async def get_user_targeted_announcements(
    building_id: str = Query(..., description="Building ID"),
    active_only: bool = Query(True, description="Return only active announcements"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of announcements"),
    current_user: dict = Depends(get_current_user)
):
    """Get all announcements specifically targeted to the current user"""
    try:
        user_id = current_user.get('uid')

        announcements = await announcement_service.get_user_targeted_announcements(
            user_id=user_id,
            building_id=building_id,
            active_only=active_only,
            limit=limit
        )

        # Add is_read field based on current user
        for ann in announcements:
            read_by = ann.get('read_by', [])
            ann['is_read'] = user_id in read_by

        return AnnouncementListResponse(
            announcements=[AnnouncementResponse(**ann) for ann in announcements],
            total_count=len(announcements),
            building_id=building_id,
            audience_filter="targeted"
        )

    except Exception as e:
        logger.error(f"Error getting user targeted announcements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/publish-scheduled", response_model=dict)
async def publish_scheduled_announcements(
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger publishing of scheduled announcements (Admin only)"""
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can publish scheduled announcements")
    
    try:
        count = await announcement_service.publish_scheduled_announcements()
        
        return {
            "success": True,
            "announcements_published": count,
            "message": f"Published {count} scheduled announcement(s)"
        }
        
    except Exception as e:
        logger.error(f"Error publishing scheduled announcements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/expire-old", response_model=dict)
async def expire_old_announcements(
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger expiration of old announcements (Admin only)"""
    # Verify user is admin
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Only administrators can expire announcements")
    
    try:
        count = await announcement_service.expire_old_announcements()
        
        return {
            "success": True,
            "announcements_expired": count,
            "message": f"Expired {count} announcement(s)"
        }
        
    except Exception as e:
        logger.error(f"Error expiring announcements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/types/available", response_model=dict)
async def get_available_announcement_types(
    current_user: dict = Depends(get_current_user)
):
    """Get available announcement types, audiences, priorities, and other metadata"""
    return {
        "announcement_types": [
            {"value": "general", "label": "General Announcement"},
            {"value": "maintenance", "label": "Maintenance Notice"},
            {"value": "reminder", "label": "Reminder"},
            {"value": "event", "label": "Event Notification"},
            {"value": "policy", "label": "Policy Update"},
            {"value": "emergency", "label": "Emergency Alert"}
        ],
        "audiences": [
            {"value": "all", "label": "All Users"},
            {"value": "tenants", "label": "Tenants Only"},
            {"value": "staff", "label": "Staff Only"},
            {"value": "admins", "label": "Administrators Only"},
            {"value": "department", "label": "Specific Departments"},
            {"value": "specific_users", "label": "Specific Users"}
        ],
        "priority_levels": [
            {"value": "low", "label": "Low Priority"},
            {"value": "normal", "label": "Normal Priority"},
            {"value": "high", "label": "High Priority"},
            {"value": "urgent", "label": "Urgent"},
            {"value": "critical", "label": "Critical"}
        ],
        "departments": [
            {"value": "maintenance", "label": "Maintenance"},
            {"value": "security", "label": "Security"},
            {"value": "housekeeping", "label": "Housekeeping"},
            {"value": "administration", "label": "Administration"},
            {"value": "management", "label": "Management"}
        ],
        "user_role": current_user.get('role', 'tenant')
    }

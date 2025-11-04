from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging
import uuid

from ..models.database_models import Announcement
from ..database.database_service import database_service, COLLECTIONS
from ..database.collections import COLLECTIONS
from .notification_service import notification_service
from .email_service import email_service
from .websocket_service import websocket_notification_service
from .announcement_id_service import announcement_id_service

logger = logging.getLogger(__name__)

class AnnouncementService:
    """Service for managing announcements and broadcasting them via multiple channels"""
    
    def __init__(self):
        self.db = database_service
        self.notification_service = notification_service
    
    async def create_announcement(
        self,
        created_by: str,
        building_id: str,
        title: str,
        content: str,
        announcement_type: str = "general",
        audience: str = "all",
        location_affected: Optional[str] = None,
        send_notifications: bool = True,
        send_email: bool = False,
        target_departments: Optional[List[str]] = None,
        target_user_ids: Optional[List[str]] = None,
        target_roles: Optional[List[str]] = None,
        priority_level: str = "normal",
        scheduled_publish_date: Optional[datetime] = None,
        expiry_date: Optional[datetime] = None,
        is_published: bool = True,
        attachments: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Create new announcement and broadcast it via multiple channels
        
        Args:
            created_by: Admin user ID creating the announcement
            building_id: Building where announcement applies
            title: Short headline for the announcement
            content: Full announcement message
            announcement_type: Type of announcement (maintenance, reminder, event, policy, general)
            audience: Target audience (tenants, staff, admins, all, department, specific_users)
            location_affected: Specific location/area affected
            send_notifications: Whether to send push/websocket notifications
            send_email: Whether to send email notifications
            target_departments: List of specific departments to target
            target_user_ids: List of specific user IDs to target
            target_roles: List of specific roles to target
            priority_level: Priority level (low, normal, high, urgent, critical)
            scheduled_publish_date: When to publish (None = publish immediately)
            expiry_date: When announcement expires and auto-deactivates
            is_published: False for drafts, True to publish
            attachments: List of attachment URLs
            tags: List of searchable tags
            
        Returns:
            (success, announcement_id, error_message)
        """
        try:
            formatted_id = await announcement_id_service.generate_announcement_id()
            
            # Generate unique announcement ID for database
            announcement_id = str(uuid.uuid4())
            
            # Determine if announcement should be published now
            now = datetime.now(timezone.utc)
            
            # Ensure scheduled_publish_date is timezone-aware if provided
            if scheduled_publish_date and scheduled_publish_date.tzinfo is None:
                scheduled_publish_date = scheduled_publish_date.replace(tzinfo=timezone.utc)
            
            # Ensure expiry_date is timezone-aware if provided  
            if expiry_date and expiry_date.tzinfo is None:
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)
            
            should_publish_now = is_published and (scheduled_publish_date is None or scheduled_publish_date <= now)
            
            # Create announcement data
            announcement_data = {
                "id": announcement_id,
                "formatted_id": formatted_id,  # Add formatted ID
                "created_by": created_by,
                "building_id": building_id,
                "title": title,
                "content": content,
                "type": announcement_type,
                "audience": audience,
                "location_affected": location_affected,
                "is_active": True,
                
                # Enhanced targeting
                "target_departments": target_departments or [],
                "target_user_ids": target_user_ids or [],
                "target_roles": target_roles or [],
                
                # Scheduling and priority
                "priority_level": priority_level,
                "scheduled_publish_date": scheduled_publish_date,
                "expiry_date": expiry_date,
                "is_published": should_publish_now,
                
                # Additional metadata
                "attachments": attachments or [],
                "tags": tags or [],
                "view_count": 0,
                "read_by": [],  # Track which users have read this announcement

                # Timestamps
                "date_added": now,
                "published_at": now if should_publish_now else None,
                "created_at": now,
                "updated_at": now
            }
            
            # Save to database using the UUID as the document ID
            # This ensures the document can be retrieved using the 'id' field
            success, doc_id, error = await self.db.create_document(
                COLLECTIONS['announcements'],
                announcement_data,
                document_id=announcement_id  # Use our UUID as the Firestore document ID
            )
            
            if not success:
                return False, None, f"Failed to create announcement: {error}"
            
            logger.info(f"Announcement created: {formatted_id} ({announcement_id}) by {created_by}")
            
            # Broadcast announcement via notification channels only if published immediately
            if should_publish_now and (send_notifications or send_email):
                await self._broadcast_announcement(
                    announcement_data, 
                    send_notifications=send_notifications,
                    send_email=send_email
                )
            elif not should_publish_now:
                logger.info(f"Announcement {formatted_id} created as draft or scheduled for later")
            
            return True, announcement_id, None
            
        except Exception as e:
            logger.error(f"Error creating announcement: {str(e)}")
            return False, None, str(e)
    
    async def get_announcements(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get announcements for a specific building with advanced filtering
        
        Args:
            limit: Maximum number of announcements to return
            
        Returns:
            List of announcement dictionaries
        """
        try:
        
            # Query announcements
            success, announcements, error = await self.db.query_documents(
                COLLECTIONS['announcements'],
                limit=1000  
            )
            
            if not success:
                logger.error(f"Failed to get announcements: {error}")
                return []
            
            # Apply limit
            return announcements[:limit]
                
        except Exception as e:
            logger.error(f"Error getting announcements: {str(e)}")
            return []
    
    async def get_announcement_by_id(self, announcement_id: str) -> Optional[Dict[str, Any]]:
        """Get specific announcement by ID"""
        try:
            # First try to get by document ID directly (faster)
            success, announcement, error = await self.db.get_document(
                COLLECTIONS['announcements'],
                announcement_id
            )
            
            if success and announcement:
                return announcement
            
            # Fallback: query by 'id' field (for legacy documents)
            success, announcements, error = await self.db.query_collection(
                COLLECTIONS['announcements'],
                [("id", "==", announcement_id)]  # Must be a list of tuples
            )
            
            if success and announcements:
                return announcements[0] if announcements else None
            else:
                logger.error(f"Failed to get announcement {announcement_id}: {error}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting announcement {announcement_id}: {str(e)}")
            return None
    
    async def update_announcement(
        self,
        announcement_id: str,
        updated_by: str,
        updates: Dict[str, Any],
        notify_changes: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Update existing announcement
        
        Args:
            announcement_id: ID of announcement to update
            updated_by: User ID making the update
            updates: Dictionary of fields to update
            notify_changes: Whether to send notifications about the update
            
        Returns:
            (success, error_message)
        """
        try:
            # Get existing announcement
            existing = await self.get_announcement_by_id(announcement_id)
            if not existing:
                return False, "Announcement not found"
            
            # Add update metadata
            updates['updated_at'] = datetime.now(timezone.utc)
            
            # Update in database
            success, error = await self.db.update_document(
                COLLECTIONS['announcements'],
                announcement_id,
                updates
            )
            
            if not success:
                return False, f"Failed to update announcement: {error}"
            
            logger.info(f"Announcement {announcement_id} updated by {updated_by}")
            
            # Send update notifications if requested
            if notify_changes and existing.get('is_active', True):
                updated_announcement = {**existing, **updates}
                await self._broadcast_announcement_update(updated_announcement)
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error updating announcement {announcement_id}: {str(e)}")
            return False, str(e)
    
    async def deactivate_announcement(
        self,
        announcement_id: str,
        deactivated_by: str,
        notify_deactivation: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Deactivate an announcement (soft delete)
        
        Args:
            announcement_id: ID of announcement to deactivate
            deactivated_by: User ID performing the deactivation
            notify_deactivation: Whether to notify about deactivation
            
        Returns:
            (success, error_message)
        """
        try:
            updates = {
                'is_active': False,
                'updated_at': datetime.now(timezone.utc)
            }
            
            success, error = await self.update_announcement(
                announcement_id,
                deactivated_by,
                updates,
                notify_changes=notify_deactivation
            )
            
            if success:
                logger.info(f"Announcement {announcement_id} deactivated by {deactivated_by}")
            
            return success, error
            
        except Exception as e:
            logger.error(f"Error deactivating announcement {announcement_id}: {str(e)}")
            return False, str(e)
    
    async def _broadcast_announcement(
        self,
        announcement_data: Dict[str, Any],
        send_notifications: bool = True,
        send_email: bool = False
    ):
        """
        Broadcast announcement via multiple notification channels
        
        Args:
            announcement_data: Announcement data dictionary
            send_notifications: Send push and websocket notifications
            send_email: Send email notifications
        """
        try:
            building_id = announcement_data['building_id']
            audience = announcement_data['audience']
            title = announcement_data['title']
            content = announcement_data['content']
            announcement_type = announcement_data['type']
            
            # Get enhanced targeting parameters
            target_departments = announcement_data.get('target_departments', [])
            target_user_ids = announcement_data.get('target_user_ids', [])
            target_roles = announcement_data.get('target_roles', [])
            
            # Get target users based on advanced targeting
            target_users = await self._get_target_users(
                building_id, 
                audience,
                target_departments=target_departments,
                target_user_ids=target_user_ids,
                target_roles=target_roles
            )
            
            if not target_users:
                logger.warning(f"No target users found for announcement in building {building_id}")
                return
            
            # Send WebSocket real-time updates
            if send_notifications:
                await self._send_websocket_announcement(announcement_data)
            
            # Send push notifications and in-app notifications
            if send_notifications:
                await self._send_push_notifications(announcement_data, target_users)
            
            # Send email notifications
            if send_email:
                await self._send_email_announcements(announcement_data, target_users)
            
            logger.info(f"Announcement broadcast completed for {len(target_users)} users")
            
        except Exception as e:
            logger.error(f"Error broadcasting announcement: {str(e)}")
    
    def _is_announcement_visible_to_user(
        self,
        announcement: Dict[str, Any],
        audience_filter: str,
        user_id: Optional[str],
        user_role: Optional[str],
        user_department: Optional[str]
    ) -> bool:
        """
        Check if announcement should be visible to user based on targeting rules
        
        Visibility logic:
        1. If target_user_ids is set and not empty, only those users see it
        2. If target_departments is set and not empty, only users in those departments see it
        3. If target_roles is set and not empty, only users with those roles see it
        4. Otherwise, fall back to audience field (all, tenants, staff, admins)
        """
        # Specific user targeting takes highest priority
        target_user_ids = announcement.get('target_user_ids', [])
        if target_user_ids:
            return user_id in target_user_ids
        
        # Department targeting
        target_departments = announcement.get('target_departments', [])
        if target_departments and user_department:
            if user_department not in target_departments:
                return False
        
        # Role targeting
        target_roles = announcement.get('target_roles', [])
        if target_roles and user_role:
            if user_role not in target_roles:
                return False
        
        # Audience-based filtering (backward compatibility)
        audience = announcement.get('audience', 'all')
        if audience == 'all':
            return True
        elif audience == 'tenants' and user_role == 'tenant':
            return True
        elif audience == 'staff' and user_role == 'staff':
            return True
        elif audience == 'admins' and user_role == 'admin':
            return True
        elif audience == audience_filter:
            return True
        
        return audience == 'all'
    
    async def _get_target_users(
        self, 
        building_id: str, 
        audience: str,
        target_departments: Optional[List[str]] = None,
        target_user_ids: Optional[List[str]] = None,
        target_roles: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get target users based on building and advanced targeting criteria"""
        try:
            # If specific users are targeted, fetch only those
            if target_user_ids:
                all_users = []
                for uid in target_user_ids:
                    success, user, error = await self.db.get_document(
                        COLLECTIONS['user_profiles'],
                        uid
                    )
                    if success and user:
                        all_users.append(user)
                return all_users
            
            # Build base filters
            filters = [
                ('building_id', '==', building_id),
                ('status', '==', 'active')
            ]
            
            # Query all users, then filter in memory for complex conditions
            success, users, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                filters
            )
            
            if not success:
                logger.error(f"Failed to get target users: {error}")
                return []
            
            filtered_users = []
            
            for user in users:
                # Department filtering
                if target_departments:
                    user_dept = user.get('department')
                    if user_dept not in target_departments:
                        continue
                
                # Role filtering
                if target_roles:
                    user_role = user.get('role')
                    if user_role not in target_roles:
                        continue
                elif audience != 'all':
                    # Legacy audience filtering
                    user_role = user.get('role')
                    if audience == 'tenants' and user_role != 'tenant':
                        continue
                    elif audience == 'staff' and user_role != 'staff':
                        continue
                    elif audience == 'admins' and user_role != 'admin':
                        continue
                
                filtered_users.append(user)
            
            return filtered_users
                
        except Exception as e:
            logger.error(f"Error getting target users: {str(e)}")
            return []
    
    async def _send_websocket_announcement(self, announcement_data: Dict[str, Any]):
        """Send announcement via WebSocket for real-time updates"""
        try:
            await websocket_notification_service.send_announcement(announcement_data)
            logger.info(f"WebSocket announcement sent: {announcement_data['id']}")
        except Exception as e:
            logger.error(f"Error sending WebSocket announcement: {str(e)}")
    
    async def _send_push_notifications(
        self,
        announcement_data: Dict[str, Any],
        target_users: List[Dict[str, Any]]
    ):
        """Send push notifications and create in-app notifications for users"""
        try:
            title = announcement_data['title']
            content = announcement_data['content']
            announcement_type = announcement_data['type']
            announcement_id = announcement_data['id']
            
            # Create notifications for each target user
            for user in target_users:
                user_id = user.get('id') or user.get('user_id')
                if user_id:
                    # Create comprehensive notification (push + in-app + websocket)
                    await notification_service.create_notification(
                        user_id=user_id,
                        title=title,
                        message=content,
                        notification_type=f"announcement_{announcement_type}",
                        related_id=announcement_id,
                        send_push=True,
                        send_email=False,  # Email handled separately
                        send_websocket=False  # Already sent via broadcast
                    )
            
            logger.info(f"Push notifications sent for announcement {announcement_id}")
            
        except Exception as e:
            logger.error(f"Error sending push notifications: {str(e)}")
    
    async def _send_email_announcements(
        self,
        announcement_data: Dict[str, Any],
        target_users: List[Dict[str, Any]]
    ):
        """Send email announcements to target users"""
        try:
            # Prepare recipients list
            recipients = []
            for user in target_users:
                email = user.get('email')
                name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                if email and name:
                    recipients.append({"email": email, "name": name})
            
            if not recipients:
                logger.warning("No email recipients found for announcement")
                return
            
            # Send bulk email announcement
            result = await email_service.send_announcement_email(
                announcement_data,
                recipients
            )
            
            logger.info(f"Email announcements sent: {result}")
            
        except Exception as e:
            logger.error(f"Error sending email announcements: {str(e)}")
    
    async def _broadcast_announcement_update(self, announcement_data: Dict[str, Any]):
        """Broadcast announcement updates via WebSocket"""
        try:
            update_message = {
                "type": "announcement_updated",
                "data": announcement_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            building_id = announcement_data['building_id']
            audience = announcement_data['audience']
            
            if audience == 'all':
                await websocket_notification_service.manager.broadcast_to_building(
                    building_id, update_message
                )
            else:
                await websocket_notification_service.manager.broadcast_to_role(
                    audience, update_message, building_id
                )
            
            logger.info(f"Announcement update broadcast sent: {announcement_data['id']}")
            
        except Exception as e:
            logger.error(f"Error broadcasting announcement update: {str(e)}")
    
    async def publish_scheduled_announcements(self) -> int:
        """
        Check for scheduled announcements that should be published now
        Returns the number of announcements published
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Get unpublished announcements with scheduled date
            filters = [
                ('is_published', '==', False),
                ('is_active', '==', True),
                ('scheduled_publish_date', '<=', now)
            ]
            
            success, announcements, error = await self.db.query_documents(
                COLLECTIONS['announcements'],
                filters,
                limit=100
            )
            
            if not success:
                logger.error(f"Failed to get scheduled announcements: {error}")
                return 0
            
            published_count = 0
            
            for announcement in announcements:
                # Update to published status
                updates = {
                    'is_published': True,
                    'published_at': now,
                    'updated_at': now
                }
                
                success, error = await self.db.update_document(
                    COLLECTIONS['announcements'],
                    announcement['id'],
                    updates
                )
                
                if success:
                    # Broadcast the announcement
                    announcement.update(updates)
                    await self._broadcast_announcement(announcement)
                    published_count += 1
                    logger.info(f"Published scheduled announcement: {announcement.get('formatted_id')}")
            
            return published_count
            
        except Exception as e:
            logger.error(f"Error publishing scheduled announcements: {str(e)}")
            return 0
    
    async def expire_old_announcements(self) -> int:
        """
        Check for announcements past their expiry date and deactivate them
        Returns the number of announcements expired
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Get active announcements with expiry date passed
            filters = [
                ('is_active', '==', True),
                ('expiry_date', '<=', now)
            ]
            
            success, announcements, error = await self.db.query_documents(
                COLLECTIONS['announcements'],
                filters,
                limit=100
            )
            
            if not success:
                logger.error(f"Failed to get expired announcements: {error}")
                return 0
            
            expired_count = 0
            
            for announcement in announcements:
                success, error = await self.deactivate_announcement(
                    announcement['id'],
                    'system',
                    notify_deactivation=False
                )
                
                if success:
                    expired_count += 1
                    logger.info(f"Expired announcement: {announcement.get('formatted_id')}")
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Error expiring announcements: {str(e)}")
            return 0
    
    async def increment_view_count(self, announcement_id: str, user_id: str) -> bool:
        """
        Mark announcement as read by user and increment view count

        Args:
            announcement_id: The announcement document ID
            user_id: The user who viewed the announcement

        Returns:
            True if successful, False otherwise
        """
        try:
            announcement = await self.get_announcement_by_id(announcement_id)
            if not announcement:
                logger.warning(f"Announcement {announcement_id} not found when marking as read")
                return False

            # Get current read_by list
            read_by = announcement.get('read_by', [])

            # Only update if user hasn't already read it
            if user_id not in read_by:
                read_by.append(user_id)
                current_count = announcement.get('view_count', 0)

                updates = {
                    'read_by': read_by,
                    'view_count': current_count + 1,
                    'updated_at': datetime.now(timezone.utc)
                }

                success, error = await self.db.update_document(
                    COLLECTIONS['announcements'],
                    announcement_id,
                    updates
                )

                if success:
                    logger.info(f"User {user_id} marked announcement {announcement_id} as read")
                else:
                    logger.error(f"Failed to mark announcement as read: {error}")

                return success
            else:
                # Already read by this user, no update needed
                logger.debug(f"Announcement {announcement_id} already read by user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Error marking announcement as read: {str(e)}")
            return False
    
    async def get_user_targeted_announcements(
        self,
        user_id: str,
        building_id: str,
        active_only: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all announcements visible to a specific user
        """
        try:
            # Get user profile to know their role and department
            success, user, error = await self.db.get_document(
                COLLECTIONS['user_profiles'],
                user_id
            )
            
            if not success or not user:
                logger.error(f"Failed to get user profile for {user_id}")
                return []
            
            user_role = user.get('role', 'tenant')
            user_department = user.get('department')
            
            return await self.get_announcements(
                building_id=building_id,
                audience='all',
                active_only=active_only,
                limit=limit,
                user_id=user_id,
                user_role=user_role,
                user_department=user_department,
                published_only=True
            )
            
        except Exception as e:
            logger.error(f"Error getting user targeted announcements: {str(e)}")
            return []
    
    async def get_announcement_statistics(self, building_id: str) -> Dict[str, Any]:
        """Get statistics about announcements for a building"""
        try:
            # Get all announcements for building
            all_announcements = await self.get_announcements(
                building_id, 
                audience="all", 
                active_only=False, 
                limit=1000
            )
            
            # Calculate statistics
            total_announcements = len(all_announcements)
            active_announcements = len([a for a in all_announcements if a.get('is_active', True)])
            
            # Group by type
            type_breakdown = {}
            for announcement in all_announcements:
                ann_type = announcement.get('type', 'general')
                type_breakdown[ann_type] = type_breakdown.get(ann_type, 0) + 1
            
            # Group by audience
            audience_breakdown = {}
            for announcement in all_announcements:
                audience = announcement.get('audience', 'all')
                audience_breakdown[audience] = audience_breakdown.get(audience, 0) + 1
            
            # Group by priority
            priority_breakdown = {}
            for announcement in all_announcements:
                priority = announcement.get('priority_level', 'normal')
                priority_breakdown[priority] = priority_breakdown.get(priority, 0) + 1
            
            # Count scheduled and draft announcements
            scheduled_count = len([a for a in all_announcements if a.get('is_published') == False and a.get('scheduled_publish_date')])
            draft_count = len([a for a in all_announcements if a.get('is_published') == False and not a.get('scheduled_publish_date')])
            published_count = len([a for a in all_announcements if a.get('is_published') == True])
            
            # Count targeted announcements
            department_targeted = len([a for a in all_announcements if a.get('target_departments')])
            user_targeted = len([a for a in all_announcements if a.get('target_user_ids')])
            role_targeted = len([a for a in all_announcements if a.get('target_roles')])
            
            # Total views
            total_views = sum(a.get('view_count', 0) for a in all_announcements)
            
            return {
                "total_announcements": total_announcements,
                "active_announcements": active_announcements,
                "inactive_announcements": total_announcements - active_announcements,
                "published_announcements": published_count,
                "draft_announcements": draft_count,
                "scheduled_announcements": scheduled_count,
                "type_breakdown": type_breakdown,
                "audience_breakdown": audience_breakdown,
                "priority_breakdown": priority_breakdown,
                "department_targeted_count": department_targeted,
                "user_targeted_count": user_targeted,
                "role_targeted_count": role_targeted,
                "total_views": total_views,
                "building_id": building_id,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting announcement statistics: {str(e)}")
            return {
                "error": str(e),
                "building_id": building_id,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

# Create global service instance
announcement_service = AnnouncementService()

"""
Comprehensive Notification Manager for FacilityFix

This service handles all notification scenarios across the application including:
- Work Orders, Job Services, Work Order Permits
- Maintenance Tasks (Preventive/Corrective)
- Inventory Management
- Announcements
- User Management
- System notifications

The manager provides:
- Template-based notification generation
- Multi-channel delivery (in-app, push, email)
- User preferences and targeting
- Escalation and reminder logic
- Batch processing and digest delivery
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum

from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.notification_models import (
    EnhancedNotification, NotificationType, NotificationPriority, 
    NotificationChannel, DeliveryStatus, NotificationTemplate,
    NotificationRule, NotificationPreference, NotificationBatch
)

logger = logging.getLogger(__name__)


class NotificationManager:
    """Comprehensive notification management service"""
    
    def __init__(self):
        self.db = database_service
        self._templates_cache: Dict[str, NotificationTemplate] = {}
        self._rules_cache: Dict[str, List[NotificationRule]] = {}
        self._preferences_cache: Dict[str, NotificationPreference] = {}
        
    # ═══════════════════════════════════════════════════════════════════════════
    # CORE NOTIFICATION CREATION AND DELIVERY
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def create_notification(
        self,
        notification_type: NotificationType,
        recipient_id: str,
        title: str,
        message: str,
        sender_id: Optional[str] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        building_id: Optional[str] = None,
        department: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: Optional[List[NotificationChannel]] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        requires_action: bool = False,
        expires_at: Optional[datetime] = None,
        custom_data: Optional[Dict[str, Any]] = None,
        send_immediately: bool = True
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create and optionally send a notification
        
        Returns:
            Tuple of (success, notification_id, error_message)
        """
        try:
            notification_id = str(uuid.uuid4())
            
            # Apply user preferences if no channels specified
            if channels is None:
                channels = await self._get_user_preferred_channels(recipient_id, notification_type)
            
            # Create notification object
            notification = EnhancedNotification(
                id=notification_id,
                notification_type=notification_type,
                recipient_id=recipient_id,
                sender_id=sender_id or "system",
                title=title,
                message=message,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                building_id=building_id,
                department=department,
                priority=priority,
                channels=channels,
                action_url=action_url,
                action_label=action_label,
                requires_action=requires_action,
                expires_at=expires_at,
                custom_data=custom_data or {},
                created_at=datetime.utcnow()
            )
            
            # Store notification
            success, _, error = await self.db.create_document(
                COLLECTIONS['notifications'],
                notification.dict(exclude_none=True),
                notification_id
            )
            
            if not success:
                logger.error(f"Failed to create notification: {error}")
                return False, None, error
            
            # Send immediately if requested
            if send_immediately:
                await self._deliver_notification(notification)
            
            logger.info(f"Created notification {notification_id} for user {recipient_id}")
            return True, notification_id, None
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            return False, None, str(e)
    
    async def create_bulk_notifications(
        self,
        notification_type: NotificationType,
        recipient_ids: List[str],
        title: str,
        message: str,
        **kwargs
    ) -> Tuple[bool, List[str], Optional[str]]:
        """Create notifications for multiple recipients"""
        try:
            notification_ids = []
            
            for recipient_id in recipient_ids:
                success, notif_id, error = await self.create_notification(
                    notification_type=notification_type,
                    recipient_id=recipient_id,
                    title=title,
                    message=message,
                    **kwargs
                )
                
                if success and notif_id:
                    notification_ids.append(notif_id)
                else:
                    logger.warning(f"Failed to create notification for {recipient_id}: {error}")
            
            return True, notification_ids, None
            
        except Exception as e:
            logger.error(f"Error creating bulk notifications: {str(e)}")
            return False, [], str(e)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WORK ORDER NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_work_order_submitted(
        self,
        work_order_id: str,
        requester_id: str,
        building_id: Optional[str] = None,
        location: Optional[str] = None
    ) -> bool:
        """Notify when work order is submitted - acknowledgment to tenant/staff"""
        try:
            # Notify requester (acknowledgment)
            await self.create_notification(
                notification_type=NotificationType.WORK_ORDER_SUBMITTED,
                recipient_id=requester_id,
                title="Work Order Request Submitted",
                message=f"Your work order request for {location or 'the specified location'} has been submitted and is being reviewed.",
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                building_id=building_id,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                action_url=f"/work-orders/{work_order_id}",
                action_label="View Request"
            )
            
            # Notify all admins about new request
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=NotificationType.WORK_ORDER_SUBMITTED,
                    recipient_id=admin["id"],
                    title="New Work Order Request",
                    message=f"A new work order request has been submitted for {location or 'review'}.",
                    related_entity_type="work_order",
                    related_entity_id=work_order_id,
                    building_id=building_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    action_url=f"/admin/work-orders/{work_order_id}",
                    action_label="Review Request",
                    requires_action=True
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending work order submitted notifications: {str(e)}")
            return False
    
    async def notify_work_order_assigned(
        self,
        work_order_id: str,
        assignee_id: str,
        requester_id: str,
        assigned_by: str,
        location: Optional[str] = None,
        scheduled_date: Optional[datetime] = None
    ) -> bool:
        """Notify when work order is assigned"""
        try:
            # Get assignee details
            assignee = await self._get_user_details(assignee_id)
            assignee_name = f"{assignee.get('first_name', '')} {assignee.get('last_name', '')}".strip()
            
            # Notify assignee
            await self.create_notification(
                notification_type=NotificationType.WORK_ORDER_ASSIGNED,
                recipient_id=assignee_id,
                title="Work Order Assigned",
                message=f"You have been assigned a work order for {location or 'a location'}."
                        + (f" Scheduled for {scheduled_date.strftime('%Y-%m-%d %H:%M')}" if scheduled_date else ""),
                sender_id=assigned_by,
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/work-orders/{work_order_id}",
                action_label="View Work Order",
                requires_action=True
            )
            
            # Notify requester
            await self.create_notification(
                notification_type=NotificationType.WORK_ORDER_ASSIGNED,
                recipient_id=requester_id,
                title="Work Order Assigned",
                message=f"Your work order has been assigned to {assignee_name or 'a technician'}."
                        + (f" Scheduled for {scheduled_date.strftime('%Y-%m-%d %H:%M')}" if scheduled_date else ""),
                sender_id=assigned_by,
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                action_url=f"/work-orders/{work_order_id}",
                action_label="Track Progress"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending work order assigned notifications: {str(e)}")
            return False
    
    async def notify_work_order_schedule_updated(
        self,
        work_order_id: str,
        assignee_id: str,
        requester_id: str,
        new_schedule: datetime,
        location: Optional[str] = None,
        reason: Optional[str] = None
    ) -> bool:
        """Notify when work order schedule is set or updated"""
        try:
            schedule_text = new_schedule.strftime('%Y-%m-%d %H:%M')
            reason_text = f" Reason: {reason}" if reason else ""
            
            # Notify assignee
            await self.create_notification(
                notification_type=NotificationType.WORK_ORDER_SCHEDULE_UPDATED,
                recipient_id=assignee_id,
                title="Work Order Schedule Updated",
                message=f"The schedule for your work order at {location or 'the location'} has been updated to {schedule_text}.{reason_text}",
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                action_url=f"/work-orders/{work_order_id}",
                action_label="View Details"
            )
            
            # Notify requester
            await self.create_notification(
                notification_type=NotificationType.WORK_ORDER_SCHEDULE_UPDATED,
                recipient_id=requester_id,
                title="Work Order Schedule Updated",
                message=f"The schedule for your work order has been updated to {schedule_text}.{reason_text}",
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                action_url=f"/work-orders/{work_order_id}",
                action_label="View Details"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending work order schedule notifications: {str(e)}")
            return False
    
    async def notify_work_order_canceled(
        self,
        work_order_id: str,
        assignee_id: Optional[str],
        requester_id: str,
        canceled_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """Notify when work order is canceled"""
        try:
            reason_text = f" Reason: {reason}" if reason else ""
            
            # Notify assignee if assigned
            if assignee_id:
                await self.create_notification(
                    notification_type=NotificationType.WORK_ORDER_CANCELED,
                    recipient_id=assignee_id,
                    title="Work Order Canceled",
                    message=f"The work order you were assigned has been canceled.{reason_text}",
                    sender_id=canceled_by,
                    related_entity_type="work_order",
                    related_entity_id=work_order_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    action_url=f"/work-orders/{work_order_id}",
                    action_label="View Details"
                )
            
            # Notify requester
            await self.create_notification(
                notification_type=NotificationType.WORK_ORDER_CANCELED,
                recipient_id=requester_id,
                title="Work Order Canceled",
                message=f"Your work order has been canceled.{reason_text}",
                sender_id=canceled_by,
                related_entity_type="work_order",
                related_entity_id=work_order_id,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                action_url=f"/work-orders/{work_order_id}",
                action_label="View Details"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending work order canceled notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # JOB SERVICE NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_job_service_received(
        self,
        job_service_id: str,
        staff_id: str,
        tenant_id: str,
        title: str,
        location: Optional[str] = None
    ) -> bool:
        """Notify when job service task is received by staff (also notify tenant)"""
        try:
            # Notify staff
            await self.create_notification(
                notification_type=NotificationType.JOB_SERVICE_RECEIVED,
                recipient_id=staff_id,
                title="New Job Service Task",
                message=f"You have received a new job service task: {title}"
                        + (f" at {location}" if location else ""),
                related_entity_type="job_service",
                related_entity_id=job_service_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/job-services/{job_service_id}",
                action_label="View Task",
                requires_action=True
            )
            
            # Notify tenant
            await self.create_notification(
                notification_type=NotificationType.JOB_SERVICE_RECEIVED,
                recipient_id=tenant_id,
                title="Job Service Assigned",
                message=f"Your job service request '{title}' has been assigned to our maintenance team.",
                related_entity_type="job_service",
                related_entity_id=job_service_id,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                action_url=f"/job-services/{job_service_id}",
                action_label="Track Progress"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending job service received notifications: {str(e)}")
            return False
    
    async def notify_job_service_completed(
        self,
        job_service_id: str,
        staff_id: str,
        tenant_id: str,
        title: str,
        completion_notes: Optional[str] = None
    ) -> bool:
        """Notify when job service work is completed"""
        try:
            notes_text = f" Notes: {completion_notes}" if completion_notes else ""
            
            # Notify staff (confirmation)
            await self.create_notification(
                notification_type=NotificationType.JOB_SERVICE_COMPLETED,
                recipient_id=staff_id,
                title="Job Service Completed",
                message=f"You have successfully completed the job service: {title}.{notes_text}",
                sender_id=staff_id,
                related_entity_type="job_service",
                related_entity_id=job_service_id,
                channels=[NotificationChannel.IN_APP],
                action_url=f"/job-services/{job_service_id}",
                action_label="View Completed Task"
            )
            
            # Notify tenant
            await self.create_notification(
                notification_type=NotificationType.JOB_SERVICE_COMPLETED,
                recipient_id=tenant_id,
                title="Job Service Completed",
                message=f"Your job service request '{title}' has been completed.{notes_text}",
                sender_id=staff_id,
                related_entity_type="job_service",
                related_entity_id=job_service_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/job-services/{job_service_id}",
                action_label="View Results"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending job service completed notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WORK ORDER PERMIT NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_permit_created(
        self,
        permit_id: str,
        requester_id: str,
        contractor_name: str,
        work_description: str
    ) -> bool:
        """Notify when work order permit is created/awaiting approval"""
        try:
            # Notify all admins
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=NotificationType.PERMIT_CREATED,
                    recipient_id=admin["id"],
                    title="Work Order Permit Awaiting Approval",
                    message=f"New permit request from {contractor_name}: {work_description}",
                    related_entity_type="work_order_permit",
                    related_entity_id=permit_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    action_url=f"/admin/permits/{permit_id}",
                    action_label="Review Permit",
                    requires_action=True
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending permit created notifications: {str(e)}")
            return False
    
    async def notify_permit_approved(
        self,
        permit_id: str,
        requester_id: str,
        assignee_id: Optional[str],
        approved_by: str,
        contractor_name: str,
        conditions: Optional[str] = None
    ) -> bool:
        """Notify when permit is approved"""
        try:
            conditions_text = f" Conditions: {conditions}" if conditions else ""
            
            # Notify requester
            await self.create_notification(
                notification_type=NotificationType.PERMIT_APPROVED,
                recipient_id=requester_id,
                title="Work Order Permit Approved",
                message=f"Your permit request for {contractor_name} has been approved.{conditions_text}",
                sender_id=approved_by,
                related_entity_type="work_order_permit",
                related_entity_id=permit_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/permits/{permit_id}",
                action_label="View Permit"
            )
            
            # Notify assignee if applicable
            if assignee_id:
                await self.create_notification(
                    notification_type=NotificationType.PERMIT_APPROVED,
                    recipient_id=assignee_id,
                    title="Work Order Permit Approved",
                    message=f"The permit for {contractor_name} work has been approved.{conditions_text}",
                    sender_id=approved_by,
                    related_entity_type="work_order_permit",
                    related_entity_id=permit_id,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    action_url=f"/permits/{permit_id}",
                    action_label="View Permit"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending permit approved notifications: {str(e)}")
            return False
    
    async def notify_permit_rejected(
        self,
        permit_id: str,
        requester_id: str,
        rejected_by: str,
        reason: str,
        contractor_name: str
    ) -> bool:
        """Notify when permit is rejected"""
        try:
            # Notify requester
            await self.create_notification(
                notification_type=NotificationType.PERMIT_REJECTED,
                recipient_id=requester_id,
                title="Work Order Permit Rejected",
                message=f"Your permit request for {contractor_name} has been rejected. Reason: {reason}",
                sender_id=rejected_by,
                related_entity_type="work_order_permit",
                related_entity_id=permit_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/permits/{permit_id}",
                action_label="View Details"
            )
            
            # Notify admin who rejected (confirmation)
            await self.create_notification(
                notification_type=NotificationType.PERMIT_REJECTED,
                recipient_id=rejected_by,
                title="Permit Rejection Recorded",
                message=f"You have rejected the permit request for {contractor_name}.",
                sender_id=rejected_by,
                related_entity_type="work_order_permit",
                related_entity_id=permit_id,
                channels=[NotificationChannel.IN_APP],
                action_url=f"/admin/permits/{permit_id}",
                action_label="View Details"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending permit rejected notifications: {str(e)}")
            return False
    
    async def notify_permit_expiring(
        self,
        permit_id: str,
        requester_id: str,
        contractor_name: str,
        expires_at: datetime,
        days_until_expiry: int
    ) -> bool:
        """Notify when permit is expiring soon"""
        try:
            expiry_text = expires_at.strftime('%Y-%m-%d')
            
            # Notify requester
            await self.create_notification(
                notification_type=NotificationType.PERMIT_EXPIRING,
                recipient_id=requester_id,
                title="Work Order Permit Expiring Soon",
                message=f"Your permit for {contractor_name} will expire in {days_until_expiry} days ({expiry_text}). Please ensure work is completed or request an extension.",
                related_entity_type="work_order_permit",
                related_entity_id=permit_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/permits/{permit_id}",
                action_label="View Permit",
                requires_action=True
            )
            
            # Notify all admins
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=NotificationType.PERMIT_EXPIRING,
                    recipient_id=admin["id"],
                    title="Work Order Permit Expiring Soon",
                    message=f"Permit for {contractor_name} expires in {days_until_expiry} days ({expiry_text}).",
                    related_entity_type="work_order_permit",
                    related_entity_id=permit_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP],
                    action_url=f"/admin/permits/{permit_id}",
                    action_label="Review Permit"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending permit expiring notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAINTENANCE TASK NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_maintenance_task_assigned(
        self,
        task_id: str,
        staff_id: str,
        task_title: str,
        location: str,
        scheduled_date: Optional[datetime] = None,
        assigned_by: Optional[str] = None
    ) -> bool:
        """Notify when maintenance task is assigned to staff"""
        try:
            schedule_text = f" scheduled for {scheduled_date.strftime('%Y-%m-%d %H:%M')}" if scheduled_date else ""
            
            await self.create_notification(
                notification_type=NotificationType.MAINTENANCE_TASK_ASSIGNED,
                recipient_id=staff_id,
                title="Maintenance Task Assigned",
                message=f"You have been assigned a maintenance task: {task_title} at {location}{schedule_text}.",
                sender_id=assigned_by,
                related_entity_type="maintenance_task",
                related_entity_id=task_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/maintenance/{task_id}",
                action_label="View Task",
                requires_action=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending maintenance task assigned notification: {str(e)}")
            return False
    
    async def notify_maintenance_overdue(
        self,
        task_id: str,
        staff_id: str,
        manager_id: Optional[str],
        task_title: str,
        location: str,
        days_overdue: int
    ) -> bool:
        """Notify when maintenance task is overdue (escalation logic)"""
        try:
            # Notify assignee
            await self.create_notification(
                notification_type=NotificationType.MAINTENANCE_OVERDUE,
                recipient_id=staff_id,
                title="Maintenance Task Overdue",
                message=f"URGENT: Your maintenance task '{task_title}' at {location} is {days_overdue} days overdue. Please complete immediately.",
                related_entity_type="maintenance_task",
                related_entity_id=task_id,
                priority=NotificationPriority.URGENT,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/maintenance/{task_id}",
                action_label="Complete Task",
                requires_action=True
            )
            
            # Escalate to manager if specified
            if manager_id:
                await self.create_notification(
                    notification_type=NotificationType.ESCALATION,
                    recipient_id=manager_id,
                    title="Overdue Maintenance Task (Escalation)",
                    message=f"Maintenance task '{task_title}' at {location} is {days_overdue} days overdue and requires management attention.",
                    related_entity_type="maintenance_task",
                    related_entity_id=task_id,
                    priority=NotificationPriority.URGENT,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    action_url=f"/maintenance/{task_id}",
                    action_label="Review Task",
                    requires_action=True
                )
            
            # Notify all admins
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=NotificationType.MAINTENANCE_OVERDUE,
                    recipient_id=admin["id"],
                    title="Overdue Maintenance Task",
                    message=f"Maintenance task '{task_title}' at {location} is {days_overdue} days overdue.",
                    related_entity_type="maintenance_task",
                    related_entity_id=task_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP],
                    action_url=f"/admin/maintenance/{task_id}",
                    action_label="Review Task"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending maintenance overdue notifications: {str(e)}")
            return False
    
    async def notify_maintenance_completed(
        self,
        task_id: str,
        completed_by: str,
        task_title: str,
        location: str,
        completion_notes: Optional[str] = None
    ) -> bool:
        """Notify when maintenance task is completed"""
        try:
            notes_text = f" Notes: {completion_notes}" if completion_notes else ""
            
            # Notify all admins
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=NotificationType.MAINTENANCE_COMPLETED,
                    recipient_id=admin["id"],
                    title="Maintenance Task Completed",
                    message=f"Maintenance task '{task_title}' at {location} has been completed.{notes_text}",
                    sender_id=completed_by,
                    related_entity_type="maintenance_task",
                    related_entity_id=task_id,
                    channels=[NotificationChannel.IN_APP],
                    action_url=f"/admin/maintenance/{task_id}",
                    action_label="View Report"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending maintenance completed notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INVENTORY NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_inventory_low_stock(
        self,
        inventory_id: str,
        item_name: str,
        current_stock: int,
        reorder_level: int,
        building_id: Optional[str] = None,
        department: Optional[str] = None,
        is_critical: bool = False
    ) -> bool:
        """Notify when inventory reaches low/critical stock threshold"""
        try:
            notification_type = NotificationType.INVENTORY_CRITICAL_STOCK if is_critical else NotificationType.INVENTORY_LOW_STOCK
            priority = NotificationPriority.URGENT if is_critical else NotificationPriority.HIGH
            
            alert_level = "CRITICAL" if is_critical else "LOW"
            
            # Get inventory team members
            inventory_staff = await self._get_users_by_department("inventory")
            
            # Notify inventory team
            for staff in inventory_staff:
                await self.create_notification(
                    notification_type=notification_type,
                    recipient_id=staff["id"],
                    title=f"{alert_level} Stock Alert",
                    message=f"{alert_level}: {item_name} is running low (Current: {current_stock}, Reorder at: {reorder_level}). Immediate restocking required.",
                    related_entity_type="inventory",
                    related_entity_id=inventory_id,
                    building_id=building_id,
                    department=department,
                    priority=priority,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    action_url=f"/inventory/{inventory_id}",
                    action_label="Restock Item",
                    requires_action=True
                )
            
            # Notify admins
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=notification_type,
                    recipient_id=admin["id"],
                    title=f"{alert_level} Stock Alert",
                    message=f"{alert_level}: {item_name} requires restocking (Current: {current_stock}).",
                    related_entity_type="inventory",
                    related_entity_id=inventory_id,
                    building_id=building_id,
                    department=department,
                    priority=priority,
                    channels=[NotificationChannel.IN_APP],
                    action_url=f"/admin/inventory/{inventory_id}",
                    action_label="Review Item"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending inventory low stock notifications: {str(e)}")
            return False
    
    async def notify_inventory_restocked(
        self,
        inventory_id: str,
        item_name: str,
        new_stock_level: int,
        restocked_by: str,
        building_id: Optional[str] = None,
        waiting_requesters: Optional[List[str]] = None
    ) -> bool:
        """Notify when inventory is restocked"""
        try:
            # Notify inventory team
            inventory_staff = await self._get_users_by_department("inventory")
            for staff in inventory_staff:
                await self.create_notification(
                    notification_type=NotificationType.INVENTORY_RESTOCKED,
                    recipient_id=staff["id"],
                    title="Inventory Restocked",
                    message=f"{item_name} has been restocked. New stock level: {new_stock_level}.",
                    sender_id=restocked_by,
                    related_entity_type="inventory",
                    related_entity_id=inventory_id,
                    building_id=building_id,
                    channels=[NotificationChannel.IN_APP],
                    action_url=f"/inventory/{inventory_id}",
                    action_label="View Item"
                )
            
            # Notify admins
            admin_users = await self._get_users_by_role("admin")
            for admin in admin_users:
                await self.create_notification(
                    notification_type=NotificationType.INVENTORY_RESTOCKED,
                    recipient_id=admin["id"],
                    title="Inventory Restocked",
                    message=f"{item_name} has been restocked to {new_stock_level} units.",
                    sender_id=restocked_by,
                    related_entity_type="inventory",
                    related_entity_id=inventory_id,
                    building_id=building_id,
                    channels=[NotificationChannel.IN_APP],
                    action_url=f"/admin/inventory/{inventory_id}",
                    action_label="View Item"
                )
            
            # Notify waiting requesters if any
            if waiting_requesters:
                for requester_id in waiting_requesters:
                    await self.create_notification(
                        notification_type=NotificationType.INVENTORY_RESTOCKED,
                        recipient_id=requester_id,
                        title="Requested Item Now Available",
                        message=f"{item_name} that you requested is now back in stock.",
                        sender_id=restocked_by,
                        related_entity_type="inventory",
                        related_entity_id=inventory_id,
                        building_id=building_id,
                        priority=NotificationPriority.HIGH,
                        channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                        action_url=f"/inventory/request/{inventory_id}",
                        action_label="Submit Request"
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending inventory restocked notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INVENTORY REQUEST NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_inventory_request_submitted(
        self,
        request_id: str,
        requester_id: str,
        item_name: str,
        quantity: int,
        purpose: str
    ) -> bool:
        """Notify when inventory request is submitted"""
        try:
            # Notify admins and inventory staff
            recipients = []
            
            # Get admin users
            admin_users = await self._get_users_by_role("admin")
            recipients.extend([admin["id"] for admin in admin_users])
            
            # Get inventory staff
            inventory_staff = await self._get_users_by_department("inventory")
            recipients.extend([staff["id"] for staff in inventory_staff])
            
            # Remove duplicates
            recipients = list(set(recipients))
            
            for recipient_id in recipients:
                await self.create_notification(
                    notification_type=NotificationType.INVENTORY_REQUEST_SUBMITTED,
                    recipient_id=recipient_id,
                    title="New Inventory Request",
                    message=f"New inventory request for {quantity} units of {item_name} (Purpose: {purpose}).",
                    sender_id=requester_id,
                    related_entity_type="inventory_request",
                    related_entity_id=request_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    action_url=f"/inventory/requests/{request_id}",
                    action_label="Review Request",
                    requires_action=True
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending inventory request submitted notifications: {str(e)}")
            return False
    
    async def notify_inventory_request_rejected(
        self,
        request_id: str,
        requester_id: str,
        item_name: str,
        reason: str,
        rejected_by: str
    ) -> bool:
        """Notify when inventory request is rejected"""
        try:
            await self.create_notification(
                notification_type=NotificationType.INVENTORY_REQUEST_REJECTED,
                recipient_id=requester_id,
                title="Inventory Request Rejected",
                message=f"Your request for {item_name} has been rejected. Reason: {reason}",
                sender_id=rejected_by,
                related_entity_type="inventory_request",
                related_entity_id=request_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/inventory/requests/{request_id}",
                action_label="View Details"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending inventory request rejected notification: {str(e)}")
            return False
    
    async def notify_inventory_request_ready(
        self,
        request_id: str,
        requester_id: str,
        item_name: str,
        quantity: int,
        pickup_location: Optional[str] = None
    ) -> bool:
        """Notify when inventory request is ready for pickup/delivered"""
        try:
            pickup_text = f" Pick up from: {pickup_location}" if pickup_location else ""
            
            await self.create_notification(
                notification_type=NotificationType.INVENTORY_REQUEST_READY,
                recipient_id=requester_id,
                title="Inventory Request Ready",
                message=f"Your request for {quantity} units of {item_name} is ready for pickup.{pickup_text}",
                related_entity_type="inventory_request",
                related_entity_id=request_id,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/inventory/requests/{request_id}",
                action_label="View Details",
                requires_action=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending inventory request ready notification: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANNOUNCEMENT NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_announcement_published(
        self,
        announcement_id: str,
        title: str,
        content: str,
        target_audience: str,
        target_roles: Optional[List[str]] = None,
        target_departments: Optional[List[str]] = None,
        target_user_ids: Optional[List[str]] = None,
        building_id: Optional[str] = None,
        priority: str = "normal",
        announcement_type: str = ""
    ) -> bool:
        """Notify target audience about new announcement"""
        try:
            # Determine notification priority
            notif_priority = NotificationPriority.NORMAL
            if priority in ["urgent", "critical"]:
                notif_priority = NotificationPriority.URGENT
            elif priority == "high":
                notif_priority = NotificationPriority.HIGH
            
            # Get target recipients
            recipients = await self._get_announcement_recipients(
                target_audience=target_audience,
                target_roles=target_roles,
                target_departments=target_departments,
                target_user_ids=target_user_ids,
                building_id=building_id
            )
            
            # Send notification to each recipient
            for recipient_id in recipients:
                await self.create_notification(
                    notification_type=NotificationType.ANNOUNCEMENT_PUBLISHED,
                    recipient_id=recipient_id,
                    title=f"New Announcement: {title}",
                    message=content[:150] + "..." if len(content) > 150 else content,
                    related_entity_type="announcement",
                    related_entity_id=announcement_id,
                    building_id=building_id,
                    priority=notif_priority,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    action_url=f"/announcements/{announcement_id}",
                    action_label="Read Full Announcement"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending announcement published notifications: {str(e)}")
            return False
    
    async def notify_announcement_reminder(
        self,
        announcement_id: str,
        title: str,
        event_time: datetime,
        target_recipients: List[str],
        hours_before: int = 2
    ) -> bool:
        """Send reminder notifications for events/maintenance"""
        try:
            time_text = event_time.strftime('%Y-%m-%d %H:%M')
            
            for recipient_id in target_recipients:
                await self.create_notification(
                    notification_type=NotificationType.ANNOUNCEMENT_REMINDER,
                    recipient_id=recipient_id,
                    title=f"Reminder: {title}",
                    message=f"Reminder: {title} is scheduled to begin in {hours_before} hours at {time_text}.",
                    related_entity_type="announcement",
                    related_entity_id=announcement_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    action_url=f"/announcements/{announcement_id}",
                    action_label="View Details"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending announcement reminder notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # USER MANAGEMENT NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_user_invited(
        self,
        user_id: str,
        invited_by: str,
        role: str,
        building_name: Optional[str] = None
    ) -> bool:
        """Notify when user is invited to the system"""
        try:
            building_text = f" for {building_name}" if building_name else ""
            
            await self.create_notification(
                notification_type=NotificationType.USER_INVITED,
                recipient_id=user_id,
                title="Welcome to FacilityFix",
                message=f"You have been invited to join FacilityFix as a {role}{building_text}. Please complete your registration.",
                sender_id=invited_by,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.EMAIL, NotificationChannel.IN_APP],
                action_url="/register",
                action_label="Complete Registration",
                requires_action=True
            )
            
            # Notify admin who sent invite
            await self.create_notification(
                notification_type=NotificationType.USER_INVITED,
                recipient_id=invited_by,
                title="User Invitation Sent",
                message=f"Invitation sent to new {role} user{building_text}.",
                sender_id=invited_by,
                channels=[NotificationChannel.IN_APP],
                action_url=f"/admin/users/{user_id}",
                action_label="View User"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending user invited notifications: {str(e)}")
            return False
    
    async def notify_user_approved(
        self,
        user_id: str,
        approved_by: str,
        role: str
    ) -> bool:
        """Notify when user account is approved"""
        try:
            await self.create_notification(
                notification_type=NotificationType.USER_APPROVED,
                recipient_id=user_id,
                title="Account Approved",
                message=f"Your {role} account has been approved. You can now access all system features.",
                sender_id=approved_by,
                priority=NotificationPriority.HIGH,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url="/dashboard",
                action_label="Access Dashboard"
            )
            
            # Notify admin
            await self.create_notification(
                notification_type=NotificationType.USER_APPROVED,
                recipient_id=approved_by,
                title="User Account Approved",
                message=f"You have approved a {role} account.",
                sender_id=approved_by,
                channels=[NotificationChannel.IN_APP],
                action_url=f"/admin/users/{user_id}",
                action_label="View User"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending user approved notifications: {str(e)}")
            return False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Get all users with a specific role"""
        try:
            success, users, error = await self.db.query_documents(
                COLLECTIONS['users'],
                [('role', '==', role)]
            )
            
            if success:
                return users
            else:
                logger.error(f"Error fetching users by role {role}: {error}")
                return []
                
        except Exception as e:
            logger.error(f"Error in _get_users_by_role: {str(e)}")
            return []
    
    async def _get_users_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get all users in a specific department"""
        try:
            success, users, error = await self.db.query_documents(
                COLLECTIONS['users'],
                [('department', '==', department)]
            )
            
            if success:
                return users
            else:
                logger.error(f"Error fetching users by department {department}: {error}")
                return []
                
        except Exception as e:
            logger.error(f"Error in _get_users_by_department: {str(e)}")
            return []
    
    async def _get_user_details(self, user_id: str) -> Dict[str, Any]:
        """Get user details by ID"""
        try:
            success, user, error = await self.db.get_document(
                COLLECTIONS['users'],
                user_id
            )
            
            if success and user:
                return user
            else:
                logger.warning(f"User not found: {user_id}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in _get_user_details: {str(e)}")
            return {}
    
    async def _get_user_preferred_channels(
        self, 
        user_id: str, 
        notification_type: NotificationType
    ) -> List[NotificationChannel]:
        """Get user's preferred notification channels for a specific type"""
        try:
            # Default channels
            default_channels = [NotificationChannel.IN_APP]
            
            # Try to get user preferences (placeholder for future implementation)
            # For now, return reasonable defaults based on notification type
            if notification_type in [
                NotificationType.MAINTENANCE_OVERDUE,
                NotificationType.PERMIT_EXPIRING,
                NotificationType.INVENTORY_CRITICAL_STOCK
            ]:
                return [NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL]
            elif notification_type in [
                NotificationType.WORK_ORDER_ASSIGNED,
                NotificationType.JOB_SERVICE_RECEIVED,
                NotificationType.MAINTENANCE_TASK_ASSIGNED
            ]:
                return [NotificationChannel.IN_APP, NotificationChannel.PUSH]
            else:
                return default_channels
                
        except Exception as e:
            logger.error(f"Error getting user preferred channels: {str(e)}")
            return [NotificationChannel.IN_APP]
    
    async def _get_admin_user_ids(self) -> List[str]:
        """Get list of all admin user IDs"""
        try:
            admin_users = await self._get_users_by_role("admin")
            return [user.get("id", user.get("user_id")) for user in admin_users if user.get("id") or user.get("user_id")]
        except Exception as e:
            logger.error(f"Error getting admin user IDs: {str(e)}")
            return []
    
    async def _get_announcement_recipients(
        self,
        target_audience: str,
        target_roles: Optional[List[str]] = None,
        target_departments: Optional[List[str]] = None,
        target_user_ids: Optional[List[str]] = None,
        building_id: Optional[str] = None
    ) -> List[str]:
        """Get list of recipient IDs for announcement targeting"""
        try:
            recipients = set()
            
            # Specific user IDs
            if target_user_ids:
                recipients.update(target_user_ids)
            
            # Target by roles
            if target_roles:
                for role in target_roles:
                    users = await self._get_users_by_role(role)
                    recipients.update([user["id"] for user in users if "id" in user])
            
            # Target by departments
            if target_departments:
                for dept in target_departments:
                    users = await self._get_users_by_department(dept)
                    recipients.update([user["id"] for user in users if "id" in user])
            
            # Target all users
            if target_audience == "all":
                success, users, error = await self.db.query_documents(COLLECTIONS['users'])
                if success:
                    recipients.update([user["id"] for user in users if "id" in user])
            
            # Filter by building if specified
            if building_id:
                building_users = []
                success, users, error = await self.db.query_documents(
                    COLLECTIONS['users'],
                    [('building_id', '==', building_id)]
                )
                if success:
                    building_user_ids = set([user["id"] for user in users if "id" in user])
                    recipients = recipients.intersection(building_user_ids)
            
            return list(recipients)
            
        except Exception as e:
            logger.error(f"Error getting announcement recipients: {str(e)}")
            return []
    
    async def _deliver_notification(self, notification: EnhancedNotification):
        """Handle the actual delivery of a notification through various channels"""
        try:
            # Update delivery status
            update_data = {
                "delivery_status": DeliveryStatus.SENT.value,
                "delivered_at": datetime.utcnow()
            }
            
            await self.db.update_document(
                COLLECTIONS['notifications'],
                notification.id,
                update_data
            )
            
            # Here you would implement actual delivery logic for each channel:
            # - Push notifications (FCM, APNs)
            # - Email notifications (SendGrid, AWS SES)
            # - WebSocket real-time notifications
            # - SMS notifications (Twilio)
            
            logger.info(f"Delivered notification {notification.id} via channels: {notification.channels}")
            
        except Exception as e:
            logger.error(f"Error delivering notification {notification.id}: {str(e)}")
            
            # Update delivery status to failed
            try:
                await self.db.update_document(
                    COLLECTIONS['notifications'],
                    notification.id,
                    {
                        "delivery_status": DeliveryStatus.FAILED.value,
                        "failed_reason": str(e)
                    }
                )
            except:
                pass  # Don't fail on status update failure

    # ═══════════════════════════════════════════════════════════════════════════
    # CONCERN SLIP NOTIFICATION METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def notify_concern_slip_submitted(
        self,
        concern_slip_id: str,
        title: str,
        reported_by: str,
        category: str,
        priority: str,
        location: str,
        description: Optional[str] = None
    ):
        """Notify admins when a new concern slip is submitted"""
        try:
            # Get admin users
            admin_ids = await self._get_admin_user_ids()
            print("ADMIN IDS:", admin_ids)
            for admin_id in admin_ids:
                await self.create_notification(
                    notification_type=NotificationType.CONCERN_SLIP_SUBMITTED,
                    recipient_id=admin_id,
                    title="New Concern Slip Submitted",
                    message=f"New concern slip '{title}' submitted by tenant. Category: {category}, Priority: {priority}, Location: {location}",
                    related_entity_type="concern_slip",
                    related_entity_id=concern_slip_id,
                    priority=NotificationPriority.HIGH if priority == "critical" else NotificationPriority.NORMAL,
                    action_url=f"/concern-slips/{concern_slip_id}",
                    custom_data={
                        "concern_slip_id": concern_slip_id,
                        "reported_by": reported_by,
                        "category": category,
                        "priority": priority,
                        "location": location,
                        "title": title
                    },
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    expires_at=datetime.utcnow() + timedelta(days=7)
                )
                
            logger.info(f"Sent concern slip submitted notifications for {concern_slip_id}")
            
        except Exception as e:
            logger.error(f"Error sending concern slip submitted notifications: {str(e)}")

    async def notify_concern_slip_assigned(
        self,
        concern_slip_id: str,
        title: str,
        staff_id: str,
        assigned_by: str,
        category: str,
        priority: str,
        location: str
    ):
        """Notify staff member when assigned to assess a concern slip"""
        try:
            await self.create_notification(
                notification_type=NotificationType.CONCERN_SLIP_ASSIGNED,
                recipient_id=staff_id,
                title="Concern Slip Assignment",
                message=f"You have been assigned to assess concern slip '{title}'. Category: {category}, Priority: {priority}, Location: {location}",
                related_entity_type="concern_slip",
                related_entity_id=concern_slip_id,
                priority=NotificationPriority.HIGH if priority == "critical" else NotificationPriority.NORMAL,
                action_url=f"/concern-slips/{concern_slip_id}",
                custom_data={
                    "concern_slip_id": concern_slip_id,
                    "assigned_by": assigned_by,
                    "category": category,
                    "priority": priority,
                    "location": location,
                    "title": title,
                    "assessment_required": True
                },
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                expires_at=datetime.utcnow() + timedelta(days=3)
            )
            
            logger.info(f"Sent concern slip assignment notification to {staff_id} for {concern_slip_id}")
            
        except Exception as e:
            logger.error(f"Error sending concern slip assignment notification: {str(e)}")

    async def notify_concern_slip_assessed(
        self,
        concern_slip_id: str,
        title: str,
        staff_id: str,
        assessment: str,
        resolution_type: str
    ):
        """Notify admins when staff completes assessment of concern slip"""
        try:
            # Get admin users
            admin_ids = await self._get_admin_user_ids()
            
            # Format resolution type for display
            resolution_display = "Job Service" if resolution_type == "job_service" else "Work Order Permit"
            
            for admin_id in admin_ids:
                await self.create_notification(
                    notification_type=NotificationType.CONCERN_SLIP_ASSESSED,
                    recipient_id=admin_id,
                    title="Concern Slip Assessment Completed",
                    message=f"Staff assessment completed for '{title}'. Resolution: {resolution_display}. {assessment[:100]}{'...' if len(assessment) > 100 else ''}",
                    related_entity_type="concern_slip",
                    related_entity_id=concern_slip_id,
                    priority=NotificationPriority.HIGH,
                    action_url=f"/concern-slips/{concern_slip_id}",
                    custom_data={
                        "concern_slip_id": concern_slip_id,
                        "assessed_by": staff_id,
                        "assessment": assessment,
                        "resolution_type": resolution_type,
                        "title": title,
                        "requires_admin_action": True
                    },
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                    expires_at=datetime.utcnow() + timedelta(days=5)
                )
                
            logger.info(f"Sent concern slip assessment notifications for {concern_slip_id}")
            
        except Exception as e:
            logger.error(f"Error sending concern slip assessment notifications: {str(e)}")

    async def notify_concern_slip_evaluated(
        self,
        concern_slip_id: str,
        title: str,
        tenant_id: str,
        status: str,
        resolution_type: Optional[str] = None,
        admin_notes: Optional[str] = None
    ):
        """Notify tenant when their concern slip is evaluated (approved/rejected)"""
        try:
            status_text = "approved" if status == "approved" else "rejected"
            message = f"Your concern slip '{title}' has been {status_text}"
            
            if resolution_type:
                message += f". Resolution type: {resolution_type.replace('_', ' ').title()}"
            
            if admin_notes:
                message += f". Notes: {admin_notes}"
            
            await self.create_notification(
                notification_type=NotificationType.CONCERN_SLIP_EVALUATED,
                recipient_id=tenant_id,
                title=f"Concern Slip {status_text.title()}",
                message=message,
                related_entity_type="concern_slip",
                related_entity_id=concern_slip_id,
                priority=NotificationPriority.HIGH,
                action_url=f"/concern-slips/{concern_slip_id}",
                custom_data={
                    "concern_slip_id": concern_slip_id,
                    "status": status,
                    "resolution_type": resolution_type,
                    "admin_notes": admin_notes,
                    "title": title
                },
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            
            logger.info(f"Sent concern slip evaluation notification to {tenant_id} for {concern_slip_id}")
            
        except Exception as e:
            logger.error(f"Error sending concern slip evaluation notification: {str(e)}")

    async def notify_concern_slip_resolution_set(
        self,
        concern_slip_id: str,
        title: str,
        tenant_id: str,
        resolution_type: str,
        admin_notes: Optional[str] = None
    ):
        """Notify tenant when resolution type is set for their concern slip"""
        try:
            resolution_text = "Job Service" if resolution_type == "job_service" else "Work Order Permit"
            message = f"Resolution type set for '{title}': {resolution_text}"
            
            if admin_notes:
                message += f". Notes: {admin_notes}"
            
            await self.create_notification(
                notification_type=NotificationType.CONCERN_SLIP_RESOLUTION_SET,
                recipient_id=tenant_id,
                title="Concern Slip Resolution Type Set",
                message=message,
                related_entity_type="concern_slip",
                related_entity_id=concern_slip_id,
                priority=NotificationPriority.HIGH,
                action_url=f"/concern-slips/{concern_slip_id}",
                custom_data={
                    "concern_slip_id": concern_slip_id,
                    "resolution_type": resolution_type,
                    "admin_notes": admin_notes,
                    "title": title,
                    "next_action": f"Create {resolution_text}"
                },
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            
            logger.info(f"Sent concern slip resolution type notification to {tenant_id} for {concern_slip_id}")
            
        except Exception as e:
            logger.error(f"Error sending concern slip resolution type notification: {str(e)}")

    async def notify_concern_slip_returned_to_tenant(
        self,
        concern_slip_id: str,
        title: str,
        tenant_id: str,
        assessment: str,
        recommendation: str
    ):
        """Notify tenant when concern slip is returned after assessment"""
        try:
            message = f"Your concern slip '{title}' has been assessed and returned. "
            message += f"Recommendation: {recommendation[:100]}{'...' if len(recommendation) > 100 else ''}"
            
            await self.create_notification(
                notification_type=NotificationType.CONCERN_SLIP_RETURNED,
                recipient_id=tenant_id,
                title="Concern Slip Assessment Complete",
                message=message,
                related_entity_type="concern_slip",
                related_entity_id=concern_slip_id,
                priority=NotificationPriority.HIGH,
                action_url=f"/concern-slips/{concern_slip_id}",
                custom_data={
                    "concern_slip_id": concern_slip_id,
                    "assessment": assessment,
                    "recommendation": recommendation,
                    "title": title,
                    "next_action": "Proceed with Job Service or Work Order Permit"
                },
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            
            logger.info(f"Sent concern slip return notification to {tenant_id} for {concern_slip_id}")
            
        except Exception as e:
            logger.error(f"Error sending concern slip return notification: {str(e)}")


    async def notify_maintenance_task_assigned(
        self,
        task_id: str,
        task_title: str,
        assignee_id: str,
        assigned_by: str,
        location: str,
        scheduled_date: Optional[datetime] = None,
        priority: str = "medium"
    ) -> bool:
        """Notify staff when a maintenance task is assigned to them"""
        try:
            # Get assignee details
            assignee = await self._get_user_details(assignee_id)
            assignee_name = f"{assignee.get('first_name', '')} {assignee.get('last_name', '')}".strip()

            # Get assigner details
            assigner = await self._get_user_details(assigned_by)
            assigner_name = f"{assigner.get('first_name', '')} {assigner.get('last_name', '')}".strip()

            schedule_text = ""
            if scheduled_date:
                schedule_text = f" Scheduled for {scheduled_date.strftime('%Y-%m-%d %H:%M')}."

            priority_text = f" Priority: {priority.title()}."

            await self.create_notification(
                notification_type=NotificationType.MAINTENANCE_TASK_ASSIGNED,
                recipient_id=assignee_id,
                title="Maintenance Task Assigned",
                message=f"You have been assigned maintenance task '{task_title}' at {location}.{schedule_text}{priority_text}",
                sender_id=assigned_by,
                related_entity_type="maintenance_task",
                related_entity_id=task_id,
                priority=NotificationPriority.HIGH if priority in ["high", "critical"] else NotificationPriority.MEDIUM,
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                action_url=f"/maintenance/{task_id}",
                action_label="View Task Details",
                requires_action=True,
                custom_data={
                    "task_id": task_id,
                    "task_title": task_title,
                    "location": location,
                    "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
                    "priority": priority,
                    "assigned_by": assigner_name
                },
                expires_at=datetime.utcnow() + timedelta(days=7)
            )

            logger.info(f"Sent maintenance task assignment notification to {assignee_name} ({assignee_id}) for task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending maintenance task assignment notification: {str(e)}")
            return False

    async def notify_inventory_replacement_requested(
        self,
        request_id: str,
        item_name: str,
        quantity: int,
        reason: str,
        maintenance_task_id: str
    ) -> bool:
        """Notify admins when staff requests replacement for defective inventory item"""
        try:
            # Get all admin users
            admin_ids = await self._get_admin_user_ids()

            if not admin_ids:
                logger.warning("No admin users found to notify about replacement request")
                return False

            # Get maintenance task details for context
            task_title = "Unknown Task"
            try:
                from ..services.maintenance_task_service import maintenance_task_service
                task = await maintenance_task_service.get_task(maintenance_task_id)
                if task:
                    task_title = task.task_title
            except Exception as task_error:
                logger.warning(f"Could not get task details for {maintenance_task_id}: {task_error}")

            title = "Inventory Replacement Requested"
            message = f"Staff has requested replacement for '{item_name}' (Qty: {quantity}). Reason: {reason}. Task: {task_title}"

            # Notify all admins
            for admin_id in admin_ids:
                await self.create_notification(
                    notification_type=NotificationType.INVENTORY_REPLACEMENT_REQUESTED,
                    recipient_id=admin_id,
                    title=title,
                    message=message,
                    related_entity_type="inventory_request",
                    related_entity_id=request_id,
                    priority=NotificationPriority.HIGH,
                    channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                    action_url=f"/inventory/requests/{request_id}",
                    action_label="Review Request",
                    requires_action=True,
                    custom_data={
                        "request_id": request_id,
                        "item_name": item_name,
                        "quantity": quantity,
                        "reason": reason,
                        "maintenance_task_id": maintenance_task_id,
                        "task_title": task_title
                    },
                    expires_at=datetime.utcnow() + timedelta(days=3)
                )

            logger.info(f"Sent inventory replacement request notifications to {len(admin_ids)} admins for request {request_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending inventory replacement request notification: {str(e)}")
            return False

    async def _get_admin_user_ids(self) -> List[str]:
        """Get all admin user IDs for notifications"""
        try:
            # Query users collection for admin role
            success, users, error = await self.db.query_documents(
                COLLECTIONS['users'],
                [('role', '==', 'admin')]
            )

            if success and users:
                return [user.get('_doc_id') or user.get('id') for user in users if user.get('_doc_id') or user.get('id')]
            else:
                logger.warning(f"Could not get admin users: {error}")
                return []

        except Exception as e:
            logger.error(f"Error getting admin user IDs: {str(e)}")
            return []


# Create global notification manager instance
notification_manager = NotificationManager()
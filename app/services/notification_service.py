from typing import List, Optional
from datetime import datetime
from ..models.database_models import Notification
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from .fcm_service import fcm_service
from .email_service import email_service
from .websocket_service import websocket_notification_service
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.db = database_service
        self.fcm = fcm_service

    async def create_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str = "info",
        related_id: Optional[str] = None,
        send_push: bool = True,
        send_email: bool = False,
        send_websocket: bool = True,
        email_data: Optional[dict] = None
    ) -> bool:
        """Create a comprehensive notification across all channels"""
        try:
            # 1. Create in-app notification in database
            notification_data = {
                "recipient_id": user_id,
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "related_id": related_id,
                "is_read": False,
                "created_at": datetime.now()
            }
            
            success, notification_id, error = await self.db.create_document(
                COLLECTIONS['notifications'], 
                notification_data
            )
            
            if not success:
                logger.error(f"Failed to create in-app notification: {error}")
                return False
            
            # 2. Send push notification via FCM
            if send_push:
                try:
                    await self.fcm.send_notification_to_user(user_id, title, message, {
                        "type": notification_type,
                        "related_id": related_id or "",
                        "notification_id": notification_id
                    })
            
                except Exception as e:
                        logger.error(f"Failed to send FCM notification: {str(e)}")
            
            # 3. Send WebSocket notification for real-time updates
            if send_websocket:
                try:
                    await websocket_notification_service.manager.send_personal_message(user_id, {
                        "type": "notification",
                        "notification_type": notification_type,
                        "id": notification_id,
                        "title": title,
                        "message": message,
                        "related_id": related_id,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Failed to send WebSocket notification: {str(e)}")
            
            # 4. Send email notification if requested and data provided
            if send_email and email_data:
                try:
                    recipient_email = email_data.get('recipient_email')
                    recipient_name = email_data.get('recipient_name')
                    
                    if recipient_email and recipient_name:
                        # Determine appropriate email template based on notification type
                        email_success = await self._send_email_notification(
                            notification_type, email_data
                        )
                        if not email_success:
                            logger.warning(f"Failed to send email notification to {recipient_email}")
                except Exception as e:
                    logger.error(f"Failed to send email notification: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create comprehensive notification: {str(e)}")
            return False

    async def _send_email_notification(self, notification_type: str, email_data: dict) -> bool:
        """Route email notifications to appropriate service methods"""
        try:
            if notification_type.startswith('work_order'):
                return await email_service.send_work_order_notification(email_data, notification_type)
            elif notification_type.startswith('maintenance'):
                return await email_service.send_maintenance_notification(email_data, notification_type)
            elif notification_type.startswith('inventory') or notification_type == 'low_stock_alert':
                return await email_service.send_inventory_notification(email_data, notification_type)
            else:
                # Generic notification email
                recipient_email = email_data.get('recipient_email')
                recipient_name = email_data.get('recipient_name')
                title = email_data.get('title', 'FacilityFix Notification')
                message = email_data.get('message', '')
                
                # Simple HTML email for generic notifications
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2>{title}</h2>
                    <p>Hello {recipient_name},</p>
                    <p>{message}</p>
                    <p>Best regards,<br>FacilityFix Team</p>
                </body>
                </html>
                """
                
                return await email_service.send_email(
                    recipient_email, recipient_name, title, html_content
                )
        except Exception as e:
            logger.error(f"Error sending email notification: {str(e)}")
            return False

    async def get_user_notifications(self, user_id: str, limit: int = 50) -> List[dict]:
        """Get notifications for a user"""
        try:
            success, notifications, error = await self.db.query_documents(
                COLLECTIONS['notifications'],
                [('recipient_id', '==', user_id)],
                order_by=[('created_at', 'desc')],
                limit=limit
            )
            
            return notifications if success else []
            
        except Exception as e:
            logger.error(f"Failed to get user notifications: {str(e)}")
            return []

    async def get_unread_notifications(self, user_id: str) -> List[dict]:
        """Get unread notifications for a user"""
        try:
            success, notifications, error = await self.db.query_documents(
                COLLECTIONS['notifications'],
                [
                    ('recipient_id', '==', user_id),
                    ('is_read', '==', False)
                ],
                order_by=[('created_at', 'desc')]
            )
            
            return notifications if success else []
            
        except Exception as e:
            logger.error(f"Failed to get unread notifications: {str(e)}")
            return []

    async def mark_notifications_as_read(self, user_id: str, notification_ids: List[str]) -> bool:
        """Mark notifications as read"""
        try:
            for notification_id in notification_ids:
                # Verify notification belongs to user before updating
                success, notification, error = await self.db.get_document(
                    COLLECTIONS['notifications'], 
                    notification_id
                )
                
                if success and notification and notification.get('recipient_id') == user_id:
                    await self.db.update_document(
                        COLLECTIONS['notifications'],
                        notification_id,
                        {"is_read": True, "read_at": datetime.now()}
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark notifications as read: {str(e)}")
            return False

    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification (with user verification)"""
        try:
            # Verify the notification belongs to the user
            success, notification, error = await self.db.get_document(
                COLLECTIONS['notifications'], 
                notification_id
            )
            
            if not success or not notification or notification.get('recipient_id') != user_id:
                return False
            
            success, error = await self.db.delete_document(COLLECTIONS['notifications'], notification_id)
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete notification: {str(e)}")
            return False

    async def notify_admins_low_stock(self, building_id: str, alert_data: dict) -> bool:
        """Send low stock notification to admins"""
        try:
            # Get admin users for the building
            success, admins, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                [
                    ('building_id', '==', building_id),
                    ('role', '==', 'admin'),
                    ('status', '==', 'active')
                ]
            )
            
            if not success:
                return False
            
            item_name = alert_data.get('item_name', 'Unknown Item')
            current_stock = alert_data.get('current_stock', 0)
            alert_level = alert_data.get('alert_level', 'low')
            
            title = f"Low Stock Alert: {item_name}"
            message = f"{item_name} is {alert_level} ({current_stock} remaining)"
            
            # Create notifications for each admin
            for admin in admins:
                admin_id = admin.get('id') or admin.get('user_id')
                if admin_id:
                    await self.create_notification(
                        user_id=admin_id,
                        title=title,
                        message=message,
                        notification_type="low_stock_alert",
                        related_id=alert_data.get('inventory_id'),
                        send_push=True
                    )
            
            # Also send FCM alert
            await self.fcm.send_low_stock_alert(alert_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to notify admins of low stock: {str(e)}")
            return False

    async def notify_inventory_request_update(self, request_data: dict, notification_type: str) -> bool:
        """Send inventory request update notifications"""
        try:
            # Send FCM notification
            await self.fcm.send_inventory_request_notification(request_data, notification_type)
            
            # Create in-app notification
            if notification_type == "request_created":
                # Notify admins
                building_id = request_data.get('building_id')
                success, admins, error = await self.db.query_documents(
                    COLLECTIONS['user_profiles'],
                    [
                        ('building_id', '==', building_id),
                        ('role', '==', 'admin'),
                        ('status', '==', 'active')
                    ]
                )
                
                if success:
                    title = "New Inventory Request"
                    message = f"New request for {request_data.get('item_name', 'item')}"
                    
                    for admin in admins:
                        admin_id = admin.get('id') or admin.get('user_id')
                        if admin_id:
                            await self.create_notification(
                                user_id=admin_id,
                                title=title,
                                message=message,
                                notification_type="inventory_request",
                                related_id=request_data.get('id'),
                                send_push=False  # Already sent via FCM
                            )
            
            else:
                # Notify requester
                requester_id = request_data.get('requested_by')
                if requester_id:
                    status_messages = {
                        "request_approved": "Your inventory request has been approved",
                        "request_denied": "Your inventory request has been denied",
                        "request_fulfilled": "Your inventory request has been fulfilled"
                    }
                    
                    title = "Request Update"
                    message = status_messages.get(notification_type, "Your request status has been updated")
                    
                    await self.create_notification(
                        user_id=requester_id,
                        title=title,
                        message=message,
                        notification_type="inventory_request",
                        related_id=request_data.get('id'),
                        send_push=False  # Already sent via FCM
                    )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send inventory request notification: {str(e)}")
            return False

    async def notify_preventive_maintenance_due(self, building_id: str, maintenance_data: dict) -> bool:
        """Send preventive maintenance due notification to assigned staff and admins"""
        try:
            equipment_name = maintenance_data.get('equipment_name', 'Unknown Equipment')
            task_title = maintenance_data.get('task_title', 'Maintenance Task')
            scheduled_date = maintenance_data.get('scheduled_date')
            assigned_to = maintenance_data.get('assigned_to')
            priority = maintenance_data.get('priority', 'medium')
            
            # Format scheduled date
            date_str = "soon"
            if scheduled_date:
                if isinstance(scheduled_date, str):
                    scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
                date_str = scheduled_date.strftime("%B %d, %Y")
            
            # Determine notification urgency based on priority
            if priority == 'critical':
                title = f"🚨 CRITICAL Maintenance Due: {equipment_name}"
                body = f"Critical maintenance '{task_title}' is due {date_str}"
            elif priority == 'high':
                title = f"⚠️ HIGH Priority Maintenance: {equipment_name}"
                body = f"High priority maintenance '{task_title}' is due {date_str}"
            else:
                title = f"🔧 Maintenance Due: {equipment_name}"
                body = f"Maintenance '{task_title}' is scheduled for {date_str}"
            
            # Notify assigned technician if specified
            if assigned_to:
                await self.create_notification(
                    user_id=assigned_to,
                    title=title,
                    message=body,
                    notification_type="preventive_maintenance_due",
                    related_id=maintenance_data.get('task_id'),
                    send_push=True
                )
            
            # Also notify admins for high/critical priority tasks
            if priority in ['high', 'critical']:
                success, admins, error = await self.db.query_documents(
                    COLLECTIONS['user_profiles'],
                    [
                        ('building_id', '==', building_id),
                        ('role', '==', 'admin'),
                        ('status', '==', 'active')
                    ]
                )
                
                if success:
                    for admin in admins:
                        admin_id = admin.get('id') or admin.get('user_id')
                        if admin_id and admin_id != assigned_to:  # Don't duplicate if admin is assigned
                            await self.create_notification(
                                user_id=admin_id,
                                title=title,
                                message=body,
                                notification_type="preventive_maintenance_due",
                                related_id=maintenance_data.get('task_id'),
                                send_push=True
                            )
            
            # Send FCM notification
            await self.fcm.send_preventive_maintenance_notification(maintenance_data, "maintenance_due")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send preventive maintenance due notification: {str(e)}")
            return False

    async def notify_maintenance_task_assigned(self, building_id: str, task_data: dict) -> bool:
        """Send notification when maintenance task is assigned to a technician"""
        try:
            assigned_to = task_data.get('assigned_to')
            if not assigned_to:
                return False
            
            equipment_name = task_data.get('equipment_name', 'Unknown Equipment')
            task_title = task_data.get('task_title', 'Maintenance Task')
            scheduled_date = task_data.get('scheduled_date')
            priority = task_data.get('priority', 'medium')
            
            # Format scheduled date
            date_str = "soon"
            if scheduled_date:
                if isinstance(scheduled_date, str):
                    scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
                date_str = scheduled_date.strftime("%B %d, %Y at %I:%M %p")
            
            title = f"📋 New Maintenance Assignment"
            message = f"You've been assigned: '{task_title}' for {equipment_name} on {date_str}"
            
            await self.create_notification(
                user_id=assigned_to,
                title=title,
                message=message,
                notification_type="maintenance_task_assigned",
                related_id=task_data.get('task_id'),
                send_push=True
            )
            
            # Send FCM notification
            await self.fcm.send_preventive_maintenance_notification(task_data, "task_assigned")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send maintenance task assignment notification: {str(e)}")
            return False

    async def notify_maintenance_overdue(self, building_id: str, task_data: dict) -> bool:
        """Send notification when maintenance task becomes overdue"""
        try:
            assigned_to = task_data.get('assigned_to')
            equipment_name = task_data.get('equipment_name', 'Unknown Equipment')
            task_title = task_data.get('task_title', 'Maintenance Task')
            scheduled_date = task_data.get('scheduled_date')
            
            # Calculate how overdue
            overdue_days = 0
            if scheduled_date:
                if isinstance(scheduled_date, str):
                    scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
                overdue_days = (datetime.now() - scheduled_date).days
            
            title = f"🚨 OVERDUE Maintenance: {equipment_name}"
            message = f"'{task_title}' is {overdue_days} day(s) overdue"
            
            # Notify assigned technician
            if assigned_to:
                await self.create_notification(
                    user_id=assigned_to,
                    title=title,
                    message=message,
                    notification_type="maintenance_overdue",
                    related_id=task_data.get('task_id'),
                    send_push=True
                )
            
            # Also notify admins for overdue tasks
            success, admins, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                [
                    ('building_id', '==', building_id),
                    ('role', '==', 'admin'),
                    ('status', '==', 'active')
                ]
            )
            
            if success:
                for admin in admins:
                    admin_id = admin.get('id') or admin.get('user_id')
                    if admin_id and admin_id != assigned_to:  # Don't duplicate if admin is assigned
                        await self.create_notification(
                            user_id=admin_id,
                            title=title,
                            message=message,
                            notification_type="maintenance_overdue",
                            related_id=task_data.get('task_id'),
                            send_push=True
                        )
            
            # Send FCM notification
            await self.fcm.send_preventive_maintenance_notification(task_data, "maintenance_overdue")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send maintenance overdue notification: {str(e)}")
            return False

    async def notify_equipment_usage_threshold(self, building_id: str, threshold_data: dict) -> bool:
        """Send notification when equipment usage approaches maintenance threshold"""
        try:
            equipment_name = threshold_data.get('equipment_name', 'Unknown Equipment')
            current_usage = threshold_data.get('current_usage', 0)
            threshold = threshold_data.get('threshold', 0)
            usage_unit = threshold_data.get('usage_unit', 'hours')
            percentage = threshold_data.get('percentage_of_threshold', 0)
            
            if percentage >= 100:
                title = f"🚨 USAGE THRESHOLD EXCEEDED: {equipment_name}"
                message = f"{equipment_name} has exceeded usage threshold ({current_usage} {usage_unit})"
                priority = "critical"
            elif percentage >= 90:
                title = f"⚠️ Usage Threshold Alert: {equipment_name}"
                message = f"{equipment_name} is at {percentage}% of usage threshold ({current_usage}/{threshold} {usage_unit})"
                priority = "high"
            else:
                title = f"📊 Usage Threshold Warning: {equipment_name}"
                message = f"{equipment_name} is at {percentage}% of usage threshold ({current_usage}/{threshold} {usage_unit})"
                priority = "medium"
            
            # Notify admins and maintenance staff
            success, users, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                [
                    ('building_id', '==', building_id),
                    ('role', 'in', ['admin', 'staff']),
                    ('status', '==', 'active')
                ]
            )
            
            if success:
                for user in users:
                    user_id = user.get('id') or user.get('user_id')
                    if user_id:
                        await self.create_notification(
                            user_id=user_id,
                            title=title,
                            message=message,
                            notification_type="usage_threshold_alert",
                            related_id=threshold_data.get('equipment_id'),
                            send_push=True
                        )
            
            # Send FCM notification
            await self.fcm.send_equipment_usage_alert(threshold_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send equipment usage threshold notification: {str(e)}")
            return False

    async def notify_maintenance_completed(self, building_id: str, task_data: dict) -> bool:
        """Send notification when maintenance task is completed"""
        try:
            equipment_name = task_data.get('equipment_name', 'Unknown Equipment')
            task_title = task_data.get('task_title', 'Maintenance Task')
            completed_by = task_data.get('completed_by')
            completion_notes = task_data.get('completion_notes', '')
            
            title = f"✅ Maintenance Completed: {equipment_name}"
            message = f"'{task_title}' has been completed"
            if completion_notes:
                message += f" - {completion_notes[:100]}..."
            
            # Notify admins
            success, admins, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                [
                    ('building_id', '==', building_id),
                    ('role', '==', 'admin'),
                    ('status', '==', 'active')
                ]
            )
            
            if success:
                for admin in admins:
                    admin_id = admin.get('id') or admin.get('user_id')
                    if admin_id and admin_id != completed_by:  # Don't notify the person who completed it
                        await self.create_notification(
                            user_id=admin_id,
                            title=title,
                            message=message,
                            notification_type="maintenance_completed",
                            related_id=task_data.get('task_id'),
                            send_push=False  # Less urgent, no push needed
                        )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send maintenance completion notification: {str(e)}")
            return False

# Create global service instance
notification_service = NotificationService()

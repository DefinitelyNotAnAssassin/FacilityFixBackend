from typing import List, Dict, Any, Optional
import firebase_admin
from firebase_admin import messaging
import logging
from datetime import datetime
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)

class FCMService:
    """Firebase Cloud Messaging service for push notifications"""
    
    def __init__(self):
        self.db = database_service
    
    async def send_notification(
        self, 
        token: str, 
        title: str, 
        body: str, 
        data: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send a push notification to a specific device token"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )
            
            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending FCM notification: {str(e)}")
            return False
    
    async def send_to_multiple_tokens(
        self, 
        tokens: List[str], 
        title: str, 
        body: str, 
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Send notifications to multiple device tokens"""
        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                tokens=tokens,
            )
            
            response = messaging.send_multicast(message)
            logger.info(f"Successfully sent {response.success_count} messages")
            
            if response.failure_count > 0:
                logger.warning(f"Failed to send {response.failure_count} messages")
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        logger.error(f"Failed to send to token {tokens[idx]}: {resp.exception}")
            
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "responses": response.responses
            }
            
        except Exception as e:
            logger.error(f"Error sending multicast FCM notification: {str(e)}")
            return {"success_count": 0, "failure_count": len(tokens), "error": str(e)}
    
    async def send_to_topic(
        self, 
        topic: str, 
        title: str, 
        body: str, 
        data: Optional[Dict[str, str]] = None
    ) -> bool:
        """Send notification to a topic (e.g., all admins, all staff)"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                topic=topic,
            )
            
            response = messaging.send(message)
            logger.info(f"Successfully sent topic message: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending topic FCM notification: {str(e)}")
            return False
    
    async def subscribe_to_topic(self, tokens: List[str], topic: str) -> Dict[str, Any]:
        """Subscribe device tokens to a topic"""
        try:
            response = messaging.subscribe_to_topic(tokens, topic)
            logger.info(f"Successfully subscribed {response.success_count} tokens to topic {topic}")
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {str(e)}")
            return {"success_count": 0, "failure_count": len(tokens), "error": str(e)}
    
    async def unsubscribe_from_topic(self, tokens: List[str], topic: str) -> Dict[str, Any]:
        """Unsubscribe device tokens from a topic"""
        try:
            response = messaging.unsubscribe_from_topic(tokens, topic)
            logger.info(f"Successfully unsubscribed {response.success_count} tokens from topic {topic}")
            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
        except Exception as e:
            logger.error(f"Error unsubscribing from topic {topic}: {str(e)}")
            return {"success_count": 0, "failure_count": len(tokens), "error": str(e)}
    
    async def get_user_tokens(self, user_id: str) -> List[str]:
        """Get all FCM tokens for a user"""
        try:
            success, tokens_data, error = await self.db.query_documents(
                COLLECTIONS['user_fcm_tokens'],
                [('user_id', '==', user_id), ('is_active', '==', True)]
            )
            
            if success:
                return [token['fcm_token'] for token in tokens_data]
            else:
                logger.error(f"Error getting user tokens: {error}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting user tokens: {str(e)}")
            return []
    
    async def save_user_token(self, user_id: str, fcm_token: str, device_info: Dict[str, Any] = None) -> bool:
        """Save or update user's FCM token"""
        try:
            # Check if token already exists
            success, existing_tokens, error = await self.db.query_documents(
                COLLECTIONS['user_fcm_tokens'],
                [('user_id', '==', user_id), ('fcm_token', '==', fcm_token)]
            )
            
            if success and existing_tokens:
                # Update existing token
                token_doc = existing_tokens[0]
                doc_id = token_doc.get('_doc_id')
                update_data = {
                    'is_active': True,
                    'updated_at': datetime.now()
                }
                if device_info:
                    update_data['device_info'] = device_info
                
                success, error = await self.db.update_document(
                    COLLECTIONS['user_fcm_tokens'], 
                    doc_id, 
                    update_data
                )
                return success
            else:
                # Create new token record
                token_data = {
                    'user_id': user_id,
                    'fcm_token': fcm_token,
                    'device_info': device_info or {},
                    'is_active': True,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                success, token_id, error = await self.db.create_document(
                    COLLECTIONS['user_fcm_tokens'], 
                    token_data
                )
                return success
                
        except Exception as e:
            logger.error(f"Error saving user token: {str(e)}")
            return False
    
    async def deactivate_user_token(self, user_id: str, fcm_token: str) -> bool:
        """Deactivate a user's FCM token"""
        try:
            success, tokens, error = await self.db.query_documents(
                COLLECTIONS['user_fcm_tokens'],
                [('user_id', '==', user_id), ('fcm_token', '==', fcm_token)]
            )
            
            if success and tokens:
                token_doc = tokens[0]
                doc_id = token_doc.get('_doc_id')
                
                success, error = await self.db.update_document(
                    COLLECTIONS['user_fcm_tokens'],
                    doc_id,
                    {'is_active': False, 'updated_at': datetime.now()}
                )
                return success
            
            return True  # Token doesn't exist, consider it deactivated
            
        except Exception as e:
            logger.error(f"Error deactivating user token: {str(e)}")
            return False
    
    async def send_low_stock_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Send low stock alert to admins and relevant staff"""
        try:
            building_id = alert_data.get('building_id')
            item_name = alert_data.get('item_name')
            current_stock = alert_data.get('current_stock')
            alert_level = alert_data.get('alert_level')
            
            # Determine alert urgency and message
            if alert_level == "out_of_stock":
                title = "🚨 OUT OF STOCK ALERT"
                body = f"{item_name} is completely out of stock!"
                priority = "high"
            elif alert_level == "critical":
                title = "⚠️ CRITICAL LOW STOCK"
                body = f"{item_name} is critically low ({current_stock} remaining)"
                priority = "high"
            else:
                title = "📦 Low Stock Alert"
                body = f"{item_name} is running low ({current_stock} remaining)"
                priority = "normal"
            
            # Get admin and staff users for the building
            success, users, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                [
                    ('building_id', '==', building_id),
                    ('role', 'in', ['admin', 'staff']),
                    ('status', '==', 'active')
                ]
            )
            
            if not success:
                logger.error(f"Error getting users for low stock alert: {error}")
                return False
            
            # Collect all FCM tokens
            all_tokens = []
            for user in users:
                user_id = user.get('id') or user.get('user_id')
                if user_id:
                    tokens = await self.get_user_tokens(user_id)
                    all_tokens.extend(tokens)
            
            if not all_tokens:
                logger.warning("No FCM tokens found for low stock alert")
                return True  # Not an error, just no tokens to send to
            
            # Send notifications
            data = {
                "type": "low_stock_alert",
                "inventory_id": alert_data.get('inventory_id', ''),
                "building_id": building_id,
                "alert_level": alert_level,
                "priority": priority
            }
            
            result = await self.send_to_multiple_tokens(all_tokens, title, body, data)
            
            logger.info(f"Low stock alert sent: {result['success_count']} successful, {result['failure_count']} failed")
            return result['success_count'] > 0
            
        except Exception as e:
            logger.error(f"Error sending low stock alert: {str(e)}")
            return False
    
    async def send_inventory_request_notification(self, request_data: Dict[str, Any], notification_type: str) -> bool:
        """Send inventory request notifications (approval, denial, fulfillment)"""
        try:
            item_name = request_data.get('item_name', 'Unknown Item')
            quantity = request_data.get('quantity_requested') or request_data.get('quantity_approved', 0)
            requester_name = request_data.get('requester_name', 'Staff Member')
            
            if notification_type == "request_created":
                title = "📋 New Inventory Request"
                body = f"{requester_name} requested {quantity} units of {item_name}"
                target_roles = ['admin']
            elif notification_type == "request_approved":
                title = "✅ Request Approved"
                body = f"Your request for {quantity} units of {item_name} has been approved"
                target_roles = ['staff']  # Send to requester
            elif notification_type == "request_denied":
                title = "❌ Request Denied"
                body = f"Your request for {quantity} units of {item_name} has been denied"
                target_roles = ['staff']  # Send to requester
            elif notification_type == "request_fulfilled":
                title = "📦 Request Fulfilled"
                body = f"Your request for {quantity} units of {item_name} has been fulfilled"
                target_roles = ['staff']  # Send to requester
            else:
                logger.warning(f"Unknown notification type: {notification_type}")
                return False
            
            # Get target users
            building_id = request_data.get('building_id')
            filters = [('building_id', '==', building_id), ('status', '==', 'active')]
            
            if notification_type in ["request_approved", "request_denied", "request_fulfilled"]:
                # Send to specific requester
                requester_id = request_data.get('requested_by')
                if requester_id:
                    filters.append(('id', '==', requester_id))
            else:
                # Send to admins
                filters.append(('role', 'in', target_roles))
            
            success, users, error = await self.db.query_documents(COLLECTIONS['user_profiles'], filters)
            
            if not success:
                logger.error(f"Error getting users for inventory request notification: {error}")
                return False
            
            # Collect FCM tokens
            all_tokens = []
            for user in users:
                user_id = user.get('id') or user.get('user_id')
                if user_id:
                    tokens = await self.get_user_tokens(user_id)
                    all_tokens.extend(tokens)
            
            if not all_tokens:
                logger.warning("No FCM tokens found for inventory request notification")
                return True
            
            # Send notifications
            data = {
                "type": "inventory_request",
                "notification_type": notification_type,
                "request_id": request_data.get('id', ''),
                "building_id": building_id
            }
            
            result = await self.send_to_multiple_tokens(all_tokens, title, body, data)
            
            logger.info(f"Inventory request notification sent: {result['success_count']} successful, {result['failure_count']} failed")
            return result['success_count'] > 0
            
        except Exception as e:
            logger.error(f"Error sending inventory request notification: {str(e)}")
            return False
    
    async def send_preventive_maintenance_notification(self, maintenance_data: Dict[str, Any], notification_type: str) -> bool:
        """Send preventive maintenance FCM notifications"""
        try:
            equipment_name = maintenance_data.get('equipment_name', 'Unknown Equipment')
            task_title = maintenance_data.get('task_title', 'Maintenance Task')
            building_id = maintenance_data.get('building_id')
            priority = maintenance_data.get('priority', 'medium')
            assigned_to = maintenance_data.get('assigned_to')
            
            # Determine message based on notification type
            if notification_type == "maintenance_due":
                scheduled_date = maintenance_data.get('scheduled_date')
                date_str = "soon"
                if scheduled_date:
                    if isinstance(scheduled_date, str):
                        scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
                    date_str = scheduled_date.strftime("%B %d")
                
                if priority == 'critical':
                    title = f"🚨 CRITICAL Maintenance Due"
                    body = f"{equipment_name}: {task_title} due {date_str}"
                elif priority == 'high':
                    title = f"⚠️ HIGH Priority Maintenance"
                    body = f"{equipment_name}: {task_title} due {date_str}"
                else:
                    title = f"🔧 Maintenance Due"
                    body = f"{equipment_name}: {task_title} due {date_str}"
                    
            elif notification_type == "task_assigned":
                title = f"📋 New Maintenance Assignment"
                body = f"You've been assigned: {task_title} for {equipment_name}"
                
            elif notification_type == "maintenance_overdue":
                title = f"🚨 OVERDUE Maintenance"
                body = f"{equipment_name}: {task_title} is overdue"
                
            else:
                logger.warning(f"Unknown maintenance notification type: {notification_type}")
                return False
            
            # Determine target users
            target_users = []
            if notification_type == "task_assigned" and assigned_to:
                # Send only to assigned user
                target_users = [assigned_to]
            else:
                # Get relevant users (assigned + admins for high/critical priority)
                filters = [('building_id', '==', building_id), ('status', '==', 'active')]
                
                if assigned_to:
                    if priority in ['high', 'critical']:
                        # Include assigned user and admins
                        filters.append(('role', 'in', ['admin', 'staff']))
                    else:
                        # Include only assigned user
                        filters.append(('id', '==', assigned_to))
                else:
                    # No specific assignment, notify admins and maintenance staff
                    filters.append(('role', 'in', ['admin', 'staff']))
                
                success, users, error = await self.db.query_documents(COLLECTIONS['user_profiles'], filters)
                if success:
                    target_users = [user.get('id') or user.get('user_id') for user in users if user.get('id') or user.get('user_id')]
            
            # Collect FCM tokens
            all_tokens = []
            for user_id in target_users:
                if user_id:
                    tokens = await self.get_user_tokens(user_id)
                    all_tokens.extend(tokens)
            
            if not all_tokens:
                logger.warning(f"No FCM tokens found for maintenance notification: {notification_type}")
                return True
            
            # Send notifications
            data = {
                "type": "preventive_maintenance",
                "notification_type": notification_type,
                "task_id": maintenance_data.get('task_id', ''),
                "equipment_id": maintenance_data.get('equipment_id', ''),
                "building_id": building_id,
                "priority": priority
            }
            
            result = await self.send_to_multiple_tokens(all_tokens, title, body, data)
            
            logger.info(f"Preventive maintenance notification sent: {result['success_count']} successful, {result['failure_count']} failed")
            return result['success_count'] > 0
            
        except Exception as e:
            logger.error(f"Error sending preventive maintenance notification: {str(e)}")
            return False

    async def send_equipment_usage_alert(self, threshold_data: Dict[str, Any]) -> bool:
        """Send equipment usage threshold alert"""
        try:
            equipment_name = threshold_data.get('equipment_name', 'Unknown Equipment')
            current_usage = threshold_data.get('current_usage', 0)
            threshold = threshold_data.get('threshold', 0)
            usage_unit = threshold_data.get('usage_unit', 'hours')
            percentage = threshold_data.get('percentage_of_threshold', 0)
            building_id = threshold_data.get('building_id')
            
            # Determine alert level and message
            if percentage >= 100:
                title = f"🚨 USAGE THRESHOLD EXCEEDED"
                body = f"{equipment_name} exceeded {threshold} {usage_unit} threshold"
                priority = "high"
            elif percentage >= 90:
                title = f"⚠️ Usage Threshold Alert"
                body = f"{equipment_name} at {percentage}% of usage threshold"
                priority = "high"
            else:
                title = f"📊 Usage Threshold Warning"
                body = f"{equipment_name} at {percentage}% of usage threshold"
                priority = "normal"
            
            # Get admin and maintenance staff
            success, users, error = await self.db.query_documents(
                COLLECTIONS['user_profiles'],
                [
                    ('building_id', '==', building_id),
                    ('role', 'in', ['admin', 'staff']),
                    ('status', '==', 'active')
                ]
            )
            
            if not success:
                logger.error(f"Error getting users for usage threshold alert: {error}")
                return False
            
            # Collect FCM tokens
            all_tokens = []
            for user in users:
                user_id = user.get('id') or user.get('user_id')
                if user_id:
                    tokens = await self.get_user_tokens(user_id)
                    all_tokens.extend(tokens)
            
            if not all_tokens:
                logger.warning("No FCM tokens found for usage threshold alert")
                return True
            
            # Send notifications
            data = {
                "type": "usage_threshold_alert",
                "equipment_id": threshold_data.get('equipment_id', ''),
                "building_id": building_id,
                "current_usage": str(current_usage),
                "threshold": str(threshold),
                "percentage": str(percentage),
                "priority": priority
            }
            
            result = await self.send_to_multiple_tokens(all_tokens, title, body, data)
            
            logger.info(f"Usage threshold alert sent: {result['success_count']} successful, {result['failure_count']} failed")
            return result['success_count'] > 0
            
        except Exception as e:
            logger.error(f"Error sending usage threshold alert: {str(e)}")
            return False

# Create global service instance
fcm_service = FCMService()

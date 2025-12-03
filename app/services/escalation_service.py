"""
Auto-Escalation Service

Handles automatic priority escalation for aging items:
- Concern Slips
- Job Services
- Work Order Permits

Escalation Rules:
- LOW → MEDIUM after 3 days
- LOW → HIGH after 5 days
- MEDIUM → HIGH after 5 days

Only escalates items with status='pending'
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from app.core.config import settings

logger = logging.getLogger(__name__)


class EscalationService:
    """Service for automatic priority escalation of aging items"""
    
    # Collection configurations with field mappings
    ESCALATION_COLLECTIONS = {
        "concern_slips": {
            "priority_field": "priority",
            "created_at_field": "created_at",
            "status_field": "status",
            "display_id_field": "formatted_id",
            "title_field": "title"
        },
        "job_services": {
            "priority_field": "priority",
            "created_at_field": "created_at",
            "status_field": "status",
            "display_id_field": "id",
            "title_field": "title"
        },
        "work_order_permits": {
            "priority_field": "priority",
            "created_at_field": "created_at",
            "status_field": "status",
            "display_id_field": "formatted_id",
            "title_field": "title"
        }
    }
    
    # Terminal statuses that should NOT be escalated
    TERMINAL_STATUSES = {"completed", "closed", "rejected", "cancelled", "denied"}
    
    def __init__(self):
        self.db = database_service
    
    async def check_and_escalate_all(self) -> Dict[str, Any]:
        """
        Main entry point: check and escalate all collections
        
        Returns:
            Dictionary with escalation statistics
        """
        if not settings.ENABLE_AUTO_ESCALATION:
            logger.warning("⚠️ Auto-escalation is disabled in settings")
            return {"enabled": False, "message": "Auto-escalation disabled"}
        
        logger.info("🔄 Starting auto-escalation check...")
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "enabled": True,
            "total_escalated": 0,
            "total_processed": 0,
            "collections": {},
            "errors": []
        }
        
        # Process each collection
        for collection_name in self.ESCALATION_COLLECTIONS.keys():
            try:
                collection_result = await self._escalate_collection(collection_name)
                result["collections"][collection_name] = collection_result
                result["total_escalated"] += collection_result.get("escalated_count", 0)
                result["total_processed"] += collection_result.get("processed_count", 0)
            except Exception as e:
                error_msg = f"Error processing {collection_name}: {str(e)}"
                logger.error(f"❌ {error_msg}")
                result["errors"].append(error_msg)
        
        logger.info(f"✅ Auto-escalation complete: {result['total_escalated']} escalated, {result['total_processed']} processed")
        return result
    
    async def _escalate_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Process escalation for a single collection
        
        Args:
            collection_name: Name of collection to process
            
        Returns:
            Dictionary with collection-specific escalation results
        """
        config = self.ESCALATION_COLLECTIONS[collection_name]
        result = {
            "collection": collection_name,
            "processed_count": 0,
            "escalated_count": 0,
            "escalations": [],
            "errors": []
        }
        
        try:
            # Get all documents in collection
            success, documents, error = await self.db.query_documents(collection_name, [])
            
            if not success:
                logger.error(f"Failed to query {collection_name}: {error}")
                result["errors"].append(f"Query failed: {error}")
                return result
            
            if not documents:
                logger.debug(f"No documents found in {collection_name}")
                return result
            
            result["processed_count"] = len(documents)
            
            # Process each document (documents is a list, not dict)
            for doc_data in documents:
                # Get document ID - MUST use _doc_id for Firestore updates
                doc_id = doc_data.get("_doc_id")
                if not doc_id:
                    logger.warning(f"[ESCALATION] Document missing _doc_id: {doc_data.get('id', doc_data.get('formatted_id', 'unknown'))}")
                    continue
                
                # Skip items with terminal status
                status = doc_data.get(config["status_field"], "").lower()
                if status in self.TERMINAL_STATUSES:
                    continue
                
                # Only escalate "pending" status items
                if status != "pending":
                    continue
                
                # Get current priority
                current_priority = doc_data.get(config["priority_field"], "").lower()
                
                # Skip if no priority
                if not current_priority:
                    continue
                
                # Get created_at timestamp
                created_at = doc_data.get(config["created_at_field"])
                if not created_at:
                    logger.debug(f"No created_at for {collection_name} {doc_id}")
                    continue
                
                # Parse datetime if it's a string
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        logger.warning(f"Could not parse created_at for {doc_id}: {created_at}")
                        continue
                
                # Calculate age (in minutes if demo mode, otherwise in days)
                age_amount = self._calculate_age(created_at)
                
                # Determine if escalation is needed
                target_priority = self._determine_target_priority(current_priority, age_amount)
                
                if target_priority and target_priority != current_priority:
                    # Perform escalation
                    escalation_record = await self._perform_escalation(
                        collection_name=collection_name,
                        doc_id=doc_id,
                        doc_data=doc_data,
                        config=config,
                        old_priority=current_priority,
                        new_priority=target_priority,
                        age_amount=age_amount
                    )
                    
                    if escalation_record:
                        result["escalations"].append(escalation_record)
                        result["escalated_count"] += 1
        
        except Exception as e:
            error_msg = f"Unexpected error processing {collection_name}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            result["errors"].append(error_msg)
        
        return result
    
    def _calculate_age(self, created_at: datetime) -> int:
        """
        Calculate age based on configured time unit (days or minutes)
        
        Args:
            created_at: Creation datetime
            
        Returns:
            Age in configured unit (days or minutes)
        """
        now = datetime.utcnow()
        
        # Handle timezone-aware datetimes
        if created_at.tzinfo is not None:
            now = now.replace(tzinfo=created_at.tzinfo)
        
        time_difference = now - created_at
        
        if settings.ESCALATION_TIME_UNIT.lower() == "minutes":
            # Return age in minutes (for demo/testing)
            return int(time_difference.total_seconds() / 60)
        else:
            # Default: return age in days
            return time_difference.days
    
    def _determine_target_priority(self, current_priority: str, age_amount: int) -> Optional[str]:
        """
        Determine if priority should be escalated based on age
        
        Escalation rules (values interpreted as days or minutes based on ESCALATION_TIME_UNIT):
        - LOW → MEDIUM after 3 units
        - LOW → HIGH after 5 units
        - MEDIUM → HIGH after 5 units
        
        Args:
            current_priority: Current priority level (low, medium, high)
            age_amount: Age in configured unit (days or minutes)
            
        Returns:
            Target priority or None if no escalation needed
        """
        current_priority = current_priority.lower()
        
        if current_priority == "low":
            # LOW escalates to MEDIUM after 3 units, HIGH after 5 units
            if age_amount >= settings.ESCALATE_LOW_TO_HIGH_DAYS:
                return "high"
            elif age_amount >= settings.ESCALATE_LOW_TO_MED_DAYS:
                return "medium"
        
        elif current_priority == "medium":
            # MEDIUM escalates to HIGH after 5 units
            if age_amount >= settings.ESCALATE_MED_TO_HIGH_DAYS:
                return "high"
        
        # HIGH stays HIGH, no escalation needed
        return None
    
    async def _perform_escalation(
        self,
        collection_name: str,
        doc_id: str,
        doc_data: dict,
        config: dict,
        old_priority: str,
        new_priority: str,
        age_amount: int
    ) -> Optional[Dict[str, Any]]:
        """
        Execute escalation: update database and send notifications
        
        Args:
            collection_name: Collection name
            doc_id: Document ID
            doc_data: Complete document data
            config: Collection configuration
            old_priority: Old priority level
            new_priority: New priority level
            age_amount: Age in configured unit (days or minutes)
            
        Returns:
            Escalation record if successful, None otherwise
        """
        try:
            display_id = doc_data.get(config["display_id_field"], doc_id)
            title = doc_data.get(config["title_field"], "")
            
            # Update document priority
            update_data = {
                config["priority_field"]: new_priority,
                "updated_at": datetime.utcnow()
            }
            
            logger.info(f"[ESCALATION] Attempting to update {collection_name} doc_id={doc_id} with priority={new_priority}")
            success, error = await self.db.update_document(collection_name, doc_id, update_data)
            
            if not success:
                logger.error(f"[ESCALATION] Failed to update {collection_name} {doc_id}: {error}")
                return None
            
            logger.info(f"[ESCALATION] Successfully updated {collection_name} {doc_id}: priority changed to {new_priority}")
            
            # Create escalation message
            message = (
                f"Priority Escalated: {display_id} has been automatically escalated to {new_priority.upper()} "
                f"due to aging (Exceeded {settings.ESCALATE_LOW_TO_MED_DAYS} days medium "
                f"{settings.ESCALATE_MED_TO_HIGH_DAYS} days high)."
            )
            
            logger.info(f"✅ Escalated {collection_name} {display_id}: {old_priority} → {new_priority}")
            
            # Send escalation notification
            await self._send_escalation_notifications(
                collection_name=collection_name,
                item_id=display_id,
                item_data=doc_data,
                title=title,
                message=message,
                old_priority=old_priority,
                new_priority=new_priority
            )
            
            # Return escalation record
            return {
                "collection": collection_name,
                "item_id": display_id,
                "old_priority": old_priority,
                "new_priority": new_priority,
                "age_amount": age_amount,
                "time_unit": settings.ESCALATION_TIME_UNIT,
                "message": message,
                "escalated_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(f"❌ Error performing escalation for {doc_id}: {str(e)}")
            return None
    
    async def _send_escalation_notifications(
        self,
        collection_name: str,
        item_id: str,
        item_data: dict,
        title: str,
        message: str,
        old_priority: str,
        new_priority: str
    ) -> None:
        """
        Send escalation notification to both admins and tenants
        
        Args:
            collection_name: Collection name
            item_id: Item ID
            item_data: Item data
            title: Item title
            message: Escalation message
            old_priority: Old priority
            new_priority: New priority
        """
        try:
            from app.services.notification_manager import notification_manager
            from app.models.notification_models import NotificationPriority, NotificationType, NotificationChannel
            
            # Map item priority to notification priority
            priority_map = {
                "low": NotificationPriority.LOW,
                "medium": NotificationPriority.NORMAL,
                "high": NotificationPriority.HIGH
            }
            notification_priority = priority_map.get(new_priority.lower(), NotificationPriority.NORMAL)
            
            # ============ ADMIN NOTIFICATIONS ============
            # Get all admin users
            success, admin_users, error = await self.db.query_documents(
                COLLECTIONS['users'],
                [("role", "==", "admin")]
            )
            
            if success and admin_users:
                # Send notification to each admin
                for admin_user in admin_users:
                    try:
                        admin_id = admin_user.get("_doc_id") or admin_user.get("id")
                        
                        # Build admin action URL
                        action_url = f"/admin/maintenance/repair-tasks/{item_id}"
                        
                        await notification_manager.create_notification(
                            notification_type=NotificationType.ESCALATION,
                            recipient_id=admin_id,
                            title=f"Priority Escalated: {item_id}",
                            message=f"{title} has been automatically escalated from {old_priority.upper()} to {new_priority.upper()} due to aging. Please review and take action.",
                            related_entity_type=collection_name,
                            related_entity_id=item_id,
                            action_url=action_url,
                            action_label="View Item",
                            priority=notification_priority,
                            channels=[NotificationChannel.IN_APP],
                            requires_action=True,
                            custom_data={
                                "escalation_type": "auto_aging",
                                "old_priority": old_priority,
                                "new_priority": new_priority,
                                "collection": collection_name
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send notification to admin {admin_id}: {str(e)}")
            else:
                logger.warning(f"Could not fetch admins for notification: {error}")
            
            # ============ TENANT NOTIFICATIONS ============
            # Get the tenant who created the item
            # - reported_by for concern slips
            # - created_by for job services
            # - requested_by for work order permits
            created_by = item_data.get("requested_by") or item_data.get("reported_by") or item_data.get("created_by") or item_data.get("tenant_id")
            
            if created_by:
                try:
                    # Build tenant action URL
                    action_url = f"/tenant/maintenance/repair-tasks/{item_id}"
                    
                    # Calculate age for message
                    created_at = item_data.get("created_at")
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        except (ValueError, AttributeError):
                            created_at = None
                    
                    age_amount = self._calculate_age(created_at) if created_at else "several"
                    time_unit = settings.ESCALATION_TIME_UNIT
                    
                    await notification_manager.create_notification(
                        notification_type=NotificationType.ESCALATION,
                        recipient_id=created_by,
                        title=f"Priority Escalated: {item_id}",
                        message=f"Your {title} priority has been automatically escalated from {old_priority.upper()} to {new_priority.upper()} because it's been pending for {age_amount} {time_unit}. We're prioritizing this for you.",
                        related_entity_type=collection_name,
                        related_entity_id=item_id,
                        action_url=action_url,
                        action_label="View Item",
                        priority=notification_priority,
                        channels=[NotificationChannel.IN_APP],
                        requires_action=False,
                        custom_data={
                            "escalation_type": "auto_aging",
                            "old_priority": old_priority,
                            "new_priority": new_priority,
                            "collection": collection_name
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to send notification to tenant {created_by}: {str(e)}")
            else:
                logger.debug(f"No tenant found for {item_id}, skipping tenant notification")
        
        except Exception as e:
            logger.error(f"Error sending escalation notifications: {str(e)}")


# Singleton instance
escalation_service = EscalationService()

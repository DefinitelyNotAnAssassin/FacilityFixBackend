from celery import current_task
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from ..core.celery_app import celery_app
from ..services.inventory_service import inventory_service
from ..services.fcm_service import fcm_service
from ..services.notification_service import notification_service
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def check_all_low_stock_alerts(self):
    """Check all inventory items for low stock conditions and create alerts"""
    try:
        logger.info("Starting low stock alert check for all buildings")
        
        # Get all buildings
        success, buildings, error = database_service.query_documents(
            COLLECTIONS['buildings'], []
        )
        
        if not success:
            logger.error(f"Failed to get buildings: {error}")
            return {'status': 'error', 'message': error}
        
        total_alerts_created = 0
        buildings_processed = 0
        
        for building in buildings:
            building_id = building.get('id')
            if not building_id:
                continue
                
            try:
                alerts_created = _check_building_low_stock(building_id)
                total_alerts_created += alerts_created
                buildings_processed += 1
                
                # Update task progress
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': buildings_processed,
                        'total': len(buildings),
                        'alerts_created': total_alerts_created
                    }
                )
                
            except Exception as e:
                logger.error(f"Error checking low stock for building {building_id}: {str(e)}")
                continue
        
        logger.info(f"Low stock check completed. Created {total_alerts_created} alerts across {buildings_processed} buildings")
        
        return {
            'status': 'completed',
            'buildings_processed': buildings_processed,
            'alerts_created': total_alerts_created,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in low stock alert check: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def send_reorder_reminders(self):
    """Send reorder reminders for items that have been low stock for extended periods"""
    try:
        logger.info("Starting reorder reminder process")
        
        # Get all active low stock alerts older than 24 hours
        cutoff_date = datetime.now() - timedelta(hours=24)
        
        success, alerts, error = database_service.query_documents(
            COLLECTIONS['low_stock_alerts'],
            [('status', '==', 'low stock')]
        )
        
        if not success:
            logger.error(f"Failed to get low stock alerts: {error}")
            return {'status': 'error', 'message': error}
        
        # Filter alerts older than cutoff
        old_alerts = [
            alert for alert in alerts
            if alert.get('created_at', datetime.now()) < cutoff_date
        ]
        
        reminders_sent = 0
        
        for alert in old_alerts:
            try:
                building_id = alert.get('building_id')
                item_name = alert.get('item_name')
                alert_level = alert.get('alert_level', 'low')
                
                # Create reorder reminder notification
                title = f"Reorder Reminder: {item_name}"
                body = f"{item_name} has been {alert_level} stock for over 24 hours. Consider reordering."
                
                # Send to building admins
                success, admins, error = database_service.query_documents(
                    COLLECTIONS['user_profiles'],
                    [
                        ('building_id', '==', building_id),
                        ('role', '==', 'admin'),
                        ('status', '==', 'active')
                    ]
                )
                
                if success and admins:
                    for admin in admins:
                        admin_id = admin.get('id') or admin.get('user_id')
                        if admin_id:
                            notification_service.create_notification(
                                user_id=admin_id,
                                title=title,
                                message=body,
                                notification_type="reorder_reminder",
                                related_id=alert.get('inventory_id'),
                                send_push=True
                            )
                    
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Error sending reorder reminder for alert {alert.get('id')}: {str(e)}")
                continue
        
        logger.info(f"Reorder reminder process completed. Sent {reminders_sent} reminders")
        
        return {
            'status': 'completed',
            'reminders_sent': reminders_sent,
            'alerts_processed': len(old_alerts),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in reorder reminder process: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task
def process_inventory_request_approval(request_id: str, approved_by: str, quantity_approved: int = None, admin_notes: str = None):
    """Process inventory request approval in background"""
    try:
        logger.info(f"Processing inventory request approval: {request_id}")
        
        success, error = inventory_service.approve_inventory_request(
            request_id=request_id,
            approved_by=approved_by,
            quantity_approved=quantity_approved,
            admin_notes=admin_notes
        )
        
        if success:
            # Get request data for notification
            success, request_data, error = database_service.get_document(
                COLLECTIONS['inventory_requests'], 
                request_id
            )
            
            if success and request_data:
                # Send notification to requester
                notification_service.notify_inventory_request_update(
                    request_data, 
                    "request_approved"
                )
            
            logger.info(f"Successfully processed approval for request {request_id}")
            return {'status': 'completed', 'request_id': request_id}
        else:
            logger.error(f"Failed to approve request {request_id}: {error}")
            raise Exception(error)
            
    except Exception as e:
        logger.error(f"Error processing request approval: {str(e)}")
        raise

@celery_app.task
def auto_fulfill_approved_requests():
    """Automatically fulfill approved requests where stock is available"""
    try:
        logger.info("Starting auto-fulfillment of approved requests")
        
        # Get all approved requests
        success, requests, error = database_service.query_documents(
            COLLECTIONS['inventory_requests'],
            [('status', '==', 'approved')]
        )
        
        if not success:
            logger.error(f"Failed to get approved requests: {error}")
            return {'status': 'error', 'message': error}
        
        fulfilled_count = 0
        
        for request in requests:
            try:
                request_id = request.get('id') or request.get('_doc_id')
                inventory_id = request.get('inventory_id')
                quantity_needed = request.get('quantity_approved', 0)
                
                if not all([request_id, inventory_id, quantity_needed]):
                    continue
                
                # Check stock availability
                success, item_data, error = inventory_service.get_inventory_item(inventory_id)
                if not success:
                    continue
                
                current_stock = item_data.get('current_stock', 0)
                
                # Auto-fulfill if stock is available
                if current_stock >= quantity_needed:
                    success, error = inventory_service.fulfill_inventory_request(
                        request_id, 
                        "system_auto_fulfill"
                    )
                    
                    if success:
                        fulfilled_count += 1
                        
                        # Send notification
                        notification_service.notify_inventory_request_update(
                            request, 
                            "request_fulfilled"
                        )
                        
            except Exception as e:
                logger.error(f"Error auto-fulfilling request {request.get('id')}: {str(e)}")
                continue
        
        logger.info(f"Auto-fulfillment completed. Fulfilled {fulfilled_count} requests")
        
        return {
            'status': 'completed',
            'requests_fulfilled': fulfilled_count,
            'requests_processed': len(requests),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in auto-fulfillment process: {str(e)}")
        raise

def _check_building_low_stock(building_id: str) -> int:
    """Helper function to check low stock for a specific building"""
    try:
        # Get all active inventory items for the building
        success, items, error = inventory_service.get_inventory_by_building(building_id)
        if not success:
            logger.error(f"Failed to get inventory for building {building_id}: {error}")
            return 0
        
        alerts_created = 0
        
        for item in items:
            try:
                item_id = item.get('id')
                current_stock = item.get('current_stock', 0)
                reorder_level = item.get('reorder_level', 0)
                
                if current_stock <= reorder_level:
                    # Check if alert already exists
                    success, existing_alerts, error = database_service.query_documents(
                        COLLECTIONS['low_stock_alerts'],
                        [
                            ('inventory_id', '==', item_id),
                            ('status', '==', 'active')
                        ]
                    )
                    
                    if success and not existing_alerts:
                        # Determine alert level
                        if current_stock == 0:
                            alert_level = "out_of_stock"
                        elif current_stock <= reorder_level * 0.5:
                            alert_level = "critical"
                        else:
                            alert_level = "low"
                        
                        # Create alert
                        alert_data = {
                            'inventory_id': item_id,
                            'building_id': building_id,
                            'item_name': item.get('item_name'),
                            'current_stock': current_stock,
                            'reorder_level': reorder_level,
                            'alert_level': alert_level,
                            'status': 'active',
                            'created_at': datetime.now()
                        }
                        
                        success, alert_id, error = database_service.create_document(
                            COLLECTIONS['low_stock_alerts'],
                            alert_data
                        )
                        
                        if success:
                            alerts_created += 1
                            
                            # Send immediate notification
                            fcm_service.send_low_stock_alert(alert_data)
                            notification_service.notify_admins_low_stock(building_id, alert_data)
                            
            except Exception as e:
                logger.error(f"Error checking item {item.get('id')}: {str(e)}")
                continue
        
        return alerts_created
        
    except Exception as e:
        logger.error(f"Error checking low stock for building {building_id}: {str(e)}")
        return 0

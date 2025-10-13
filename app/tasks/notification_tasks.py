from celery import current_task
from datetime import datetime, timedelta
import logging
from ..core.celery_app import celery_app
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def cleanup_old_notifications(self, days_to_keep: int = 30):
    """Clean up old read notifications to prevent database bloat"""
    try:
        logger.info(f"Starting cleanup of notifications older than {days_to_keep} days")
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Get old read notifications
        success, old_notifications, error = database_service.query_documents(
            COLLECTIONS['notifications'],
            [
                ('is_read', '==', True),
                ('created_at', '<', cutoff_date)
            ]
        )
        
        if not success:
            logger.error(f"Failed to get old notifications: {error}")
            return {'status': 'error', 'message': error}
        
        deleted_count = 0
        
        for notification in old_notifications:
            try:
                notification_id = notification.get('id') or notification.get('_doc_id')
                if notification_id:
                    success, error = database_service.delete_document(
                        COLLECTIONS['notifications'], 
                        notification_id
                    )
                    
                    if success:
                        deleted_count += 1
                    else:
                        logger.error(f"Failed to delete notification {notification_id}: {error}")
                        
                # Update progress
                current_task.update_state(
                    state='PROGRESS',
                    meta={'current': deleted_count, 'total': len(old_notifications)}
                )
                        
            except Exception as e:
                logger.error(f"Error deleting notification: {str(e)}")
                continue
        
        logger.info(f"Notification cleanup completed. Deleted {deleted_count} old notifications")
        
        return {
            'status': 'completed',
            'notifications_deleted': deleted_count,
            'notifications_processed': len(old_notifications),
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in notification cleanup: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task
def send_bulk_notification(user_ids: list, title: str, message: str, notification_type: str = "info", related_id: str = None):
    """Send notifications to multiple users in bulk"""
    try:
        logger.info(f"Sending bulk notification to {len(user_ids)} users")
        
        from ..services.notification_service import notification_service
        
        sent_count = 0
        failed_count = 0
        
        for user_id in user_ids:
            try:
                success = notification_service.create_notification(
                    user_id=user_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    related_id=related_id,
                    send_push=True
                )
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {str(e)}")
                failed_count += 1
                continue
        
        logger.info(f"Bulk notification completed. Sent: {sent_count}, Failed: {failed_count}")
        
        return {
            'status': 'completed',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'total_users': len(user_ids),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in bulk notification: {str(e)}")
        raise

@celery_app.task
def send_scheduled_maintenance_reminders():
    """Send reminders for upcoming scheduled maintenance tasks"""
    try:
        logger.info("Sending scheduled maintenance reminders")
        
        # Get maintenance tasks scheduled for tomorrow
        tomorrow = datetime.now() + timedelta(days=1)
        start_of_tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_tomorrow = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        success, tasks, error = database_service.query_documents(
            COLLECTIONS['maintenance_tasks'],
            [
                ('status', '==', 'scheduled'),
                ('scheduled_date', '>=', start_of_tomorrow),
                ('scheduled_date', '<=', end_of_tomorrow)
            ]
        )
        
        if not success:
            logger.error(f"Failed to get scheduled tasks: {error}")
            return {'status': 'error', 'message': error}
        
        reminders_sent = 0
        
        for task in tasks:
            try:
                assigned_to = task.get('assigned_to')
                if not assigned_to:
                    continue
                
                title = "Maintenance Task Reminder"
                message = f"You have a maintenance task scheduled for tomorrow: {task.get('task_description', 'Unknown task')}"
                
                from ..services.notification_service import notification_service
                
                success = notification_service.create_notification(
                    user_id=assigned_to,
                    title=title,
                    message=message,
                    notification_type="maintenance_reminder",
                    related_id=task.get('id'),
                    send_push=True
                )
                
                if success:
                    reminders_sent += 1
                    
            except Exception as e:
                logger.error(f"Error sending reminder for task {task.get('id')}: {str(e)}")
                continue
        
        logger.info(f"Maintenance reminders completed. Sent {reminders_sent} reminders")
        
        return {
            'status': 'completed',
            'reminders_sent': reminders_sent,
            'tasks_processed': len(tasks),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending maintenance reminders: {str(e)}")
        raise

from celery import current_task
from datetime import datetime, timedelta
import logging
import asyncio
from ..core.celery_app import celery_app
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..core.config import settings

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
    """Send reminders for upcoming scheduled maintenance tasks at 7 days, 3 days, and 1 day before"""
    # Run the async function in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_maintenance_reminders_async())
    finally:
        loop.close()


async def _send_maintenance_reminders_async():
    """Async helper for sending maintenance reminders"""
    try:
        from ..core.config import settings
        
        # Get reminder intervals from config (supports both days and minutes for demo)
        reminder_intervals = settings.MAINTENANCE_REMINDER_DAYS  # e.g., [7, 3, 1] or [2, 1, 0.5] for demo
        
        logger.info(f"Sending scheduled maintenance reminders (intervals: {reminder_intervals})")
        print(f"[MAINTENANCE_REMINDER] Starting reminder check with intervals: {reminder_intervals}")
        
        now = datetime.now()
        reminders_sent = 0
        tasks_checked = set()  # Track which tasks we've checked to avoid duplicates
        
        # Check for reminders at configured intervals
        for interval in reminder_intervals:
            # Calculate the target date (supports both days and fractional minutes)
            if interval >= 1:
                # Treat as days
                target_date = now + timedelta(days=interval)
                time_unit = "days"
            else:
                # Treat as minutes (for demo mode)
                target_date = now + timedelta(minutes=interval * 60)
                time_unit = "minutes"
            
            start_of_target = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_target = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            logger.info(f"Checking for tasks scheduled {interval} {time_unit} from now ({start_of_target})")
            print(f"[MAINTENANCE_REMINDER] Checking for reminders in {interval} {time_unit}")
            
            # Query only by status (no composite index needed), then filter dates in code
            success, all_scheduled_tasks, error = await database_service.query_documents(
                COLLECTIONS['maintenance_tasks'],
                [('status', '==', 'scheduled')]
            )
            
            if not success:
                logger.error(f"Failed to get scheduled tasks: {error}")
                continue
            
            # Filter tasks by scheduled date in code (avoids needing composite index)
            # Handle both naive and aware datetimes
            from datetime import timezone
            tasks = []
            for t in all_scheduled_tasks:
                sched_date = t.get('scheduled_date')
                if not sched_date:
                    continue
                # Make both datetimes comparable (convert naive to aware if needed)
                if sched_date.tzinfo is None:
                    sched_date = sched_date.replace(tzinfo=timezone.utc)
                if start_of_target.tzinfo is None:
                    start_cmp = start_of_target.replace(tzinfo=timezone.utc)
                    end_cmp = end_of_target.replace(tzinfo=timezone.utc)
                else:
                    start_cmp = start_of_target
                    end_cmp = end_of_target
                
                if start_cmp <= sched_date <= end_cmp:
                    tasks.append(t)
            
            logger.info(f"Found {len(tasks)} tasks scheduled {interval} {time_unit} from now")
            print(f"[MAINTENANCE_REMINDER] Found {len(tasks)} tasks for {interval} {time_unit} interval")
            
            for task in tasks:
                try:
                    task_id = task.get('id')
                    assigned_to = task.get('assigned_to')
                    
                    # Skip if no assignment or already processed this task for this reminder
                    if not assigned_to or task_id in tasks_checked:
                        continue
                    
                    tasks_checked.add(task_id)
                    
                    task_title = task.get('task_title', task.get('task_description', 'Maintenance Task'))
                    location = task.get('location', 'Unknown Location')
                    scheduled_date = task.get('scheduled_date')
                    
                    # Format the reminder message based on interval
                    if interval >= 1:
                        # Days mode
                        if interval >= 7:
                            reminder_text = "in 1 week"
                            urgency = "upcoming"
                        elif interval >= 3:
                            reminder_text = "in 3 days"
                            urgency = "approaching"
                        else:  # 1 day or less
                            reminder_text = "tomorrow"
                            urgency = "urgent"
                    else:
                        # Minutes mode (demo)
                        minutes = int(interval * 60)
                        reminder_text = f"in {minutes} minutes"
                        urgency = "demo-urgent"
                    
                    title = f"Maintenance Task Reminder - {urgency.title()}"
                    message = f"Reminder: You have a maintenance task '{task_title}' at {location} scheduled for {reminder_text}."
                    
                    # Convert assigned_to (staff_id) to Firebase UID
                    from ..services.user_id_service import user_id_service
                    user_profile = await user_id_service.get_staff_profile_from_staff_id(assigned_to)
                    
                    if not user_profile:
                        logger.warning(f"Could not find user profile for staff_id {assigned_to}")
                        continue
                    
                    firebase_uid = user_profile.id
                    
                    # Send the reminder notification
                    from ..services.notification_manager import notification_manager
                    
                    print(f"[MAINTENANCE_REMINDER] Sending {interval}-interval reminder for task {task_id} to {firebase_uid}")
                    print(f"[MAINTENANCE_REMINDER] Message: {message}")
                    
                    success_result = await notification_manager.create_notification(
                        notification_type='maintenance_overdue',
                        recipient_id=firebase_uid,
                        title=title,
                        message=message,
                        related_entity_type="maintenance_task",
                        related_entity_id=task_id,
                        priority='high',
                        channels=['in_app', 'push', 'email'],
                        action_url=f"{settings.FRONTEND_URL}/#/maintenance/{task_id}",
                        action_label="View Task",
                        requires_action=True
                    )
                    
                    if success_result[0]:  # First element of tuple is success boolean
                        reminders_sent += 1
                        logger.info(f"✓ Sent {interval}-interval reminder for task {task_id}")
                        print(f"[MAINTENANCE_REMINDER] ✓ Reminder sent for task {task_id}")
                    else:
                        logger.warning(f"✗ Failed to send {interval}-interval reminder for task {task_id}: {success_result[2]}")
                        print(f"[MAINTENANCE_REMINDER] ✗ Failed to send reminder: {success_result[2]}")
                    
                except Exception as e:
                    logger.error(f"Error sending {interval}-interval reminder for task {task.get('id')}: {str(e)}")
                    import traceback
                    print(f"[MAINTENANCE_REMINDER] ERROR: {traceback.format_exc()}")
                    continue
        
        logger.info(f"Maintenance reminders completed. Sent {reminders_sent} reminders")
        print(f"[MAINTENANCE_REMINDER] Total reminders sent: {reminders_sent}")
        
        return {
            'status': 'completed',
            'reminders_sent': reminders_sent,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in send_scheduled_maintenance_reminders: {str(e)}")
        import traceback
        print(f"[MAINTENANCE_REMINDER] CRITICAL ERROR: {traceback.format_exc()}")
        raise

from celery import current_task
from datetime import datetime, timedelta
import logging
from ..core.celery_app import celery_app
from ..services.maintenance_scheduler_service import maintenance_scheduler_service
from ..services.equipment_usage_service import equipment_usage_service

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def generate_scheduled_maintenance_tasks(self, days_ahead: int = 30):
    """Generate scheduled maintenance tasks for the next N days"""
    try:
        logger.info(f"Starting scheduled maintenance task generation for {days_ahead} days ahead")
        
        success, tasks_generated, error = maintenance_scheduler_service.generate_scheduled_tasks(days_ahead)
        
        if success:
            logger.info(f"Successfully generated {tasks_generated} maintenance tasks")
            return {
                'status': 'completed',
                'tasks_generated': tasks_generated,
                'days_ahead': days_ahead,
                'timestamp': datetime.now().isoformat()
            }
        else:
            logger.error(f"Failed to generate maintenance tasks: {error}")
            raise Exception(error)
            
    except Exception as e:
        logger.error(f"Error in scheduled maintenance task generation: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def check_usage_based_maintenance(self):
    """Check usage-based maintenance schedules and generate tasks when thresholds are met"""
    try:
        logger.info("Starting usage-based maintenance check")
        
        success, tasks_generated, error = maintenance_scheduler_service.check_usage_based_schedules()
        
        if success:
            logger.info(f"Usage-based maintenance check completed. Generated {tasks_generated} tasks")
            return {
                'status': 'completed',
                'tasks_generated': tasks_generated,
                'timestamp': datetime.now().isoformat()
            }
        else:
            logger.error(f"Failed usage-based maintenance check: {error}")
            raise Exception(error)
            
    except Exception as e:
        logger.error(f"Error in usage-based maintenance check: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def generate_maintenance_reports(self, building_id: str = None, report_type: str = "weekly"):
    """Generate maintenance reports"""
    try:
        logger.info(f"Generating {report_type} maintenance report for building {building_id or 'all'}")
        
        # Calculate period based on report type
        if report_type == "daily":
            period_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            period_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999) - timedelta(days=1)
        elif report_type == "weekly":
            period_start = datetime.now() - timedelta(days=7)
            period_end = datetime.now()
        elif report_type == "monthly":
            period_start = datetime.now() - timedelta(days=30)
            period_end = datetime.now()
        else:
            period_start = datetime.now() - timedelta(days=7)
            period_end = datetime.now()
        
        # This would integrate with a reporting service
        # For now, we'll return a placeholder response
        
        logger.info(f"Maintenance report generation completed for {report_type}")
        return {
            'status': 'completed',
            'report_type': report_type,
            'building_id': building_id,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating maintenance report: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def check_overdue_maintenance_tasks(self):
    """Check for overdue maintenance tasks and send alerts"""
    try:
        logger.info("Checking for overdue maintenance tasks")
        
        from ..database.database_service import database_service
        from ..database.collections import COLLECTIONS
        
        # Get tasks that are overdue (scheduled_date < now and status = scheduled)
        current_time = datetime.now()
        
        success, overdue_tasks, error = database_service.query_documents(
            COLLECTIONS['maintenance_tasks'],
            [
                ('status', '==', 'scheduled'),
                ('scheduled_date', '<', current_time)
            ]
        )
        
        if not success:
            raise Exception(f"Failed to get overdue tasks: {error}")
        
        # Update overdue tasks status
        overdue_count = 0
        for task in overdue_tasks:
            try:
                task_id = task.get('id')
                success, error = database_service.update_document(
                    COLLECTIONS['maintenance_tasks'],
                    task_id,
                    {
                        'status': 'overdue',
                        'updated_at': datetime.now()
                    }
                )
                
                if success:
                    overdue_count += 1
                    
                    # Send notification to assigned user
                    assigned_to = task.get('assigned_to')
                    if assigned_to:
                        from ..services.notification_service import notification_service
                        
                        notification_service.create_notification(
                            user_id=assigned_to,
                            title="Overdue Maintenance Task",
                            message=f"Task '{task.get('task_title', 'Unknown')}' is overdue",
                            notification_type="maintenance_overdue",
                            related_id=task_id,
                            send_push=True
                        )
                
            except Exception as e:
                logger.error(f"Error processing overdue task {task.get('id')}: {str(e)}")
                continue
        
        logger.info(f"Processed {overdue_count} overdue maintenance tasks")
        return {
            'status': 'completed',
            'overdue_tasks_processed': overdue_count,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking overdue maintenance tasks: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def check_equipment_usage_thresholds(self, building_id: str = None):
    """Check equipment usage against maintenance thresholds"""
    try:
        logger.info(f"Checking equipment usage thresholds for building {building_id or 'all'}")
        
        success, threshold_alerts, error = equipment_usage_service.check_usage_thresholds(building_id)
        
        if not success:
            raise Exception(f"Failed to check usage thresholds: {error}")
        
        # Send notifications for equipment approaching thresholds
        notifications_sent = 0
        for alert in threshold_alerts:
            try:
                if alert['percentage_of_threshold'] >= 90:  # 90% of threshold reached
                    # Get building admins to notify
                    from ..database.database_service import database_service
                    from ..database.collections import COLLECTIONS
                    
                    success, admins, error = database_service.query_documents(
                        COLLECTIONS['user_profiles'],
                        [
                            ('role', '==', 'admin'),
                            ('building_id', '==', alert.get('building_id'))
                        ]
                    )
                    
                    if success:
                        from ..services.notification_service import notification_service
                        
                        for admin in admins:
                            notification_service.create_notification(
                                user_id=admin.get('id'),
                                title="Equipment Usage Threshold Alert",
                                message=f"{alert['equipment_name']} has reached {alert['percentage_of_threshold']}% of usage threshold",
                                notification_type="usage_threshold_alert",
                                related_id=alert['equipment_id'],
                                send_push=True
                            )
                            notifications_sent += 1
                
            except Exception as e:
                logger.error(f"Error sending threshold alert for equipment {alert.get('equipment_id')}: {str(e)}")
                continue
        
        logger.info(f"Usage threshold check completed. {len(threshold_alerts)} alerts, {notifications_sent} notifications sent")
        return {
            'status': 'completed',
            'threshold_alerts': len(threshold_alerts),
            'notifications_sent': notifications_sent,
            'building_id': building_id,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking equipment usage thresholds: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

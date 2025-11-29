from celery import Celery
from .config import settings
import os

# Create Celery instance
celery_app = Celery(
    "facilityfix",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=[
        "app.tasks.inventory_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.maintenance_tasks",
        "app.tasks.auth_tasks"  # Added for password reset OTP cleanup
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic task schedule
celery_app.conf.beat_schedule = {
    # Generate daily usage analytics
    'generate-daily-analytics': {
        'task': 'app.tasks.analytics_tasks.generate_daily_usage_analytics',
        'schedule': 3600.0,  # Every hour
    },
    # Generate weekly analytics
    'generate-weekly-analytics': {
        'task': 'app.tasks.analytics_tasks.generate_weekly_usage_analytics',
        'schedule': 86400.0,  # Every day
    },
    # Generate monthly analytics
    'generate-monthly-analytics': {
        'task': 'app.tasks.analytics_tasks.generate_monthly_usage_analytics',
        'schedule': 86400.0 * 7,  # Every week
    },
    # Check for low stock alerts
    'check-low-stock-alerts': {
        'task': 'app.tasks.inventory_tasks.check_all_low_stock_alerts',
        'schedule': 1800.0,  # Every 30 minutes
    },
    # Send reorder reminders
    'send-reorder-reminders': {
        'task': 'app.tasks.inventory_tasks.send_reorder_reminders',
        'schedule': 86400.0,  # Daily
    },
    # Clean up old notifications
    'cleanup-old-notifications': {
        'task': 'app.tasks.notification_tasks.cleanup_old_notifications',
        'schedule': 86400.0 * 7,  # Weekly
    },
    # Generate preventive maintenance tasks
    'generate-preventive-maintenance-tasks': {
        'task': 'app.tasks.maintenance_tasks.generate_scheduled_maintenance_tasks',
        'schedule': 86400.0,  # Daily at midnight
    },
    # Check usage-based maintenance schedules
    'check-usage-based-maintenance': {
        'task': 'app.tasks.maintenance_tasks.check_usage_based_maintenance',
        'schedule': 3600.0,  # Every hour
    },
    # Check for overdue maintenance tasks
    'check-overdue-maintenance': {
        'task': 'app.tasks.maintenance_tasks.check_overdue_maintenance_tasks',
        'schedule': 3600.0,  # Every hour
    },
    # Check equipment usage thresholds
    'check-equipment-usage-thresholds': {
        'task': 'app.tasks.maintenance_tasks.check_equipment_usage_thresholds',
        'schedule': 7200.0,  # Every 2 hours
    },
    # Send maintenance reminders (existing task, keeping for compatibility)
    'send-maintenance-reminders': {
        'task': 'app.tasks.notification_tasks.send_scheduled_maintenance_reminders',
        'schedule': 86400.0,  # Daily
    },
    # Clean up expired password reset OTPs
    'cleanup-expired-password-reset-otps': {
        'task': 'app.tasks.auth_tasks.cleanup_expired_password_reset_otps',
        'schedule': 3600.0,  # Every hour
    },
}

celery_app.conf.timezone = 'UTC'

"""
APScheduler setup for automatic escalation tasks.
Runs independently without Redis dependency.
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def escalation_job():
    """Background job that checks and escalates items"""
    try:
        import asyncio
        from app.services.escalation_service import escalation_service
        
        logger.info(f"[{datetime.now()}] 🔄 Running automatic escalation check...")
        result = asyncio.run(escalation_service.check_and_escalate_all())
        
        if result.get('total_escalated', 0) > 0:
            logger.info(f"✅ Escalation complete: {result['total_escalated']} items escalated")
            logger.info(f"   Time unit: {result.get('time_unit', 'unknown')}")
            for escalation in result.get('escalations', []):
                logger.info(f"   - {escalation['old_priority']} → {escalation['new_priority']} (age: {escalation['age_amount']})")
        else:
            logger.info("ℹ️  No items needed escalation")
            
    except Exception as e:
        logger.error(f"❌ Escalation job failed: {str(e)}", exc_info=True)


def maintenance_reminder_job():
    """Background job that sends maintenance reminders (7/3/1 days before)"""
    try:
        from app.tasks.notification_tasks import send_scheduled_maintenance_reminders
        
        logger.info(f"[{datetime.now()}] 🔔 Running maintenance reminder check...")
        result = send_scheduled_maintenance_reminders()
        
        reminders_sent = result.get('reminders_sent', 0) if result else 0
        
        if reminders_sent > 0:
            logger.info(f"✅ Maintenance reminders sent: {reminders_sent} notification(s)")
        else:
            logger.info("ℹ️  No maintenance reminders needed at this time")
            
    except Exception as e:
        logger.error(f"❌ Maintenance reminder job failed: {str(e)}", exc_info=True)


def start_scheduler():
    """Start the background scheduler for escalation checks"""
    if scheduler.running:
        logger.warning("Scheduler already running")
        return
    
    try:
        # Get configuration for interval
        from app.core.config import settings
        
        # Check every minute (you can adjust this)
        # In production, you might check every hour or every 30 minutes
        interval_minutes = 1
        
        logger.info(f"Starting scheduler: checking escalations every {interval_minutes} minute(s)")
        logger.info(f"Current escalation mode: {settings.ESCALATION_TIME_UNIT} (thresholds: {settings.ESCALATE_LOW_TO_MED_DAYS} units)")
        
        scheduler.add_job(
            escalation_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='escalation_check',
            name='Automatic Escalation Check',
            replace_existing=True,
            misfire_grace_time=10
        )
        
        # Add maintenance reminder job (runs daily to check for 7/3/1 day reminders)
        scheduler.add_job(
            maintenance_reminder_job,
            trigger=IntervalTrigger(hours=24),
            id='maintenance_reminder_check',
            name='Maintenance Reminder Check',
            replace_existing=True,
            misfire_grace_time=10
        )
        
        scheduler.start()
        logger.info("✅ Scheduler started successfully")
        logger.info("   - Escalation check: every minute")
        logger.info("   - Maintenance reminders: daily (every 24 hours)")
        
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {str(e)}", exc_info=True)


def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("✅ Scheduler stopped")
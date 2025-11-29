from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def start_scheduler():
    """Start the background scheduler for automatic tasks"""
    try:
        # Add any scheduled jobs here
        # For example, checking for overdue maintenance tasks
        logger.info("Starting background scheduler...")
        scheduler.start()
        logger.info("Background scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

def stop_scheduler():
    """Stop the background scheduler"""
    try:
        logger.info("Stopping background scheduler...")
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
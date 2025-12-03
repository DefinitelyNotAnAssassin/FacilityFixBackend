"""
Celery task for automatic priority escalation

Scheduled to run daily via Celery Beat
"""

import logging
import asyncio
from celery import shared_task
from app.services.escalation_service import escalation_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def check_and_escalate_pending_items(self):
    """
    Celery task: Check and escalate pending items based on age
    
    Runs daily via Celery Beat scheduler
    Retries up to 3 times with exponential backoff on failure
    """
    try:
        logger.info("🔄 Celery task started: check_and_escalate_pending_items")
        
        # Run async escalation check
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(escalation_service.check_and_escalate_all())
        
        logger.info(f"✅ Escalation task completed: {result}")
        return result
    
    except Exception as exc:
        logger.error(f"❌ Escalation task failed: {str(exc)}")
        
        # Retry with exponential backoff (60s, 120s, 240s)
        retry_countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_countdown)

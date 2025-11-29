import logging
from datetime import datetime
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task
def cleanup_expired_password_reset_otps():
    """
    Clean up expired password reset OTPs.
    Deletes OTPs that are expired and unused.
    """
    try:
        logger.info("Starting cleanup of expired password reset OTPs")

        # Query for expired and unused OTPs
        success, otps, error = await database_service.query_documents(
            COLLECTIONS["password_reset_otps"],
            [
                ("expires_at", "<", datetime.utcnow()),
                ("used", "==", False)
            ]
        )

        if not success:
            logger.error(f"Failed to query expired OTPs: {error}")
            return

        deleted_count = 0
        for otp in otps:
            delete_success, delete_error = await database_service.delete_document(
                COLLECTIONS["password_reset_otps"],
                otp["_doc_id"]
            )
            if delete_success:
                deleted_count += 1
            else:
                logger.warning(f"Failed to delete OTP {otp['_doc_id']}: {delete_error}")

        logger.info(f"Cleaned up {deleted_count} expired password reset OTPs")

    except Exception as e:
        logger.error(f"Error during OTP cleanup: {str(e)}")
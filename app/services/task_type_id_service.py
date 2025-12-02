from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TaskTypeIDService:
    """Generate and manage formatted TaskType IDs (TT-YYYY-XXXXX)"""
    async def generate_task_type_id(self) -> str:
        current_year = datetime.utcnow().year
        counter_id = f"task_type_counter_{current_year}"

        # Try to get the counter document
        success, counter_data, error = await database_service.get_document(
            COLLECTIONS['counters'],
            counter_id,
        )

        if not success or not counter_data:
            # Counter doesn't exist, create it starting from 1
            counter_data = {
                "year": current_year,
                "counter": 1,
                "last_updated": datetime.utcnow(),
            }
            create_success, _, create_error = await database_service.create_document(
                COLLECTIONS['counters'],
                counter_data,
                counter_id,
                validate=False,  # internal counter doc, skip validation
            )

            if not create_success:
                logger.error(f"Failed to create task type counter: {create_error}")
                raise Exception(f"Failed to create task type counter: {create_error}")

            next_number = 1
        else:
            # Atomically increment the counter (best-effort: not transactional here)
            current_counter = counter_data.get("counter", 0)
            next_number = current_counter + 1

            update_success, update_error = await database_service.update_document(
                COLLECTIONS['counters'],
                counter_id,
                {
                    "counter": next_number,
                    "last_updated": datetime.utcnow()
                },
                validate=False  # Skip validation for internal counter collection
            )

            if not update_success:
                logger.error(f"Failed to increment task type counter: {update_error}")
                raise Exception(f"Failed to increment task type counter: {update_error}")

        formatted_id = f"TT-{current_year}-{next_number:05d}"
        logger.info(f"Generated unique task type ID: {formatted_id}")
        return formatted_id

    async def get_current_counter(self, year: int = None) -> int:
        if year is None:
            year = datetime.utcnow().year
        counter_id = f"task_type_counter_{year}"
        success, counter_data, error = await database_service.get_document(COLLECTIONS['counters'], counter_id)
        if not success or not counter_data:
            return 0
        return counter_data.get('counter', 0)

    async def verify_id_uniqueness(self, formatted_id: str) -> bool:
        success, results, error = await database_service.query_documents(
            COLLECTIONS['task_types'],
            [("formatted_id", "==", formatted_id)]
        )
        if not success:
            logger.error(f"Failed to verify ID uniqueness: {error}")
            return False
        return len(results) == 0


task_type_id_service = TaskTypeIDService()

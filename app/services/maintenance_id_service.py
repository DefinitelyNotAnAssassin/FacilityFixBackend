from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class MaintenanceIdService:
    @staticmethod
    async def generate_maintenance_id(maintenance_type: Optional[str] = None) -> str:
        """
        Generate next available maintenance ID in format: MT-YYYY-NNNNN
        Example: MT-2025-00001, MT-2025-00002, etc.

        Uses a counters collection to store per-year counters. This implementation
        reads the counter doc for the current year and increments it. It keeps
        operations simple and relies on the underlying `database_service` to
        provide atomic update semantics if available.
        """
        current_year = datetime.utcnow().year
        counter_id = f"maintenance_counter_{current_year}"

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
                logger.error(f"Failed to create maintenance counter: {create_error}")
                raise Exception(f"Failed to create maintenance counter: {create_error}")

            next_number = 1
        else:
            # Atomically increment the counter
            current_counter = counter_data.get("counter", 0)
            next_number = current_counter + 1

            # Update with the new counter value
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
                logger.error(f"Failed to increment maintenance counter: {update_error}")
                raise Exception(f"Failed to increment maintenance counter: {update_error}")

        # Choose prefix based on maintenance type
        prefix = "MT"
        if maintenance_type:
            mt = str(maintenance_type).lower()
            if "external" in mt or mt == "epm":
                prefix = "EPM"
            elif "internal" in mt or mt == "ipm":
                prefix = "IPM"

        # Generate formatted ID: PREFIX-YYYY-NNNNN (5 digits with leading zeros)
        formatted_id = f"{prefix}-{current_year}-{next_number:05d}"
        logger.info(f"Generated unique maintenance ID: {formatted_id}")

        return formatted_id

    @staticmethod
    async def get_current_counter(year: int = None) -> int:
        """Get the current counter value for a specific year"""
        if year is None:
            year = datetime.utcnow().year

        counter_id = f"maintenance_counter_{year}"
        success, counter_data, error = await database_service.get_document(
            COLLECTIONS['counters'],
            counter_id
        )

        if not success or not counter_data:
            return 0

        return counter_data.get("counter", 0)

    @staticmethod
    async def verify_id_uniqueness(formatted_id: str) -> bool:
        """
        Verify that a formatted ID is unique in the maintenance_tasks collection
        """
        success, results, error = await database_service.query_documents(
            COLLECTIONS['maintenance_tasks'],
            [("formatted_id", "==", formatted_id)]
        )

        if not success:
            logger.error(f"Failed to verify ID uniqueness: {error}")
            return False

        # ID is unique if no results found
        return len(results) == 0


maintenance_id_service = MaintenanceIdService()

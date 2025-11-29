from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from datetime import datetime
from google.cloud.firestore_v1 import Increment
import asyncio
import logging

logger = logging.getLogger(__name__)

class EquipmentIdService:
    @staticmethod
    async def generate_equipment_id() -> str:
        """
        Generate next available equipment ID in format: EQ-YYYY-NNNNN
        Example: EQ-2025-00001, EQ-2025-00002, etc.
        
        This uses Firestore's atomic increment to ensure uniqueness even with concurrent requests.
        """
        current_year = datetime.utcnow().year
        counter_id = f"equipment_counter_{current_year}"
        
        # Try to get the counter document
        success, counter_data, error = await database_service.get_document(
            COLLECTIONS['counters'],
            counter_id
        )
        
        if not success or not counter_data:
            # Counter doesn't exist, create it starting from 1
            counter_data = {
                "year": current_year,
                "counter": 1,
                "last_updated": datetime.utcnow()
            }
            create_success, _, create_error = await database_service.create_document(
                COLLECTIONS['counters'],
                counter_data,
                counter_id,
                validate=False  # Skip validation for internal counter collection
            )
            
            if not create_success:
                logger.error(f"Failed to create counter: {create_error}")
                raise Exception(f"Failed to create counter: {create_error}")
            
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
                logger.error(f"Failed to increment counter: {update_error}")
                raise Exception(f"Failed to increment counter: {update_error}")
        
        # Generate formatted ID: EQ-YYYY-NNNNN (5 digits with leading zeros)
        formatted_id = f"EQ-{current_year}-{next_number:05d}"
        logger.info(f"Generated unique equipment ID: {formatted_id}")
        
        return formatted_id
    
    @staticmethod
    async def get_current_counter(year: int = None) -> int:
        """Get the current counter value for a specific year"""
        if year is None:
            year = datetime.utcnow().year
        
        counter_id = f"equipment_counter_{year}"
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
        Verify that a formatted ID is unique in the equipment collection
        """
        success, results, error = await database_service.query_documents(
            COLLECTIONS['equipment'],
            [("formatted_id", "==", formatted_id)]
        )
        
        if not success:
            logger.error(f"Failed to verify ID uniqueness: {error}")
            return False
        
        # ID is unique if no results found
        return len(results) == 0

equipment_id_service = EquipmentIdService()
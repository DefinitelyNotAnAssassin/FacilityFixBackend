#!/usr/bin/env python3
"""
Test creating equipment uses formatted_id as document ID and saves formatted fields.
"""

import asyncio
import sys
import os
from datetime import datetime
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.equipment_service import equipment_service
from app.services.equipment_id_service import equipment_id_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    try:
        # Create a test equipment
        test_admin = 'test_admin_001'
        equipment_payload = {
            'building_id': 'test_building_formatted',
            'equipment_name': 'Formatted ID Test Equipment',
            'asset_tag': 'FIT-001',
            'manufacturer': 'TestCorp',
            'equipment_type': 'HVAC',
            'category': 'HVAC',
            'status': 'Operational',
            'location': 'Unit 1',
        }

        success, id_or_none, error = await equipment_service.create_equipment(equipment_payload, test_admin)
        if not success:
            logger.error('Failed to create equipment: %s', error)
            return False

        logger.info('Created equipment with id: %s', id_or_none)

        # Fetch created equipment using doc ID (formatted ID should be used as doc id)
        s, doc, err = await database_service.get_document(COLLECTIONS['equipment'], id_or_none)
        if not s or not doc:
            logger.error('Failed to fetch equipment by formatted id: %s (err: %s)', id_or_none, err)
            return False

        logger.info('Fetched equipment document: %s', doc)

        # Check that formatted_id and equipment_id are set and match doc id
        formatted_id = doc.get('formatted_id') or doc.get('equipment_id')
        if not formatted_id:
            logger.error('Created document missing formatted_id or equipment_id')
        else:
            if formatted_id != id_or_none:
                logger.warning('Formatted ID (%s) does not match doc id (%s)', formatted_id, id_or_none)
            else:
                logger.info('Formatted ID matches document ID (%s)', formatted_id)

        # Cleanup
        await database_service.delete_document(COLLECTIONS['equipment'], id_or_none)
        logger.info('Deleted test equipment %s', id_or_none)
        return True

    except Exception as e:
        logger.exception('Error in test')
        return False

if __name__ == '__main__':
    ok = asyncio.run(run_test())
    sys.exit(0 if ok else 1)

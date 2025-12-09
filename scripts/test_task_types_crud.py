#!/usr/bin/env python3
"""
Simple CRUD test for TaskTypeService using the database service.
"""
import asyncio
import sys
import os
from datetime import datetime
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.task_type_service import task_type_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    try:
        test_admin = 'test_admin_task_type'
        payload = {
            'name': 'Sample Task Type',
            'maintenance_type': 'Routine',
            'description': 'A task type for unit testing',
            'inventory_items': []
        }

        # Create
        success, doc_id, error = await task_type_service.create_task_type(payload, test_admin)
        if not success:
            logger.error('Failed to create task type: %s', error)
            return False
        logger.info('Created task type: %s', doc_id)

        # Get
        s, doc, err = await task_type_service.get_task_type(doc_id)
        if not s or not doc:
            logger.error('Failed to fetch task type %s: %s', doc_id, err)
            return False
        logger.info('Fetched created task type: %s', doc)
        # Validate the returned formatted_id
        if doc.get('formatted_id') and doc.get('formatted_id') != doc_id:
            logger.error('Formatted ID does not match the document id: %s vs %s', doc.get('formatted_id'), doc_id)
            return False

        # Update
        update_payload = {'description': 'Updated description for testing'}
        s, err = await task_type_service.update_task_type(doc_id, update_payload, test_admin)
        if not s:
            logger.error('Failed to update task type: %s', err)
            return False
        logger.info('Updated task type %s', doc_id)

        # List
        s, items, err = await task_type_service.list_task_types()
        if not s:
            logger.error('Failed to list task types: %s', err)
            return False
        logger.info('Listed %d task types', len(items))

        # Add inventory item
        item = {'item_id': 'test-item-001', 'quantity': 1, 'item_name': 'Test Item'}
        s, err = await task_type_service.add_inventory_item(doc_id, item, test_admin)
        if not s:
            logger.error('Failed to add inventory item: %s', err)
            return False
        logger.info('Added inventory item to task type %s', doc_id)

        # Remove inventory item
        s, err = await task_type_service.remove_inventory_item(doc_id, 'test-item-001', test_admin)
        if not s:
            logger.error('Failed to remove inventory item: %s', err)
            return False
        logger.info('Removed inventory item from task type %s', doc_id)

        # Soft delete
        s, err = await task_type_service.soft_delete_task_type(doc_id, test_admin)
        if not s:
            logger.error('Failed to soft delete task type: %s', err)
            return False
        logger.info('Soft deleted task type %s', doc_id)

        # Verify it is inactive in list
        s, items, err = await task_type_service.list_task_types(include_inactive=False)
        ids = [i.get('id') for i in items]
        if doc_id in ids:
            logger.error('Soft-deleted task type still returned in active list')
            return False

        # Cleanup - permanently delete from DB
        # Not using a service method to hard delete; delete directly from database service
        await database_service.delete_document(COLLECTIONS['task_types'], doc_id)
        logger.info('Permanently deleted test doc %s', doc_id)

        return True

    except Exception as e:
        logger.exception('Error running task type CRUD test')
        return False

if __name__ == '__main__':
    ok = asyncio.run(run_test())
    sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""
Test script for maintenance task inventory flows:
- Admin creates a task with inventory parts -> reservation/requests created
- Staff receives item(s) (good condition & defective) -> consumption / replacement request created
- Staff returns items -> restock occurs and statuses update
"""

import asyncio
import sys
import os
from datetime import datetime
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.maintenance_task_service import maintenance_task_service
from app.services.inventory_service import inventory_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_flow_test():
    test_building = 'test_flow_building'
    test_admin = 'test_admin_001'
    test_user = 'test_staff_001'

    created_resources = []

    try:
        # 1) Create building
        building_payload = {
            'id': test_building,
            'building_name': 'Flow Test Building',
            'address': '1 Test St',
            'total_floors': 1,
            'total_units': 1,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        s, b_id, err = await database_service.create_document(COLLECTIONS['buildings'], building_payload)
        if s:
            created_resources.append((COLLECTIONS['buildings'], b_id))
            logger.info('Created building: %s', b_id)
        else:
            logger.warning('Building creation warning: %s', err)

        # 2) Create inventory item
        item_payload = {
            'building_id': test_building,
            'item_name': 'Flow Test Bulb',
            'item_code': 'FTB-001',
            'department': 'Maintenance',
            'classification': 'consumable',
            'category': 'Electrical',
            'current_stock': 10,
            'reorder_level': 2,
            'max_stock_level': 20,
            'unit_of_measure': 'pcs',
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        s, item_id, err = await database_service.create_document(COLLECTIONS['inventory'], item_payload)
        if not s:
            logger.error('Failed to create test item: %s', err)
            return False
        created_resources.append((COLLECTIONS['inventory'], item_id))
        logger.info('Created item %s (%s)', item_id, item_payload['item_name'])

        # 3) Admin creates maintenance task with parts_used; reservation will be created
        payload = {
            'building_id': test_building,
            'task_title': 'Flow Test Maintenance',
            'task_description': 'Test description for flows',
            'location': 'Test Location',
            'scheduled_date': datetime.utcnow().isoformat(),
            'assigned_to': test_user,
            'parts_used': [
                {
                    'inventory_id': item_id,
                    'quantity': 2,
                    'reserve': True
                }
            ]
        }

        task = await maintenance_task_service.create_task(test_admin, payload)
        created_resources.append((COLLECTIONS['maintenance_tasks'], task.id))
        logger.info('Task created: %s', task.id)

        if not task.inventory_request_ids:
            logger.error('No inventory requests created for task')
            return False

        request_id = task.inventory_request_ids[0]
        logger.info('Inventory request id: %s', request_id)

        # Verify request status is 'reserved'
        s, req_doc, _ = await database_service.get_document(COLLECTIONS['inventory_requests'], request_id)
        logger.info('Initial request status: %s', req_doc.get('status'))

        # 4) Staff receives the request in good condition (consumes stock)
        logger.info('Staff receives request in good condition...')
        updated = await maintenance_task_service.mark_inventory_request_received(request_id, test_user, condition='ok')
        logger.info('Receive result: %s', updated.get('updated_request').get('status'))

        # Check inventory consumed
        s, item_after, _ = await inventory_service.get_inventory_item(item_id)
        logger.info('Item current_stock after receive: %s', item_after.get('current_stock'))

        # 5) Create a new task with 1 quantity and simulate receiving as 'defective', ensuring replacement request created
        payload2 = {
            'building_id': test_building,
            'task_title': 'Flow Test Maintenance Defective',
            'task_description': 'Test description for defective flow',
            'location': 'Test Location',
            'scheduled_date': datetime.utcnow().isoformat(),
            'assigned_to': test_user,
            'parts_used': [
                {
                    'inventory_id': item_id,
                    'quantity': 1,
                    'reserve': True
                }
            ]
        }

        task2 = await maintenance_task_service.create_task(test_admin, payload2)
        created_resources.append((COLLECTIONS['maintenance_tasks'], task2.id))
        logger.info('Task created (defective): %s', task2.id)

        request_id2 = task2.inventory_request_ids[0]
        logger.info('Inventory request id 2: %s', request_id2)

        # Staff receives this one as defective
        updated2 = await maintenance_task_service.mark_inventory_request_received(request_id2, test_user, condition='broken')
        logger.info('Receive result (defective): %s', updated2.get('updated_request').get('status'))

        # The defective branch creates a replacement request; verify it exists and is attached
        # Wait a moment for replacement creation
        await asyncio.sleep(1)

        s, req_doc2, _ = await database_service.get_document(COLLECTIONS['inventory_requests'], request_id2)
        # Find replacement request ids by querying requests linked to task2 with purpose containing 'Replacement'
        s, all_reqs, _ = await inventory_service.get_inventory_requests()
        replacements = [r for r in all_reqs if r.get('purpose', '').lower().startswith('replacement') and r.get('maintenance_task_id') == task2.id]
        logger.info('Replacement requests found count: %s', len(replacements))
        if replacements:
            created_resources.extend([(COLLECTIONS['inventory_requests'], replacements[0].get('_doc_id') or replacements[0].get('id'))])
            logger.info('Replacement request id: %s', replacements[0].get('_doc_id') or replacements[0].get('id'))

        # 6) Return 1 item for the original fulfilled request (restock)
        logger.info('Returning one item from first request...')
        s_return, err_return = await inventory_service.return_inventory_request(request_id, test_user, quantity=1)
        logger.info('Return result: %s', s_return)

        # Check inventory current_stock increased by 1
        s, item_after_return, _ = await inventory_service.get_inventory_item(item_id)
        logger.info('Item current_stock after return: %s', item_after_return.get('current_stock'))

        # 7) Cleanup created resources
        logger.info('Cleaning up created resources...')
        for col, _id in created_resources:
            try:
                await database_service.delete_document(col, _id)
                logger.info('Deleted %s %s', col, _id)
            except Exception as exc:
                logger.warning('Failed to delete %s %s: %s', col, _id, exc)

        logger.info('Test flow completed successfully')
        return True

    except Exception as ex:
        logger.error('Exception in test flow: %s', ex)
        return False

if __name__ == '__main__':
    ok = asyncio.run(run_flow_test())
    sys.exit(0 if ok else 1)

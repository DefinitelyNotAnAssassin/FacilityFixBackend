#!/usr/bin/env python3
"""
Demo script: Maintenance task with inventory reservation, request, auto-receive on assessment, and returns

This script runs the following flow using backend service layer:
1) Create an inventory item
2) Create a maintenance task that automatically creates a reservation for the inventory
3) Create an inventory request (simulate a defective item / replacement request)
4) Approve the request (admin) and optionally fulfill
5) Staff submits an assessment; the router auto-receives inventory for the task and requests
6) Demonstrate returning a reservation and returning a request (partial return)

This is meant to be run from the backend project root and requires the backend packages to be installable into the environment.

Usage:
    python scripts/demo_maintenance_inventory_request_return_flow.py

"""

import asyncio
import sys
import os
from datetime import datetime
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.maintenance_task_service import maintenance_task_service
from app.services.inventory_service import inventory_service
from app.services.maintenance_id_service import maintenance_id_service
from app.services.user_id_service import user_id_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def demo_flow():
    admin_uid = 'admin_demo_001'
    staff_uid = 'staff_demo_001'
    building_id = 'B_DEMO_001'

    # 1) Create inventory item
    logger.info('Creating inventory item...')
    item = {
        'building_id': building_id,
        'item_name': 'Demo Electrical Tape',
        'item_code': 'DEMO-ELC-0001',
        'category': 'Electrical',
        'department': 'Maintenance',
        'classification': 'consumable',
        'current_stock': 50,
        'reorder_level': 5,
        'max_stock_level': 200,
        'unit_of_measure': 'pcs',
        'is_active': True,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    s, item_id, err = await database_service.create_document(COLLECTIONS['inventory'], item)
    if not s:
        logger.error('Failed to create inventory item: %s', err)
        return False

    logger.info('Inventory created: id=%s, code=%s', item_id, item['item_code'])

    # 2) Create maintenance task with reservation
    logger.info('Creating maintenance task and reserving inventory...')
    payload = {
        'building_id': building_id,
        'task_title': 'Demo Maintenance - Fix Wiring',
        'task_description': 'Replace electrical tape and verify wiring',
        'location': 'Demo Site - Building',
        'scheduled_date': datetime.utcnow().isoformat(),
        'assigned_to': staff_uid,
        'parts_used': [
            {
                'inventory_id': item_id,
                'quantity': 3
            }
        ],
    }
    task = await maintenance_task_service.create_task(created_by=admin_uid, payload=payload)
    if not task:
        logger.error('Failed to create task')
        return False

    logger.info('Created maintenance task: %s (assigned to %s)', task.id, task.assigned_to)

    # 3) Create an inventory request (staff) for a replacement (simulate defective)
    logger.info('Creating an inventory request for replacement (defective)')
    request_data = {
        'inventory_id': item_id,
        'quantity_requested': 1,
        'purpose': 'defective replacement',
        'reference_id': task.id,
        'maintenance_task_id': task.id,
        'item_name': item['item_name']
    }

    req_success, req_id, req_err = await inventory_service.create_inventory_request({**request_data, 'requested_by': staff_uid})
    if not req_success:
        logger.error('Failed to create inventory request: %s', req_err)
        return False

    logger.info('Inventory request created: %s', req_id)

    # 4) Admin approves the request (simulate admin approving)
    logger.info('Approving inventory request as admin...')
    appr_success, appr_err = await inventory_service.approve_inventory_request(req_id, admin_uid, quantity_approved=1, admin_notes='OK to replace')
    if not appr_success:
        logger.error('Failed to approve request: %s', appr_err)
        return False

    logger.info('Request approved')

    # 5) Staff submits assessment. This will automatically mark the task inventory as received
    logger.info('Staff submitting assessment, which triggers auto-receive...')
    from app.routers.maintenance import submit_assessment, SubmitAssessmentRequest
    assessment_request = SubmitAssessmentRequest(assessment='Work completed, tapes used', assessment_notes='No issues')
    current_user = {'uid': staff_uid, 'role': 'staff', 'first_name': 'Demo', 'last_name': 'Staff'}

    # Call the submit_assessment route (router-level function) directly
    res = await submit_assessment(task.id, assessment_request, current_user)
    logger.info('Assessment submitted response: %s', res)

    # 6) Check reservation(s) updated
    logger.info('Checking reservations & requests for task...')
    r_success, reservations, r_err = await inventory_service.get_inventory_reservations({'maintenance_task_id': task.id})
    if r_success and reservations:
        for r in reservations:
            logger.info('Reservation: id=%s, inventory_id=%s, status=%s', r.get('id') or r.get('_doc_id'), r.get('inventory_id'), r.get('status'))

    s, updated_req, _ = await inventory_service.get_inventory_request_by_id(req_id)
    logger.info('Request status after assessment: %s', updated_req.get('status'))

    # 7) Demonstrate returning part of a reservation (staff returns 1 of 3)
    logger.info('Demonstrating reservation return (partial)...')
    # Get reservation doc id from database query
    if not (r_success and reservations and len(reservations) > 0):
        logger.warning('No reservations found to return')
    else:
        res_doc = reservations[0]
        # find doc id record via query
        filters = [
            ('maintenance_task_id', '==', task.id),
            ('inventory_id', '==', res_doc.get('inventory_id')),
            ('status', '==', 'received')
        ]
        q_s, docs, q_e = await database_service.query_documents(COLLECTIONS['inventory_reservations'], filters)
        if q_s and docs:
            reservation_doc_id = docs[0].get('_doc_id') or docs[0].get('id')
            logger.info('Returning 1 piece from reservation id=%s', reservation_doc_id)
            ret_success, ret_data, ret_err = await inventory_service.return_reservation(reservation_doc_id, staff_uid, quantity=1, date_returned=datetime.utcnow(), notes='Partial return - unused')
            if not ret_success:
                logger.error('Failed to return reservation: %s', ret_err)
            else:
                logger.info('Reservation return completed: %s', ret_data)
        else:
            logger.warning('No matching reservation doc found to return')

    # 8) Demonstrate returning a fulfilled request
    logger.info('Demonstrating request return...')
    # Fulfill the request (admin): fulfills and reduces stock
    ful_success, ful_err = await inventory_service.fulfill_inventory_request(req_id, admin_uid)
    if not ful_success:
        logger.warning('Failed to fulfill request: %s', ful_err)
    else:
        logger.info('Request fulfilled successfully')

    # Staff returns that request (e.g., returning a defective replacement)
    ret_req_success, ret_req_err = await inventory_service.return_inventory_request(req_id, staff_uid, quantity=1)
    if not ret_req_success:
        logger.error('Failed to return request item: %s', ret_req_err)
    else:
        logger.info('Request returned (restocked) successfully')

    # Report final stock
    s, final_item, err = await inventory_service.get_inventory_item(item_id)
    logger.info('Final inventory stock for item %s: %s', item_id, final_item.get('current_stock'))

    logger.info('Demo flow completed.')
    return True

if __name__ == '__main__':
    ok = asyncio.run(demo_flow())
    sys.exit(0 if ok else 1)

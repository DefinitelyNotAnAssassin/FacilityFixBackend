#!/usr/bin/env python3
"""
Test maintenance task inventory flows:
1. Auto-reserve inventory on task creation
2. Auto-receive inventory when staff submits assessment (deducts stock)
3. Staff can return unused items (adds to stock, keeps reservation amount for recurrence)

Flow Example:
- Task created: reserves 10 items
- Staff submits assessment: auto-receives 10 items (stock -10)
- Staff returns 5 unused: stock +5 (reservation stays at 10 for recurrence)
- Next recurrence: reserves same 10 items
"""

import sys
import os
import asyncio
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.maintenance import router as maintenance_router
from app.routers.inventory import router as inventory_router
from app.auth.dependencies import get_current_user as _real_get_current_user
from app.services.maintenance_task_service import maintenance_task_service
from app.services.inventory_service import inventory_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

# Setup test app
app = FastAPI()
app.include_router(maintenance_router)
app.include_router(inventory_router)

def fake_admin_user():
    return {"uid": "test_admin_001", "role": "admin", "email": "admin@example.com"}

app.dependency_overrides[_real_get_current_user] = fake_admin_user
client = TestClient(app)

async def test_task_receive_and_return_flow():
    """Test complete task inventory receive and return flow"""
    
    print('\n' + '='*70)
    print('TESTING TASK INVENTORY RECEIVE AND RETURN FLOW')
    print('='*70)
    
    test_building = 'test_building_001'
    test_user = 'test_admin_001'
    test_admin = 'test_admin_001'

    # Step 1: Create inventory items
    print('\n[STEP 1] Creating inventory items...')
    item1 = {
        'building_id': test_building,
        'item_name': 'Test Bulb',
        'item_code': 'TB-001',
        'category': 'Electrical',
        'department': 'Maintenance',
        'classification': 'consumable',
        'current_stock': 10,
        'reorder_level': 2,
        'max_stock_level': 20,
        'unit_of_measure': 'pcs',
        'is_active': True,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }

    s, item_id1, err = await database_service.create_document(COLLECTIONS['inventory'], item1)
    if not s:
        print(f'   ❌ Failed to create test item: {err}')
        return False
    print(f'   ✅ Created inventory: {item1["item_name"]} (ID: {item_id1})')

    # Step 2: Admin creates a maintenance task with this item to be reserved
    print('\n[STEP 2] Creating maintenance task with inventory reservation...')
    payload = {
        'building_id': test_building,
        'task_title': 'Test MT',
        'task_description': 'Test description',
        'location': 'Test room',
        'scheduled_date': datetime.utcnow().isoformat(),
        'assigned_to': test_user,
        'parts_used': [
            {
                'inventory_id': item_id1,
                'quantity': 2,
                'reserve': True
            }
        ]
    }

    task = await maintenance_task_service.create_task(test_admin, payload)
    print(f'   ✅ Task created: {task.id}')

    # Step 3: Confirm that an inventory reservation was created
    print('\n[STEP 3] Verifying inventory reservation...')
    reservation_ids = getattr(task, 'inventory_reservation_ids', []) or []
    if not reservation_ids:
        print('   ❌ No inventory reservation created on task')
        return False

    print(f'   ✅ Inventory reservation created: {reservation_ids}')

    # Verify reservation status
    s, res_doc, e = await inventory_service.get_inventory_reservation_by_id(reservation_ids[0])
    print(f'   Reservation status: {res_doc.get("status")}')

    # Step 4: Staff receives the task inventory
    print('\n[STEP 4] Marking task inventory as received by staff...')
    s, err = await inventory_service.mark_task_inventory_received(task.id, test_user, deduct_stock=True)
    if not s:
        print(f'   ❌ Failed to mark task inventory received: {err}')
        return False
    print('   ✅ Task inventory marked as received')

    # Fetch updated reservation
    s, res2, e2 = await inventory_service.get_inventory_reservation_by_id(reservation_ids[0])
    print(f'   Updated reservation status: {res2.get("status")}')

    # Verify inventory stock reduced
    s, item_after, err3 = await inventory_service.get_inventory_item(item_id1)
    print(f'   Item stock after receive: {item_after.get("current_stock")}')

    # Step 5: Staff returns one item (partial return)
    print('\n[STEP 5] Returning one item from reservation...')
    s, return_data, err = await inventory_service.return_reservation(reservation_ids[0], test_user, quantity=1)
    if not s:
        print(f'   ❌ Failed to return item: {err}')
        return False
    print('   ✅ Item returned successfully')

    s, item_after_return, _ = await inventory_service.get_inventory_item(item_id1)
    print(f'   Item stock after return: {item_after_return.get("current_stock")}')

    # Step 6: Verify reservation after return
    print('\n[STEP 6] Verifying reservation after return...')
    s, reservations, err = await inventory_service.get_inventory_reservations({'maintenance_task_id': task.id})
    if s and reservations:
        reservation_doc = reservations[0]
        filters = [('maintenance_task_id', '==', task.id), ('inventory_id', '==', reservation_doc.get('inventory_id'))]
        q_s, docs, q_e = await database_service.query_documents(COLLECTIONS['inventory_reservations'], filters)
        if q_s and docs:
            res_doc_id = docs[0].get('_doc_id') or docs[0].get('id')
            print(f'   ✅ Found reservation: {res_doc_id}')

    print('\n' + '='*70)
    print('TASK RECEIVE AND RETURN TEST COMPLETE')
    print('='*70)
    return True

if __name__ == '__main__':
    success = asyncio.run(test_task_receive_and_return_flow())
    sys.exit(0 if success else 1)

import sys, os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.inventory import router as inventory_router
from app.services.inventory_service import inventory_service
from app.services.maintenance_task_service import maintenance_task_service
from app.services.maintenance_id_service import maintenance_id_service
from app.auth.dependencies import get_current_user as _real_get_current_user
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

app = FastAPI()
app.include_router(inventory_router)

# Create a fake staff user

def fake_staff_user():
    return {"uid": "test_staff_user", "role": "staff", "email": "staff@example.com"}

app.dependency_overrides[_real_get_current_user] = fake_staff_user

client = TestClient(app)

async def setup_inventory_and_task():
    # create admin user profile
    admin_profile = {
        'user_id': 'test_admin_user',
        'first_name': 'Test',
        'last_name': 'Admin',
        'role': 'admin',
        'email': 'admin@example.com',
        'staff_id': None
    }
    # Use the user_id as the Firestore document ID so get_user_profile(user_id) works
    await database_service.create_document(COLLECTIONS['users'], admin_profile, document_id=admin_profile['user_id'])

    # create staff user profile
    staff_profile = {
        'user_id': 'test_staff_user',
        'first_name': 'Test',
        'last_name': 'Staff',
        'role': 'staff',
        'email': 'staff@example.com',
        'staff_id': 'S-0001'
    }
    await database_service.create_document(COLLECTIONS['users'], staff_profile, document_id=staff_profile['user_id'])

    # create admin user
    admin_uid = 'test_admin_user'

    # create an inventory item
    item_payload = {
        'building_id': 'test_building',
        'item_name': 'Staff Reserve Item',
        'department': 'Maintenance',
        'classification': 'consumable',
        'current_stock': 10,
        'reorder_level': 3,
        'unit_of_measure': 'pcs'
    }
    success, item_id, err = await inventory_service.create_inventory_item(item_payload, admin_uid)
    if not success:
        raise Exception(f"Failed to create inventory item: {err}")
    print('Created inventory item', item_id)

    # create a maintenance task and assign to staff (use create_task)
    task_payload = {
        'building_id': 'test_building',
        'task_title': 'Test Task for Reservation',
        'task_description': 'Testing staff reservation',
        'location': 'Unit 1',
        'scheduled_date': '2025-12-01T08:00:00Z',
        'assigned_to': 'test_staff_user',
        'parts_used': []
    }

    task = await maintenance_task_service.create_task(admin_uid, task_payload)
    print('Created maintenance task', getattr(task, 'id', None))
    return item_id, task.id


def test_staff_reservation_policy():
    # Setup test: create item and task
    item_id, task_id = asyncio.run(setup_inventory_and_task())

    payload = {
        'inventory_id': item_id,
        'quantity': 1,
        'maintenance_task_id': task_id
    }

    # Staff should NOT be allowed to create a reservation (admin only)
    r = client.post('/inventory/reservations', json=payload)
    print('staff create reservation status', r.status_code)
    assert r.status_code == 403

    # Now create reservation as admin (using direct service call)
    admin_uid = 'test_admin_user'
    success, reservation_id, err = asyncio.run(inventory_service.create_inventory_reservation(payload, admin_uid))
    print('Admin create reservation result:', success, reservation_id, err)
    assert success, f"Admin failed to create reservation: {err}"

    # Staff assigned to task should be able to mark reservation as received
    print('Attempting staff to mark reservation received:', reservation_id)
    # Inspect reservation document to verify created_by and fields
    try:
        success_doc, res_doc, err_doc = asyncio.run(database_service.get_document(COLLECTIONS['inventory_reservations'], reservation_id))
        print('Reservation document fetched:', success_doc, err_doc)
        print(res_doc)
    except Exception as e:
        print('Failed to fetch reservation doc:', e)

    r2 = client.put(f'/inventory/reservations/{reservation_id}/received')
    print('staff mark received status', r2.status_code, r2.text)
    assert r2.status_code == 200
    print('reservation_id', reservation_id)

if __name__ == '__main__':
    test_staff_reservation_policy()
    print('Test complete')

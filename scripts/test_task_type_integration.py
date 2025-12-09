"""
Test script to verify task type integration with maintenance tasks
"""
import sys, os
import asyncio
import json
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.maintenance import router as maintenance_router
from app.routers.task_types import router as task_types_router
from app.services.task_type_service import task_type_service
from app.services.inventory_service import inventory_service
from app.auth.dependencies import get_current_user as _real_get_current_user
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

# ============================================================================
# Setup Test App
# ============================================================================

app = FastAPI()
app.include_router(maintenance_router)
app.include_router(task_types_router)

def fake_admin_user():
    return {"uid": "test_admin_user", "role": "admin", "email": "admin@example.com"}

app.dependency_overrides[_real_get_current_user] = fake_admin_user
client = TestClient(app)

# ============================================================================
# Test Functions
# ============================================================================

async def setup_test_data():
    """Create test admin profile, inventory item, and task type"""
    
    # Create admin user profile
    admin_profile = {
        'user_id': 'test_admin_user',
        'first_name': 'Task Type',
        'last_name': 'Admin',
        'role': 'admin',
        'email': 'admin@tasktype.test',
        'department': 'Maintenance'
    }
    try:
        await database_service.create_document(
            COLLECTIONS['users'], 
            admin_profile, 
            document_id=admin_profile['user_id']
        )
        print('✅ Created admin user profile')
    except Exception as e:
        print(f'⚠️  Admin profile might exist: {e}')

    # Create inventory items for the task type
    wrench_item = {
        'building_id': 'test_building',
        'item_name': 'Adjustable Wrench',
        'department': 'Maintenance',
        'classification': 'tool',
        'current_stock': 20,
        'reorder_level': 5,
        'unit_of_measure': 'pcs'
    }
    
    screws_item = {
        'building_id': 'test_building',
        'item_name': 'Steel Screws Pack',
        'department': 'Maintenance',
        'classification': 'consumable',
        'current_stock': 50,
        'reorder_level': 10,
        'unit_of_measure': 'pack'
    }
    
    success1, wrench_id, _ = await inventory_service.create_inventory_item(wrench_item, 'test_admin_user')
    success2, screws_id, _ = await inventory_service.create_inventory_item(screws_item, 'test_admin_user')
    
    if success1 and success2:
        print(f'✅ Created inventory items: {wrench_id}, {screws_id}')
        return wrench_id, screws_id
    else:
        raise Exception('Failed to create inventory items')

def test_task_type_integration():
    """Test the complete task type integration workflow"""
    
    print('\\n' + '='*70)
    print('TESTING TASK TYPE INTEGRATION WITH MAINTENANCE TASKS')
    print('='*70 + '\\n')
    
    # Setup test data
    wrench_id, screws_id = asyncio.run(setup_test_data())
    
    # ========================================================================
    # Step 1: Create a task type with inventory items
    # ========================================================================
    print('[STEP 1] Creating task type with inventory items...')
    
    task_type_payload = {
        'name': 'Plumbing Repair',
        'description': 'Standard plumbing repair procedure',
        'maintenance_type': 'Corrective',
        'inventory_items': [
            {
                'inventory_id': wrench_id,
                'quantity': 1,
                'reserve': True
            },
            {
                'inventory_id': screws_id,
                'quantity': 2,
                'reserve': True
            }
        ]
    }
    
    r1 = client.post('/task-types/', json=task_type_payload)
    print(f'   Status: {r1.status_code}')
    
    if r1.status_code != 200:
        print(f'   ❌ FAILED: {r1.text}')
        return
    
    task_type_response = r1.json()
    task_type_id = task_type_response['task_type_id']
    print(f'   ✅ Created task type: {task_type_id}')
    
    # ========================================================================
    # Step 2: Test task types dropdown endpoint
    # ========================================================================
    print('\\n[STEP 2] Testing task types dropdown endpoint...')
    
    r2 = client.get('/maintenance/task-types')
    print(f'   Status: {r2.status_code}')
    
    if r2.status_code != 200:
        print(f'   ❌ FAILED: {r2.text}')
        return
    
    dropdown_response = r2.json()
    task_types = dropdown_response.get('data', [])
    
    print(f'   ✅ Found {len(task_types)} task types for dropdown')
    
    # Find our task type in the dropdown
    our_task_type = None
    for tt in task_types:
        if tt['id'] == task_type_id:
            our_task_type = tt
            break
    
    if our_task_type:
        print(f'   ✅ Found our task type in dropdown:')
        print(f'      Name: {our_task_type["name"]}')
        print(f'      Inventory items: {len(our_task_type["inventory_items"])}')
    else:
        print(f'   ❌ Our task type not found in dropdown')
        return
    
    # ========================================================================
    # Step 3: Create maintenance task with task type
    # ========================================================================
    print('\\n[STEP 3] Creating maintenance task with task type...')
    
    scheduled_date = datetime.utcnow() + timedelta(days=1)
    maintenance_payload = {
        'building_id': 'test_building',
        'task_title': 'Fix Kitchen Sink Leak',
        'task_description': 'Repair leaking faucet in unit kitchen',
        'location': 'Unit 101 - Kitchen',
        'scheduled_date': scheduled_date.isoformat() + 'Z',
        'task_type_id': task_type_id,  # This should auto-reserve inventory
        'assigned_to': 'S-0001'
    }
    
    r3 = client.post('/maintenance/', json=maintenance_payload)
    print(f'   Status: {r3.status_code}')
    
    if r3.status_code != 200:
        print(f'   ❌ FAILED: {r3.text}')
        return
    
    task_response = r3.json()
    task_id = task_response.get('id') or task_response.get('formatted_id')
    print(f'   ✅ Created maintenance task: {task_id}')
    
    # Check if inventory was auto-reserved
    inventory_requests = task_response.get('inventory_requests', [])
    print(f'   ✅ Auto-created {len(inventory_requests)} inventory reservations:')
    
    for req in inventory_requests:
        item_name = req.get('item_name', 'Unknown Item')
        quantity = req.get('quantity_requested', 0)
        status = req.get('status', 'unknown')
        print(f'      - {item_name}: {quantity} pcs ({status})')
    
    # ========================================================================
    # Step 4: Verify task type reference is saved
    # ========================================================================
    print('\\n[STEP 4] Verifying task type reference is saved...')
    
    # Fetch the created task to verify task_type_id is saved
    if 'task_type_id' in task_response:
        saved_task_type_id = task_response['task_type_id']
        if saved_task_type_id == task_type_id:
            print(f'   ✅ Task type ID correctly saved: {saved_task_type_id}')
        else:
            print(f'   ❌ Task type ID mismatch: expected {task_type_id}, got {saved_task_type_id}')
    else:
        print(f'   ⚠️  Task type ID not found in response')
    
    print('\\n' + '='*70)
    print('TASK TYPE INTEGRATION TEST COMPLETED')
    print('='*70 + '\\n')

if __name__ == '__main__':
    try:
        test_task_type_integration()
    except Exception as e:
        print(f'\\n❌ TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
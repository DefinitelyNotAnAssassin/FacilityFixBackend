"""
Test script to verify task type integration with maintenance task creation
Tests:
1. Fetching task types for dropdown
2. Creating maintenance task with task_type_id
3. Verifying inventory items are automatically reserved
"""
import sys, os
import asyncio
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.maintenance import router as maintenance_router
from app.routers.task_types import router as task_types_router
from app.services.task_type_service import task_type_service
from app.services.maintenance_task_service import maintenance_task_service
from app.services.inventory_service import inventory_service
from app.auth.dependencies import get_current_user as _real_get_current_user
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

# Setup test app
app = FastAPI()
app.include_router(maintenance_router)
app.include_router(task_types_router)

def fake_admin_user():
    return {"uid": "test_admin_user", "role": "admin", "email": "admin@example.com"}

app.dependency_overrides[_real_get_current_user] = fake_admin_user
client = TestClient(app)

async def test_task_type_maintenance_integration():
    """Test complete task type integration with maintenance tasks"""
    
    print('\n' + '='*70)
    print('TESTING TASK TYPE + MAINTENANCE TASK INTEGRATION')
    print('='*70)
    
    # Create test admin user
    admin_profile = {
        'user_id': 'test_admin_user',
        'first_name': 'Test',
        'last_name': 'Admin',
        'role': 'admin',
        'email': 'admin@example.com',
        'department': 'Administration'
    }
    
    try:
        await database_service.create_document(
            COLLECTIONS['users'], 
            admin_profile, 
            document_id=admin_profile['user_id']
        )
        print('✅ Created admin user profile')
    except Exception as e:
        print(f'⚠️  Admin user might already exist: {e}')
    
    # Step 1: Create inventory items
    print('\n[STEP 1] Creating inventory items...')
    
    inventory_items = [
        {
            'building_id': 'test_building',
            'item_name': 'Pipe Wrench 12 inch',
            'department': 'Maintenance',
            'classification': 'tool',
            'current_stock': 5,
            'reorder_level': 2,
            'unit_of_measure': 'pcs'
        },
        {
            'building_id': 'test_building', 
            'item_name': 'Teflon Tape Roll',
            'department': 'Maintenance',
            'classification': 'consumable',
            'current_stock': 20,
            'reorder_level': 5,
            'unit_of_measure': 'pcs'
        }
    ]
    
    created_inventory_ids = []
    for item in inventory_items:
        success, item_id, err = await inventory_service.create_inventory_item(item, 'test_admin_user')
        if success:
            created_inventory_ids.append(item_id)
            print(f'   ✅ Created inventory: {item["item_name"]} (ID: {item_id})')
        else:
            print(f'   ❌ Failed to create inventory: {err}')
    
    # Step 2: Create task type with inventory items
    print('\n[STEP 2] Creating task type with inventory items...')
    
    task_type_data = {
        'name': 'Plumbing Leak Repair',
        'description': 'Standard procedure for fixing plumbing leaks',
        'maintenance_type': 'Corrective',
        'inventory_items': [
            {'inventory_id': created_inventory_ids[0], 'quantity': 1, 'item_name': 'Pipe Wrench 12 inch'},
            {'inventory_id': created_inventory_ids[1], 'quantity': 2, 'item_name': 'Teflon Tape Roll'}
        ]
    }
    
    success, task_type_id, error = await task_type_service.create_task_type(task_type_data, 'test_admin_user')
    
    if not success:
        print(f'❌ Failed to create task type: {error}')
        return
    
    print(f'✅ Created task type: {task_type_id}')
    
    # Step 3: Test task type dropdown endpoint
    print('\n[STEP 3] Testing task type dropdown endpoint...')
    
    r1 = client.get('/maintenance/task-types')
    print(f'   Status: {r1.status_code}')
    
    if r1.status_code == 200:
        dropdown_data = r1.json()
        print(f'   Found {dropdown_data.get("count", 0)} task types')
        
        # Find our task type
        our_task_type = None
        for tt in dropdown_data.get('data', []):
            if tt.get('id') == task_type_id:
                our_task_type = tt
                break
        
        if our_task_type:
            print(f'   ✅ Found our task type in dropdown:')
            print(f'       Name: {our_task_type.get("name")}')
            print(f'       Maintenance Type: {our_task_type.get("maintenance_type")}')
            print(f'       Inventory Items: {len(our_task_type.get("inventory_items", []))}')
        else:
            print(f'   ❌ Our task type not found in dropdown')
    else:
        print(f'   ❌ Dropdown request failed: {r1.text}')
    
    # Step 4: Create maintenance task with task_type_id
    print('\n[STEP 4] Creating maintenance task with task_type_id...')
    
    maintenance_task_payload = {
        'building_id': 'test_building',
        'task_title': 'Fix Leak in Unit 101',
        'task_description': 'Repair plumbing leak reported by tenant',
        'location': 'Unit 101 - Bathroom',
        'scheduled_date': '2025-12-03T10:00:00Z',
        'task_type_id': task_type_id,  # This should auto-reserve inventory
        'assigned_to': 'test_admin_user',
        'priority': 'high'
    }
    
    r2 = client.post('/maintenance/', json=maintenance_task_payload)
    print(f'   Status: {r2.status_code}')
    
    if r2.status_code == 200:
        response_data = r2.json()
        task_data = response_data.get('task', {})
        task_id = task_data.get('id')
        print(f'   ✅ Created maintenance task: {task_id}')
        
        # Check if inventory was auto-reserved
        inventory_reservations = task_data.get('inventory_reservations', [])
        inventory_reservation_ids = task_data.get('inventory_reservation_ids', [])
        
        print(f'   Auto-created inventory reservations: {len(inventory_reservation_ids)}')
        
        if inventory_reservations:
            print('   📋 Reserved inventory:')
            for res in inventory_reservations:
                item_id = res.get('inventory_id')
                quantity = res.get('quantity') 
                status = res.get('status')
                
                # Fetch item details (use item_code as formatted ID)
                item_success, item_data, _ = asyncio.run(inventory_service.get_inventory_item(item_id))
                if item_success and item_data:
                    item_code = item_data.get('item_code', item_id)
                    item_name = item_data.get('item_name', 'Unknown')
                    print(f'       - {item_name} ({item_code}): qty {quantity} ({status})')
                else:
                    print(f'       - {item_id}: qty {quantity} ({status})')
        
        # Verify task_type_id was saved
        saved_task_type_id = task_data.get('task_type_id')
        print(f'   Saved task_type_id: {saved_task_type_id}')
        
        if saved_task_type_id == task_type_id:
            print('   ✅ Task type reference saved correctly')
        else:
            print('   ❌ Task type reference not saved properly')
            
    else:
        print(f'   ❌ Maintenance task creation failed: {r2.text}')
    
    print('\n' + '='*70)
    print('TASK TYPE INTEGRATION TEST COMPLETE')
    print('='*70)

if __name__ == '__main__':
    asyncio.run(test_task_type_maintenance_integration())
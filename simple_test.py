#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.core.firebase_init import initialize_firebase
from app.services.inventory_service import inventory_service
from app.services.task_type_service import task_type_service
from app.services.maintenance_task_service import maintenance_task_service

async def simple_reservation_test():
    """Simple test without FastAPI client"""
    print("🔧 SIMPLE INVENTORY RESERVATION TEST")
    print("=" * 40)
    
    # Initialize Firebase
    try:
        initialize_firebase()
        print("✅ Firebase initialized")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return
    
    try:
        # Step 1: Create a simple inventory item
        print("\n[STEP 1] Creating test inventory item...")
        
        inventory_data = {
            'building_id': 'test_building',
            'item_name': 'Simple Test Wrench',
            'department': 'Maintenance',
            'classification': 'tool',
            'current_stock': 5,
            'reorder_level': 1,
            'unit_of_measure': 'pcs'
        }
        
        success, item_id, error = await inventory_service.create_inventory_item(inventory_data, 'test_user')
        if not success:
            print(f"❌ Failed to create inventory: {error}")
            return
        
        print(f"✅ Created inventory item: {item_id}")
        
        # Step 2: Test direct reservation creation
        print("\n[STEP 2] Testing direct reservation creation...")
        
        reservation_data = {
            'inventory_id': item_id,
            'maintenance_task_id': 'TEST-TASK-001',
            'quantity': 2
        }
        
        success, res_id, error = await inventory_service.create_inventory_reservation(reservation_data, 'test_user')
        if success:
            print(f"✅ Created reservation: {res_id}")
        else:
            print(f"❌ Failed to create reservation: {error}")
            
        # Step 3: Test maintenance task creation with reservations
        print("\n[STEP 3] Testing maintenance task with auto-reservations...")
        
        # Create task type first
        task_type_data = {
            'name': 'Simple Test Task',
            'description': 'Simple test',
            'maintenance_type': 'Corrective',
            'inventory_items': [
                {'inventory_id': item_id, 'quantity': 1, 'item_name': 'Simple Test Wrench'}
            ]
        }
        
        success, task_type_id, error = await task_type_service.create_task_type(task_type_data, 'test_user')
        if not success:
            print(f"❌ Failed to create task type: {error}")
            return
        
        print(f"✅ Created task type: {task_type_id}")
        
        # Create maintenance task
        maintenance_payload = {
            'building_id': 'test_building',
            'task_title': 'Simple Test Task',
            'task_description': 'Testing reservations',
            'location': 'Test Area',
            'scheduled_date': '2025-12-03T10:00:00Z',
            'task_type_id': task_type_id,
            'assigned_to': 'test_user'
        }
        
        task = await maintenance_task_service.create_task('test_user', maintenance_payload)
        
        print(f"✅ Created maintenance task: {task.id}")
        print(f"📋 Task type ID: {task.task_type_id}")
        
        # Check reservations
        reservation_ids = getattr(task, 'inventory_reservation_ids', [])
        print(f"🎯 Created reservations: {len(reservation_ids)}")
        
        if reservation_ids:
            print("📦 Reservation details:")
            for res_id in reservation_ids:
                print(f"   - Reservation ID: {res_id}")
        else:
            print("❌ No reservations found in task")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(simple_reservation_test())
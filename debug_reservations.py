#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.core.firebase_init import initialize_firebase
from app.services.inventory_service import inventory_service
from app.services.task_type_service import task_type_service
from app.services.maintenance_task_service import maintenance_task_service
from fastapi.testclient import TestClient
from app.main import app

async def debug_reservation_system():
    """Debug the inventory reservation system"""
    print("🔧 DEBUGGING INVENTORY RESERVATION SYSTEM")
    print("=" * 50)
    
    # Initialize Firebase
    try:
        initialize_firebase()
        print("✅ Firebase initialized")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return
    
    client = TestClient(app)
    
    try:
        # Step 1: Create a simple inventory item
        print("\n[STEP 1] Creating test inventory item...")
        
        inventory_data = {
            'building_id': 'test_building',
            'item_name': 'Test Wrench',
            'department': 'Maintenance',
            'classification': 'tool',
            'current_stock': 10,
            'reorder_level': 2,
            'unit_of_measure': 'pcs'
        }
        
        success, item_id, error = await inventory_service.create_inventory_item(inventory_data, 'test_user')
        if not success:
            print(f"❌ Failed to create inventory: {error}")
            return
        
        print(f"✅ Created inventory item: {item_id}")
        
        # Step 2: Create a task type with this inventory
        print("\n[STEP 2] Creating task type with inventory...")
        
        task_type_data = {
            'name': 'Test Repair Task',
            'description': 'Test task with inventory',
            'maintenance_type': 'Corrective',
            'inventory_items': [
                {'inventory_id': item_id, 'quantity': 2, 'item_name': 'Test Wrench'}
            ]
        }
        
        success, task_type_id, error = await task_type_service.create_task_type(task_type_data, 'test_user')
        if not success:
            print(f"❌ Failed to create task type: {error}")
            return
        
        print(f"✅ Created task type: {task_type_id}")
        
        # Step 3: Create maintenance task with task_type_id
        print("\n[STEP 3] Creating maintenance task...")
        
        maintenance_payload = {
            'building_id': 'test_building',
            'task_title': 'Test Maintenance Task',
            'task_description': 'Testing reservation system',
            'location': 'Test Location',
            'scheduled_date': '2025-12-03T10:00:00Z',
            'task_type_id': task_type_id,  # This should create reservations
            'assigned_to': 'test_user'
        }
        
        # Create task via service (bypass auth for testing)
        task = await maintenance_task_service.create_task('test_user', maintenance_payload)
        
        print(f"✅ Created maintenance task: {task.id}")
        print(f"📋 Task type ID saved: {task.task_type_id}")
        
        # Check for reservations
        reservation_ids = getattr(task, 'inventory_reservation_ids', [])
        print(f"🎯 Created reservations: {len(reservation_ids)}")
        
        if reservation_ids:
            print("📦 Reservation details:")
            for res_id in reservation_ids:
                success, res_doc, err = await inventory_service.db.get_document('inventory_reservations', res_id)
                if success and res_doc:
                    inv_id = res_doc.get('inventory_id')
                    quantity = res_doc.get('quantity')
                    status = res_doc.get('status')
                    print(f"   - {inv_id}: qty {quantity} ({status})")
        else:
            print("❌ No reservations created")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(debug_reservation_system())
#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app.core.firebase_init import initialize_firebase
from app.services.task_type_service import task_type_service
from app.services.inventory_service import inventory_service

async def test_task_types_direct():
    """Test task types service directly"""
    print("🔧 TESTING TASK TYPES SERVICE DIRECTLY")
    print("=" * 50)
    
    try:
        # Initialize Firebase
        initialize_firebase()
        print("✅ Firebase initialized")
        
        # Test task type service
        print("\n[TEST] Calling task_type_service.list_task_types()...")
        
        success, task_types, error = await task_type_service.list_task_types(include_inactive=False)
        
        if success:
            print(f"✅ Success: Found {len(task_types)} task types")
            
            if task_types:
                print(f"\n📦 Task Types:")
                for i, tt in enumerate(task_types[:2]):  # Show first 2
                    print(f"  [{i+1}] ID: {tt.get('_doc_id') or tt.get('id') or tt.get('formatted_id')}")
                    print(f"      Name: {tt.get('name')}")
                    print(f"      Type: {tt.get('maintenance_type')}")
                    
                    inventory_items = tt.get('inventory_items', [])
                    print(f"      Inventory Items: {len(inventory_items)}")
                    
                    # Test inventory enrichment
                    for j, item in enumerate(inventory_items[:1]):  # Show first item
                        inventory_id = item.get("inventory_id") or item.get("id")
                        print(f"        [{j+1}] Testing inventory ID: {inventory_id}")
                        
                        # Test inventory service
                        item_success, item_data, item_error = await inventory_service.get_inventory_item(inventory_id)
                        
                        if item_success and item_data:
                            print(f"            ✅ Found: {item_data.get('item_name')} (Stock: {item_data.get('current_stock', 0)})")
                        else:
                            print(f"            ❌ Not found: {item_error}")
            else:
                print("❌ No task types returned")
        else:
            print(f"❌ Failed to get task types: {error}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_task_types_direct())
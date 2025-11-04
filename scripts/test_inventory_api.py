"""
Test Inventory API endpoints
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from app.services.inventory_service import inventory_service
import asyncio


async def test_inventory_crud():
    """Test basic inventory CRUD operations"""
    
    print("=" * 60)
    print("Testing Inventory CRUD Operations")
    print("=" * 60)
    
    try:
        # 1. Get all inventory items for a building
        print("\n1️⃣  Testing: Get inventory items by building")
        success, items, error = await inventory_service.get_inventory_by_building('default_building_id')
        
        if success:
            print(f"✅ Found {len(items)} inventory items")
            for item in items:
                print(f"   - {item.get('item_name')} (Code: {item.get('item_code')}) - Stock: {item.get('current_stock')}")
        else:
            print(f"❌ Failed to get inventory: {error}")
        
        # 2. Create a new inventory item
        print("\n2️⃣  Testing: Create inventory item")
        new_item = {
            'building_id': 'default_building_id',
            'item_name': 'Test Paint',
            'item_code': 'PAINT-001',
            'department': 'Maintenance',
            'classification': 'Consumables',
            'category': 'Paint',
            'current_stock': 15,
            'reorder_level': 5,
            'max_stock_level': 30,
            'unit_of_measure': 'gallons',
            'unit_cost': 35.00,
            'supplier_name': 'Paint Supplier Co',
            'storage_location': 'Storage Room B',
            'is_critical': False,
            'is_active': True,
            'brand_name': 'Premium Paint Brand'
        }
        
        success, item_id, error = await inventory_service.create_inventory_item(
            new_item,
            created_by='test_user'
        )
        
        if success:
            print(f"✅ Created inventory item with ID: {item_id}")
        else:
            print(f"❌ Failed to create item: {error}")
        
        # 3. Get the created item
        if success:
            print("\n3️⃣  Testing: Get inventory item by ID")
            get_success, item_data, get_error = await inventory_service.get_inventory_item(item_id)
            
            if get_success:
                print(f"✅ Retrieved item: {item_data.get('item_name')}")
                print(f"   Stock: {item_data.get('current_stock')} {item_data.get('unit_of_measure')}")
            else:
                print(f"❌ Failed to get item: {get_error}")
        
        # 4. Create an inventory request
        print("\n4️⃣  Testing: Create inventory request")
        request_data = {
            'inventory_id': item_id if success else 'test_id',
            'building_id': 'default_building_id',
            'requested_by': 'test_user',
            'quantity_requested': 5,
            'purpose': 'Maintenance Task #123',
            'status': 'pending',
            'priority': 'medium'
        }
        
        req_success, request_id, req_error = await inventory_service.create_inventory_request(request_data)
        
        if req_success:
            print(f"✅ Created inventory request with ID: {request_id}")
        else:
            print(f"❌ Failed to create request: {req_error}")
        
        # 5. Get inventory requests
        print("\n5️⃣  Testing: Get inventory requests")
        list_success, requests, list_error = await inventory_service.get_inventory_requests(
            building_id='default_building_id'
        )
        
        if list_success:
            print(f"✅ Found {len(requests)} inventory requests")
            for req in requests:
                print(f"   - Qty: {req.get('quantity_requested')}, Status: {req.get('status')}")
        else:
            print(f"❌ Failed to get requests: {list_error}")
        
        # 6. Get inventory summary
        print("\n6️⃣  Testing: Get inventory summary")
        sum_success, summary, sum_error = await inventory_service.get_inventory_summary('default_building_id')
        
        if sum_success:
            print(f"✅ Inventory Summary:")
            print(f"   Total Items: {summary.get('total_items')}")
            print(f"   Low Stock Items: {summary.get('low_stock_items')}")
            print(f"   Out of Stock: {summary.get('out_of_stock_items')}")
            print(f"   Critical Items: {summary.get('critical_items')}")
        else:
            print(f"❌ Failed to get summary: {sum_error}")
        
        print("\n" + "=" * 60)
        print("✅ All inventory tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_inventory_crud())

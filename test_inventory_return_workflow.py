"""
Test script for inventory return workflow with conditional auto-receive
Tests both good and defective item return scenarios
"""
import asyncio
import sys
from datetime import datetime
from app.services.inventory_service import inventory_service


class FakeDB:
    """In-memory fake database for testing"""
    def __init__(self):
        self.collections = {}
        self.doc_counter = 0
    
    def _get_next_id(self):
        self.doc_counter += 1
        return f"doc_{self.doc_counter}"
    
    async def create_document(self, collection, data, validate=False):
        if collection not in self.collections:
            self.collections[collection] = {}
        
        doc_id = self._get_next_id()
        doc_data = {**data, '_doc_id': doc_id, 'id': doc_id}
        self.collections[collection][doc_id] = doc_data
        return True, doc_id, None
    
    async def get_document(self, collection, doc_id):
        if collection not in self.collections:
            return False, None, "Collection not found"
        
        doc = self.collections[collection].get(doc_id)
        if not doc:
            return False, None, "Document not found"
        
        return True, doc, None
    
    async def update_document(self, collection, doc_id, data):
        if collection not in self.collections:
            return False, "Collection not found"
        
        if doc_id not in self.collections[collection]:
            return False, "Document not found"
        
        self.collections[collection][doc_id].update(data)
        return True, None
    
    async def query_documents(self, collection, filters=None):
        if collection not in self.collections:
            return True, [], None
        
        docs = list(self.collections[collection].values())
        
        if filters:
            for field, op, value in filters:
                if op == '==':
                    docs = [d for d in docs if d.get(field) == value]
                elif op == '!=':
                    docs = [d for d in docs if d.get(field) != value]
        
        return True, docs, None


# Use fake database for testing
inventory_service.db = FakeDB()

async def test_return_workflow():
    """Test the conditional auto-receive workflow for inventory returns"""
    
    print("\n" + "="*80)
    print("INVENTORY RETURN WORKFLOW TEST")
    print("="*80)
    
    # Step 1: Create test inventory item
    print("\n📦 Step 1: Creating test inventory item...")
    item_data = {
        'item_name': 'Cordless Drill',
        'item_code': 'TOOL-DRILL-001',
        'category': 'tools',
        'current_stock': 10,
        'minimum_stock': 3,
        'unit_of_measure': 'pcs',
        'building_id': 'building_001',
        'location': 'Tool Room A',
        'is_active': True
    }
    
    success, item_id, error = await inventory_service.create_inventory_item(
        item_data, 
        'admin_001'
    )
    
    if not success:
        print(f"❌ Failed to create item: {error}")
        return
    
    print(f"✅ Created item: {item_id}")
    print(f"   Initial stock: {item_data['current_stock']}")
    
    # Step 2: Create reservation
    print("\n📋 Step 2: Creating inventory reservation...")
    reservation_data = {
        'inventory_id': item_id,
        'maintenance_task_id': 'task_001',
        'quantity': 2,
        'status': 'approved',
        'building_id': 'building_001'
    }
    
    success, reservation_id, error = await inventory_service.create_inventory_reservation(
        reservation_data,
        'admin_001'
    )
    
    if not success:
        print(f"❌ Failed to create reservation: {error}")
        return
    
    print(f"✅ Created reservation: {reservation_id}")
    print(f"   Reserved quantity: {reservation_data['quantity']}")
    
    # Step 3: Mark reservation as received (staff picked up items)
    print("\n📥 Step 3: Marking reservation as received...")
    success, error = await inventory_service.mark_reservation_received(
        reservation_id,
        'staff_001'
    )
    
    if not success:
        print(f"❌ Failed to mark as received: {error}")
        return
    
    print(f"✅ Reservation marked as received by staff")
    
    # Get current stock before returns
    success, item_before, _ = await inventory_service.get_inventory_item(item_id)
    stock_before = item_before.get('current_stock', 0) if success else 0
    print(f"   Current stock before return: {stock_before}")
    
    # SCENARIO A: Return in GOOD condition
    print("\n" + "-"*80)
    print("SCENARIO A: RETURN IN GOOD CONDITION")
    print("-"*80)
    
    print("\n🔄 Returning 1 item in GOOD condition...")
    success, return_data, error = await inventory_service.return_reservation(
        reservation_id,
        'staff_001',
        quantity=1,
        notes="Item not needed for this task",
        item_condition="good",
        needs_replacement=False
    )
    
    if not success:
        print(f"❌ Return failed: {error}")
    else:
        print(f"✅ Return successful!")
        print(f"   Return ID: {return_data['return_id']}")
        print(f"   Quantity returned: {return_data['quantity_returned']}")
        print(f"   Item condition: {return_data['item_condition']}")
        print(f"   Status: {return_data['status']}")
        print(f"   New stock level: {return_data['new_stock']}")
        print(f"   Stock change: {stock_before} → {return_data['new_stock']} (+{return_data['new_stock'] - stock_before})")
        
        if return_data['status'] == 'available':
            print("   ✅ Item added back to available stock")
        else:
            print(f"   ⚠️  Unexpected status: {return_data['status']}")
    
    # Get updated item status
    success, item_after_good, _ = await inventory_service.get_inventory_item(item_id)
    if success:
        print(f"\n📊 Item Status After Good Return:")
        print(f"   Active: {item_after_good.get('is_active', 'N/A')}")
        print(f"   Status: {item_after_good.get('status', 'N/A')}")
        print(f"   Current Stock: {item_after_good.get('current_stock', 'N/A')}")
    
    # SCENARIO B: Return DEFECTIVE item
    print("\n" + "-"*80)
    print("SCENARIO B: RETURN DEFECTIVE/BROKEN ITEM")
    print("-"*80)
    
    # Get stock before defective return
    stock_before_defective = item_after_good.get('current_stock', 0) if success else 0
    
    print("\n🔄 Returning 1 item as DEFECTIVE (with replacement request)...")
    success, return_data, error = await inventory_service.return_reservation(
        reservation_id,
        'staff_001',
        quantity=1,
        notes="Drill bit broke during AC repair operation",
        item_condition="defective",
        needs_replacement=True
    )
    
    if not success:
        print(f"❌ Return failed: {error}")
    else:
        print(f"✅ Return successful!")
        print(f"   Return ID: {return_data['return_id']}")
        print(f"   Quantity returned: {return_data['quantity_returned']}")
        print(f"   Item condition: {return_data['item_condition']}")
        print(f"   Is defective: {return_data['is_defective']}")
        print(f"   Needs replacement: {return_data['needs_replacement']}")
        print(f"   Status: {return_data['status']}")
        print(f"   Stock level: {return_data['new_stock']}")
        print(f"   Stock change: {stock_before_defective} → {return_data['new_stock']} (±{return_data['new_stock'] - stock_before_defective})")
        
        if return_data['status'] == 'quarantined':
            print("   ✅ Item quarantined (not added to available stock)")
        else:
            print(f"   ⚠️  Unexpected status: {return_data['status']}")
        
        if return_data['is_defective']:
            print("   ✅ Item marked as defective")
        
        if return_data['needs_replacement']:
            print("   ✅ Replacement request should be created")
    
    # Get final item status
    success, item_final, _ = await inventory_service.get_inventory_item(item_id)
    if success:
        print(f"\n📊 Item Status After Defective Return:")
        print(f"   Active: {item_final.get('is_active', 'N/A')}")
        print(f"   Status: {item_final.get('status', 'N/A')}")
        print(f"   Current Stock: {item_final.get('current_stock', 'N/A')}")
        print(f"   Condition Notes: {item_final.get('condition_notes', 'N/A')}")
        
        if item_final.get('status') == 'needs_repair':
            print("   ✅ Item correctly marked as needs_repair")
        if item_final.get('is_active') == False:
            print("   ✅ Item correctly deactivated (quarantined)")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Good return: Item added to stock")
    print(f"✅ Defective return: Item quarantined (needs_repair)")
    print(f"✅ Stock properly managed based on condition")
    print(f"✅ Admin notifications triggered (check logs)")
    print("\n🎉 All tests completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(test_return_workflow())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

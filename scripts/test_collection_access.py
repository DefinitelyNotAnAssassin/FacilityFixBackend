"""
Test Collection Access - Diagnose Firestore collection issues
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from datetime import datetime
import asyncio


async def test_collections():
    """Test access to all inventory collections"""
    
    print("=" * 60)
    print("Testing Firestore Collection Access")
    print("=" * 60)
    
    # Check COLLECTIONS dictionary
    print("\n1️⃣  Checking COLLECTIONS dictionary:")
    inventory_collections = [
        'inventory',
        'inventory_transactions',
        'inventory_requests',
        'low_stock_alerts',
        'inventory_usage_analytics'
    ]
    
    for coll_name in inventory_collections:
        coll_key = COLLECTIONS.get(coll_name)
        print(f"   {coll_name}: {coll_key}")
    
    # Test creating a document in inventory_requests
    print("\n2️⃣  Testing document creation in inventory_requests:")
    test_request = {
        'inventory_id': 'TEST-001',
        'building_id': 'default_building_id',
        'requested_by': 'test_user',
        'quantity_requested': 1,
        'purpose': 'Test request',
        'status': 'pending',
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'requested_date': datetime.now()
    }
    
    try:
        print(f"   Collection key: {COLLECTIONS['inventory_requests']}")
        success, doc_id, error = await database_service.create_document(
            COLLECTIONS['inventory_requests'],
            test_request,
            validate=False
        )
        
        if success:
            print(f"   ✅ Successfully created test request with ID: {doc_id}")
            
            # Try to read it back
            print("\n3️⃣  Testing document retrieval:")
            get_success, doc_data, get_error = await database_service.get_document(
                COLLECTIONS['inventory_requests'],
                doc_id
            )
            
            if get_success:
                print(f"   ✅ Successfully retrieved document")
                print(f"   Quantity: {doc_data.get('quantity_requested')}")
                print(f"   Status: {doc_data.get('status')}")
            else:
                print(f"   ❌ Failed to retrieve: {get_error}")
            
            # Clean up
            delete_success, delete_error = await database_service.delete_document(
                COLLECTIONS['inventory_requests'],
                doc_id
            )
            if delete_success:
                print(f"   🗑️  Cleaned up test document")
        else:
            print(f"   ❌ Failed to create: {error}")
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test querying
    print("\n4️⃣  Testing query on inventory_requests:")
    try:
        success, docs, error = await database_service.query_documents(
            COLLECTIONS['inventory_requests'],
            [('status', '==', 'pending')]
        )
        
        if success:
            print(f"   ✅ Query successful, found {len(docs)} pending requests")
        else:
            print(f"   ❌ Query failed: {error}")
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Diagnostic complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_collections())

#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

async def test_firebase_direct():
    """Test Firebase collection directly"""
    print("🔧 TESTING FIREBASE COLLECTION DIRECTLY")
    print("=" * 50)
    
    try:
        from app.core.firebase_init import initialize_firebase
        from app.database.database_service import database_service
        
        # Initialize Firebase
        initialize_firebase()
        print("✅ Firebase initialized")
        
        # Test direct Firebase query
        print(f"\n[TEST] Querying 'task_types' collection...")
        
        success, documents, error = await database_service.query_documents('task_types', [])
        
        print(f"Success: {success}")
        print(f"Error: {error}")
        print(f"Document count: {len(documents) if documents else 0}")
        
        if documents:
            print(f"\n📦 First few documents:")
            for i, doc in enumerate(documents[:2]):
                print(f"  [{i+1}] Doc ID: {doc.get('_doc_id')}")
                print(f"      ID: {doc.get('id')}")
                print(f"      Name: {doc.get('name')}")
                print(f"      Category: {doc.get('category')}")
                print(f"      Maintenance Type: {doc.get('maintenance_type')}")
                print(f"      Is Active: {doc.get('is_active')}")
                print(f"      Raw: {doc}")
        else:
            print("❌ No documents found")
            
        # Test with is_active filter
        print(f"\n[TEST] Querying with is_active=True filter...")
        success2, documents2, error2 = await database_service.query_documents(
            'task_types', 
            [('is_active', '==', True)]
        )
        
        print(f"Filtered Success: {success2}")
        print(f"Filtered Count: {len(documents2) if documents2 else 0}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_firebase_direct())
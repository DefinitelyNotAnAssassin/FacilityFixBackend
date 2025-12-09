"""
Script to create compound index for inventory_reservations collection
This prevents duplicate reservations for the same item and maintenance task.

Run this script once to set up the index in Firestore.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import firestore
from app.core.firebase_config import admin_firestore


async def create_compound_index():
    """
    Create compound index on inventory_reservations collection.
    
    This index is used to efficiently query and prevent duplicates based on:
    - inventory_id
    - maintenance_task_id  
    - status
    """
    print("=" * 80)
    print("CREATING COMPOUND INDEX FOR INVENTORY RESERVATIONS")
    print("=" * 80)
    
    print("\n⚠️  IMPORTANT: Firestore compound indexes must be created via:")
    print("   1. Firebase Console (Recommended)")
    print("   2. Firebase CLI")
    print("   3. Automatic creation when query fails")
    
    print("\n📋 Index Configuration:")
    print("   Collection: inventory_reservations")
    print("   Fields:")
    print("     - inventory_id (Ascending)")
    print("     - maintenance_task_id (Ascending)")
    print("     - status (Ascending)")
    
    print("\n" + "=" * 80)
    print("OPTION 1: Create via Firebase Console")
    print("=" * 80)
    print("1. Go to: https://console.firebase.google.com")
    print("2. Select your project")
    print("3. Navigate to: Firestore Database > Indexes")
    print("4. Click 'Create Index'")
    print("5. Configure:")
    print("   - Collection ID: inventory_reservations")
    print("   - Add fields:")
    print("     * inventory_id (Ascending)")
    print("     * maintenance_task_id (Ascending)")
    print("     * status (Ascending)")
    print("6. Click 'Create Index'")
    
    print("\n" + "=" * 80)
    print("OPTION 2: Trigger Automatic Index Creation")
    print("=" * 80)
    print("Running a query that requires the index will prompt Firestore to create it...")
    
    try:
        db = admin_firestore()
        
        # This query will fail if index doesn't exist and provide a link to create it
        query = (
            db.collection('inventory_reservations')
            .where('inventory_id', '==', 'TEST-ITEM-001')
            .where('maintenance_task_id', '==', 'TEST-TASK-001')
            .where('status', '==', 'reserved')
        )
        
        print("\n🔍 Attempting query to trigger index creation...")
        docs = query.limit(1).get()
        
        print("✅ Index already exists! Query executed successfully.")
        print(f"   Found {len(docs)} documents (this is expected to be 0 for test data)")
        
    except Exception as e:
        error_msg = str(e)
        
        if "index" in error_msg.lower():
            print("\n⚠️  Index does not exist yet!")
            print("\n📝 Error message from Firestore:")
            print(f"   {error_msg}")
            
            # Extract index creation URL if available
            if "https://" in error_msg:
                import re
                urls = re.findall(r'https://[^\s]+', error_msg)
                if urls:
                    print("\n🔗 Click this link to create the index:")
                    print(f"   {urls[0]}")
                    print("\n   After clicking the link:")
                    print("   1. Review the index configuration")
                    print("   2. Click 'Create Index'")
                    print("   3. Wait for the index to build (usually takes a few minutes)")
        else:
            print(f"\n❌ Unexpected error: {error_msg}")
    
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print("After creating the index, run this script again to verify it works.")
    print("You should see: '✅ Index already exists! Query executed successfully.'")
    
    print("\n" + "=" * 80)
    print("WHY THIS INDEX IS IMPORTANT")
    print("=" * 80)
    print("✓ Prevents duplicate reservations for the same item + task")
    print("✓ Makes duplicate-check queries much faster")
    print("✓ Required for the backend duplicate prevention logic")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(create_compound_index())

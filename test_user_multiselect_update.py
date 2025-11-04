"""
Test script for user update with multi-select departments
Run this to test the update endpoint independently
"""

import asyncio
import sys
sys.path.append('backend')

from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from datetime import datetime, timezone

async def test_user_update():
    print("=" * 60)
    print("Testing User Update with Multi-Select Departments")
    print("=" * 60)
    
    # Find a test user
    print("\n1. Fetching a test user...")
    success, users, error = await database_service.query_documents(
        COLLECTIONS['users'],
        filters=[('role', '==', 'staff')],
        limit=1
    )
    
    if not success or not users:
        print(f"❌ Failed to fetch test user: {error}")
        return
    
    test_user = users[0]
    user_id = test_user.get('user_id')
    doc_id = test_user.get('_doc_id') or test_user.get('id')
    
    print(f"✅ Found test user: {user_id}")
    print(f"   Document ID: {doc_id}")
    print(f"   Current department: {test_user.get('department')}")
    print(f"   Current departments: {test_user.get('departments')}")
    
    # Test update with multi-select departments
    print("\n2. Updating user with multi-select departments...")
    test_departments = ["Maintenance", "HVAC", "Electrical"]
    
    update_data = {
        "departments": test_departments,
        "staff_departments": test_departments,
        "department": test_departments[0],  # Legacy
        "staff_department": test_departments[0],  # Legacy
        "updated_at": datetime.now(timezone.utc)
    }
    
    print(f"   Update data: {update_data}")
    
    success, error = await database_service.update_document(
        COLLECTIONS['users'],
        doc_id,
        update_data
    )
    
    if not success:
        print(f"❌ Update failed: {error}")
        return
    
    print("✅ Update successful!")
    
    # Verify update
    print("\n3. Verifying update...")
    success, updated_user, error = await database_service.get_document(
        COLLECTIONS['users'],
        doc_id
    )
    
    if not success:
        print(f"❌ Failed to fetch updated user: {error}")
        return
    
    print(f"✅ Updated user data:")
    print(f"   Department (legacy): {updated_user.get('department')}")
    print(f"   Departments (new): {updated_user.get('departments')}")
    print(f"   Staff department (legacy): {updated_user.get('staff_department')}")
    print(f"   Staff departments (new): {updated_user.get('staff_departments')}")
    
    # Verify data matches
    if (updated_user.get('departments') == test_departments and
        updated_user.get('staff_departments') == test_departments):
        print("\n✅ All checks passed! Multi-select departments working correctly.")
    else:
        print("\n❌ Data mismatch! Expected and actual values don't match.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_user_update())

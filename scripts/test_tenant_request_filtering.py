"""
Test script for tenant request filtering
Tests the role-based filtering logic for tenant requests endpoint
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from app.database.database_service import DatabaseService
from app.services.user_id_service import user_id_service

async def test_staff_filtering():
    """Test that staff filtering works with staff_id"""
    print("\n" + "="*60)
    print("Testing Staff Filtering Logic")
    print("="*60)
    
    db = DatabaseService()
    
    # Test 1: Get all users and find staff members
    print("\n[TEST 1] Finding staff members in users collection...")
    try:
        success, users_data, error = await db.query_documents("users", [])
        if success and users_data:
            staff_users = [u for u in users_data if u.get('role') == 'staff']
            print(f"✓ Found {len(staff_users)} staff members")
            
            for staff in staff_users[:3]:  # Show first 3
                user_id = staff.get('user_id') or staff.get('_firebase_doc_id')
                staff_id = staff.get('staff_id')
                email = staff.get('email')
                print(f"  - {email}: user_id={user_id}, staff_id={staff_id}")
        else:
            print(f"✗ Failed to query users: {error}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: Get sample requests with assigned_to field
    print("\n[TEST 2] Checking requests with assigned_to field...")
    collections = ["concern_slips", "job_service_requests", "work_order_permits"]
    
    for collection in collections:
        try:
            docs = await db.get_all_documents(collection)
            assigned_docs = [d for d in docs if d.get('assigned_to')]
            print(f"\n  {collection}:")
            print(f"    Total: {len(docs)}, With assigned_to: {len(assigned_docs)}")
            
            if assigned_docs:
                # Show unique assigned_to values
                assigned_ids = set(d.get('assigned_to') for d in assigned_docs)
                print(f"    Assigned to IDs: {list(assigned_ids)[:5]}")
        except Exception as e:
            print(f"    Error: {e}")
    
    # Test 3: Test user profile lookup
    print("\n[TEST 3] Testing user profile lookup...")
    try:
        if staff_users:
            test_staff = staff_users[0]
            test_user_id = test_staff.get('user_id') or test_staff.get('_firebase_doc_id')
            
            print(f"  Looking up profile for user_id: {test_user_id}")
            user_profile = await user_id_service.get_user_profile(test_user_id)
            
            if user_profile:
                print(f"  ✓ Profile found:")
                print(f"    Email: {user_profile.email}")
                print(f"    Role: {user_profile.role}")
                print(f"    Staff ID: {user_profile.staff_id}")
                
                # Test 4: Simulate filtering
                print("\n[TEST 4] Simulating staff filtering...")
                if user_profile.staff_id:
                    all_requests = []
                    for collection in collections:
                        docs = await db.get_all_documents(collection)
                        all_requests.extend(docs)
                    
                    filtered = [
                        req for req in all_requests 
                        if req.get('assigned_to') == user_profile.staff_id
                    ]
                    
                    print(f"  Total requests: {len(all_requests)}")
                    print(f"  Filtered for staff_id '{user_profile.staff_id}': {len(filtered)}")
                    
                    if filtered:
                        print(f"  Sample filtered requests:")
                        for req in filtered[:3]:
                            print(f"    - {req.get('id')} ({req.get('request_type', 'N/A')})")
                else:
                    print("  ✗ No staff_id found in profile")
            else:
                print(f"  ✗ Profile not found for {test_user_id}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

async def test_tenant_filtering():
    """Test that tenant filtering works with user_id"""
    print("\n" + "="*60)
    print("Testing Tenant Filtering Logic")
    print("="*60)
    
    db = DatabaseService()
    
    # Find tenant users
    print("\n[TEST 5] Finding tenant users...")
    try:
        success, users_data, error = await db.query_documents("users", [])
        if success and users_data:
            tenant_users = [u for u in users_data if u.get('role') == 'tenant']
            print(f"✓ Found {len(tenant_users)} tenant users")
            
            if tenant_users:
                test_tenant = tenant_users[0]
                tenant_uid = test_tenant.get('user_id') or test_tenant.get('_firebase_doc_id')
                email = test_tenant.get('email')
                
                print(f"\n  Testing with tenant: {email} (UID: {tenant_uid})")
                
                # Simulate tenant filtering
                collections = ["concern_slips", "job_service_requests", "work_order_permits"]
                all_requests = []
                
                for collection in collections:
                    docs = await db.get_all_documents(collection)
                    all_requests.extend(docs)
                
                filtered = [
                    req for req in all_requests 
                    if req.get('reported_by') == tenant_uid or req.get('requested_by') == tenant_uid
                ]
                
                print(f"  Total requests: {len(all_requests)}")
                print(f"  Filtered for tenant UID '{tenant_uid}': {len(filtered)}")
                
                if filtered:
                    print(f"  Sample filtered requests:")
                    for req in filtered[:3]:
                        print(f"    - {req.get('id')} ({req.get('request_type', 'N/A')})")
        else:
            print(f"✗ Failed to query users: {error}")
    except Exception as e:
        print(f"✗ Error: {e}")

async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TENANT REQUEST FILTERING TEST SUITE")
    print("="*60)
    
    await test_staff_filtering()
    await test_tenant_filtering()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())

"""
Test the correct inventory request flow:
1. Staff creates inventory request
2. Admin approves the request
3. Staff receives the approved request
"""
import sys, os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.inventory import router as inventory_router
from app.services.inventory_service import inventory_service
from app.auth.dependencies import get_current_user as _real_get_current_user
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

# ============================================================================
# Setup Test App and Clients
# ============================================================================

app_staff = FastAPI()
app_staff.include_router(inventory_router)

app_admin = FastAPI()
app_admin.include_router(inventory_router)

def fake_staff_user():
    return {"uid": "test_staff_user", "role": "staff", "email": "staff@example.com"}

def fake_admin_user():
    return {"uid": "test_admin_user", "role": "admin", "email": "admin@example.com"}

app_staff.dependency_overrides[_real_get_current_user] = fake_staff_user
app_admin.dependency_overrides[_real_get_current_user] = fake_admin_user

client_staff = TestClient(app_staff)
client_admin = TestClient(app_admin)

# ============================================================================
# Setup Test Data
# ============================================================================

async def setup_test_data():
    """Create user profiles and inventory item"""
    # Create admin user profile
    admin_profile = {
        'user_id': 'test_admin_user',
        'first_name': 'Test',
        'last_name': 'Admin',
        'role': 'admin',
        'department': 'Administration',
        'staff_id': None
    }
    await database_service.create_document(
        COLLECTIONS['users'], 
        admin_profile, 
        document_id=admin_profile['user_id']
    )
    print('✅ Created admin user profile')

    # Create staff user profile
    staff_profile = {
        'user_id': 'test_staff_user',
        'first_name': 'Test',
        'last_name': 'Staff',
        'role': 'staff',
        'department': 'Maintenance',
        'staff_id': 'S-0001'
    }
    await database_service.create_document(
        COLLECTIONS['users'], 
        staff_profile, 
        document_id=staff_profile['user_id']
    )
    print('✅ Created staff user profile')

    # Create an inventory item
    item_payload = {
        'building_id': 'test_building',
        'item_name': 'Wrench Set',
        'department': 'Maintenance',
        'classification': 'tool',
        'current_stock': 10,
        'reorder_level': 3,
        'unit_of_measure': 'pcs'
    }
    success, item_id, err = await inventory_service.create_inventory_item(
        item_payload, 
        'test_admin_user'
    )
    if not success:
        raise Exception(f"Failed to create inventory item: {err}")
    
    print(f'✅ Created inventory item: {item_id}')
    return item_id

# ============================================================================
# Test Flow
# ============================================================================

def test_staff_request_workflow():
    """Test complete staff request workflow"""
    print('\n' + '='*70)
    print('TESTING STAFF INVENTORY REQUEST WORKFLOW')
    print('='*70 + '\n')
    
    # Setup
    item_id = asyncio.run(setup_test_data())
    
    # ========================================================================
    # Step 1: Staff creates inventory request
    # ========================================================================
    print('\n[STEP 1] Staff creates inventory request...')
    request_payload = {
        'inventory_id': item_id,
        'quantity_requested': 2,
        'purpose': 'Repair work at Unit 101',
        'priority': 'normal',
        'status': 'pending'
    }
    
    r1 = client_staff.post('/inventory/requests', json=request_payload)
    print(f'   Status: {r1.status_code}')
    
    if r1.status_code != 200:
        print(f'   ❌ FAILED: {r1.text}')
        return
    
    response_data = r1.json()
    request_id = response_data.get('request_id')
    print(f'   ✅ SUCCESS: Request created with ID: {request_id}')
    
    # ========================================================================
    # Step 2: Admin approves the request
    # ========================================================================
    print('\n[STEP 2] Admin approves the request...')
    r2 = client_admin.post(
        f'/inventory/requests/{request_id}/approve',
        params={'quantity_approved': 2, 'admin_notes': 'Approved for maintenance work'}
    )
    print(f'   Status: {r2.status_code}')
    
    if r2.status_code != 200:
        print(f'   ❌ FAILED: {r2.text}')
        return
    
    print(f'   ✅ SUCCESS: Request approved by admin')
    
    # ========================================================================
    # Step 3: Staff receives the approved request
    # ========================================================================
    print('\n[STEP 3] Staff receives the approved request...')
    r3 = client_staff.post(
        f'/inventory/requests/{request_id}/receive',
        params={'deduct_stock': True}
    )
    print(f'   Status: {r3.status_code}')
    
    if r3.status_code != 200:
        print(f'   ❌ FAILED: {r3.text}')
        return
    
    print(f'   ✅ SUCCESS: Request marked as received by staff')
    
    # ========================================================================
    # Step 4: Verify final state
    # ========================================================================
    print('\n[STEP 4] Verify final state...')
    r4 = client_staff.get(f'/inventory/requests/{request_id}')
    
    if r4.status_code == 200:
        final_data = r4.json()['data']
        print(f'   Final status: {final_data.get("status")}')
        print(f'   Requested by: {final_data.get("requested_by")}')
        print(f'   Approved by: {final_data.get("approved_by")}')
        print(f'   ✅ Workflow complete!')
    
    print('\n' + '='*70)
    print('TEST COMPLETED SUCCESSFULLY')
    print('='*70 + '\n')

# ============================================================================
# Additional Tests
# ============================================================================

def test_staff_cannot_approve():
    """Test that staff cannot approve requests (admin-only)"""
    print('\n[NEGATIVE TEST] Staff attempts to approve request...')
    
    item_id = asyncio.run(setup_test_data())
    
    # Staff creates request
    request_payload = {
        'inventory_id': item_id,
        'quantity_requested': 1,
        'purpose': 'Test',
        'status': 'pending'
    }
    r1 = client_staff.post('/inventory/requests', json=request_payload)
    request_id = r1.json().get('request_id')
    
    # Staff tries to approve (should fail)
    r2 = client_staff.post(f'/inventory/requests/{request_id}/approve')
    print(f'   Status: {r2.status_code}')
    
    if r2.status_code == 403:
        print(f'   ✅ PASS: Staff correctly denied permission to approve')
    else:
        print(f'   ❌ FAIL: Staff should not be able to approve (got {r2.status_code})')

def test_staff_cannot_receive_unapproved():
    """Test that staff cannot receive unapproved requests"""
    print('\n[NEGATIVE TEST] Staff attempts to receive unapproved request...')
    
    item_id = asyncio.run(setup_test_data())
    
    # Staff creates request
    request_payload = {
        'inventory_id': item_id,
        'quantity_requested': 1,
        'purpose': 'Test',
        'status': 'pending'
    }
    r1 = client_staff.post('/inventory/requests', json=request_payload)
    request_id = r1.json().get('request_id')
    
    # Staff tries to receive without approval (should fail)
    r2 = client_staff.post(f'/inventory/requests/{request_id}/receive')
    print(f'   Status: {r2.status_code}')
    
    if r2.status_code == 403:
        print(f'   ✅ PASS: Staff correctly denied receiving unapproved request')
    else:
        print(f'   ❌ FAIL: Staff should not receive unapproved requests (got {r2.status_code})')

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    try:
        test_staff_request_workflow()
        # Uncomment to run negative tests
        # test_staff_cannot_approve()
        # test_staff_cannot_receive_unapproved()
    except Exception as e:
        print(f'\n❌ TEST FAILED WITH EXCEPTION: {e}')
        import traceback
        traceback.print_exc()

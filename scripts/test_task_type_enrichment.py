"""
Test script to verify Task Type user enrichment is working properly
"""
import sys, os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.task_type_service import task_type_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

async def test_task_type_user_enrichment():
    """Test that task types show proper user names"""
    
    print('\n' + '='*70)
    print('TESTING TASK TYPE USER ENRICHMENT')
    print('='*70 + '\n')
    
    # Create test user profiles first
    admin_profile = {
        'user_id': 'test_admin_user',
        'first_name': 'John',
        'last_name': 'Admin',
        'role': 'admin',
        'email': 'admin@example.com'
    }
    
    staff_profile = {
        'user_id': 'test_staff_user', 
        'first_name': 'Jane',
        'last_name': 'Staff',
        'role': 'staff',
        'email': 'staff@example.com'
    }
    
    try:
        await database_service.create_document(
            COLLECTIONS['users'], 
            admin_profile, 
            document_id=admin_profile['user_id']
        )
        await database_service.create_document(
            COLLECTIONS['users'], 
            staff_profile, 
            document_id=staff_profile['user_id']
        )
        print('✅ Created test user profiles')
    except Exception as e:
        print(f'⚠️  User profiles may already exist: {e}')
    
    # Create a task type
    task_type_data = {
        'name': 'Leak Repair Test',
        'description': 'Test task type for user enrichment',
        'category': 'Corrective',
        'maintenance_type': 'Corrective'
    }
    
    print('\n[STEP 1] Creating task type...')
    success, task_type_id, error = await task_type_service.create_task_type(
        task_type_data, 
        'test_admin_user'
    )
    
    if not success:
        print(f'❌ Failed to create task type: {error}')
        return
    
    print(f'✅ Created task type: {task_type_id}')
    
    # Fetch and verify enrichment
    print('\n[STEP 2] Fetching task type with enrichment...')
    success, enriched_task_type, error = await task_type_service.get_task_type(task_type_id)
    
    if not success:
        print(f'❌ Failed to fetch task type: {error}')
        return
    
    print(f'✅ Fetched task type successfully')
    
    # Display enriched fields
    print(f'\\n📋 ENRICHED TASK TYPE DATA:')
    print(f'   Name: {enriched_task_type.get("name")}')
    print(f'   ID: {enriched_task_type.get("formatted_id")}')
    print(f'   Created by (raw): {enriched_task_type.get("created_by")}')
    print(f'   Created by (name): {enriched_task_type.get("created_by_name")}')
    
    if enriched_task_type.get('updated_by'):
        print(f'   Updated by (raw): {enriched_task_type.get("updated_by")}')
        print(f'   Updated by (name): {enriched_task_type.get("updated_by_name")}')
    else:
        print(f'   Updated by: (not shown - item not edited)')
    
    # Test update scenario
    print('\\n[STEP 3] Updating task type to test updated_by enrichment...')
    success, error = await task_type_service.update_task_type(
        task_type_id,
        {'description': 'Updated description for enrichment test'},
        'test_staff_user'  # Different user updating
    )
    
    if not success:
        print(f'❌ Failed to update task type: {error}')
        return
        
    print(f'✅ Updated task type successfully')
    
    # Fetch again to see updated_by enrichment
    print('\\n[STEP 4] Fetching updated task type...')
    success, updated_task_type, error = await task_type_service.get_task_type(task_type_id)
    
    if success:
        print(f'\\n📋 UPDATED TASK TYPE DATA:')
        print(f'   Name: {updated_task_type.get("name")}')
        print(f'   Description: {updated_task_type.get("description")}')
        print(f'   Created by (name): {updated_task_type.get("created_by_name")}')
        
        if updated_task_type.get('updated_by'):
            print(f'   Updated by (raw): {updated_task_type.get("updated_by")}')
            print(f'   Updated by (name): {updated_task_type.get("updated_by_name")}')
            print(f'   ✅ Updated by fields correctly shown after edit')
        else:
            print(f'   ❌ Updated by fields missing after edit')
    
    # Test list enrichment
    print('\\n[STEP 5] Testing list enrichment...')
    success, task_types, error = await task_type_service.list_task_types()
    
    if success and task_types:
        print(f'✅ Found {len(task_types)} task types')
        for tt in task_types:
            if tt.get('formatted_id') == task_type_id:
                print(f'   Found our test task type in list:')
                print(f'     Created by: {tt.get("created_by_name", "NO NAME")}')
                if tt.get('updated_by_name'):
                    print(f'     Updated by: {tt.get("updated_by_name")}')
                break
    
    print('\\n' + '='*70)
    print('USER ENRICHMENT TEST COMPLETED')
    print('='*70 + '\\n')

if __name__ == '__main__':
    try:
        asyncio.run(test_task_type_user_enrichment())
    except Exception as e:
        print(f'\\n❌ TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
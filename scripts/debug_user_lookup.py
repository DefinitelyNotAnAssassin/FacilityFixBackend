"""
Test to debug why created_by_name is not working for task types
"""
import sys, os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.task_type_service import task_type_service
from app.services.user_id_service import user_id_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

async def test_user_lookup():
    """Test user lookup for the actual UID showing in the screenshot"""
    
    print('\\n' + '='*60)
    print('DEBUGGING USER LOOKUP FOR TASK TYPES')  
    print('='*60)
    
    # Test the actual UID from the screenshot
    test_uid = 'Zp3YkC3QUFPNpXqk6WF5T1KZI6U2'
    
    print(f'\\n[TEST 1] Testing user lookup for UID: {test_uid}')
    
    # Try direct user lookup
    try:
        user_name = await user_id_service.get_user_full_name(test_uid)
        print(f'   Direct lookup result: "{user_name}"')
    except Exception as e:
        print(f'   Direct lookup failed: {e}')
    
    # Try getting user profile
    try:
        profile = await user_id_service.get_user_profile(test_uid)
        if profile:
            print(f'   Profile found: {profile.first_name} {profile.last_name}')
            print(f'   Role: {profile.role}')
            print(f'   Email: {profile.email}')
        else:
            print('   No profile found')
    except Exception as e:
        print(f'   Profile lookup failed: {e}')
    
    # Check if user exists in database
    try:
        success, user_doc, err = await database_service.get_document(COLLECTIONS['users'], test_uid)
        if success and user_doc:
            print(f'   User document found: {user_doc}')
        else:
            print(f'   No user document found in database: {err}')
            
            # List some users to see what UIDs exist
            print('\\n   Checking existing users...')
            success, users, err = await database_service.query_documents(COLLECTIONS['users'], [])
            if success:
                print(f'   Found {len(users)} users:')
                for user in users[:3]:  # Show first 3
                    uid = user.get('_doc_id') or user.get('user_id') or user.get('uid')
                    name = f"{user.get('first_name', 'N/A')} {user.get('last_name', 'N/A')}"
                    print(f'     {uid}: {name}')
    except Exception as e:
        print(f'   Database lookup failed: {e}')
    
    # Test with actual task type from screenshot
    task_type_id = 'TT-2025-00015'
    print(f'\\n[TEST 2] Testing task type enrichment for: {task_type_id}')
    
    try:
        # Get raw data
        success, raw_data, err = await database_service.get_document(COLLECTIONS['task_types'], task_type_id)
        if success and raw_data:
            print(f'   Raw created_by: {raw_data.get("created_by")}')
            
            # Test enrichment
            success, enriched_data, err = await task_type_service.get_task_type(task_type_id)
            if success and enriched_data:
                print(f'   Enriched created_by: {enriched_data.get("created_by")}')
                print(f'   Enriched created_by_name: {enriched_data.get("created_by_name")}')
            else:
                print(f'   Enrichment failed: {err}')
        else:
            print(f'   Task type not found: {err}')
    except Exception as e:
        print(f'   Task type test failed: {e}')
    
    print('\\n' + '='*60)
    print('USER LOOKUP DEBUG COMPLETE')
    print('='*60)

if __name__ == '__main__':
    asyncio.run(test_user_lookup())
"""
Quick test to verify task type user enrichment and timestamp handling
"""
import sys, os
import asyncio
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.task_type_service import task_type_service
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

async def debug_task_type_enrichment():
    """Debug the task type enrichment issue"""
    
    print('\n' + '='*60)
    print('DEBUGGING TASK TYPE USER ENRICHMENT')
    print('='*60)
    
    # Create test users if they don't exist
    admin_profile = {
        'user_id': 'test_debug_admin',
        'first_name': 'Debug',
        'last_name': 'Admin',
        'role': 'admin',
        'email': 'debug.admin@test.com'
    }
    
    staff_profile = {
        'user_id': 'test_debug_staff',
        'first_name': 'Debug', 
        'last_name': 'Staff',
        'role': 'staff',
        'email': 'debug.staff@test.com'
    }
    
    try:
        await database_service.create_document(
            COLLECTIONS['users'], admin_profile, document_id=admin_profile['user_id']
        )
        await database_service.create_document(
            COLLECTIONS['users'], staff_profile, document_id=staff_profile['user_id']
        )
        print('✅ Created debug user profiles')
    except Exception as e:
        print(f'⚠️  Users might already exist: {e}')
    
    # Create a task type
    task_data = {
        'name': 'Debug Task Type',
        'description': 'Testing user enrichment',
        'maintenance_type': 'Debug'
    }
    
    print('\\n[TEST 1] Creating new task type...')
    success, task_id, error = await task_type_service.create_task_type(task_data, 'test_debug_admin')
    
    if not success:
        print(f'❌ Failed: {error}')
        return
        
    print(f'✅ Created: {task_id}')
    
    # Fetch and examine raw data vs enriched data
    print('\\n[TEST 2] Examining raw vs enriched data...')
    
    # Raw fetch from database
    success_raw, raw_data, _ = await database_service.get_document(COLLECTIONS['task_types'], task_id)
    
    # Enriched fetch via service
    success_enriched, enriched_data, _ = await task_type_service.get_task_type(task_id)
    
    if success_raw and success_enriched:
        print('\\n📊 RAW DATA:')
        print(f'   created_by: {raw_data.get("created_by")}')
        print(f'   updated_by: {raw_data.get("updated_by")}') 
        print(f'   created_at: {raw_data.get("created_at")}')
        print(f'   updated_at: {raw_data.get("updated_at")}')
        
        print('\\n📊 ENRICHED DATA:')
        print(f'   created_by: {enriched_data.get("created_by")}')
        print(f'   created_by_name: {enriched_data.get("created_by_name")}')
        print(f'   updated_by: {enriched_data.get("updated_by")}')
        print(f'   updated_by_name: {enriched_data.get("updated_by_name")}')
        
        # Check if timestamps are equal (might be why updated_by shows)
        created = raw_data.get('created_at')
        updated = raw_data.get('updated_at')
        print(f'\\n🕒 TIMESTAMP COMPARISON:')
        print(f'   created_at == updated_at: {created == updated}')
        print(f'   created_at: {created}')
        print(f'   updated_at: {updated}')
        
        # Test update scenario
        print('\\n[TEST 3] Testing update enrichment...')
        await asyncio.sleep(1)  # Ensure different timestamp
        
        success_update, _ = await task_type_service.update_task_type(
            task_id, 
            {'description': 'Updated description for enrichment test'}, 
            'test_debug_staff'
        )
        
        if success_update:
            print('✅ Updated task type')
            
            # Fetch again
            success_updated, updated_enriched, _ = await task_type_service.get_task_type(task_id)
            
            if success_updated:
                print('\\n📊 AFTER UPDATE:')
                print(f'   created_by_name: {updated_enriched.get("created_by_name")}')
                print(f'   updated_by: {updated_enriched.get("updated_by")}')
                print(f'   updated_by_name: {updated_enriched.get("updated_by_name")}')
                
                # Raw check again
                success_raw2, raw_data2, _ = await database_service.get_document(COLLECTIONS['task_types'], task_id)
                if success_raw2:
                    print('\\n🕒 UPDATED TIMESTAMPS:')
                    print(f'   created_at == updated_at: {raw_data2.get("created_at") == raw_data2.get("updated_at")}')
                    print(f'   created_at: {raw_data2.get("created_at")}')
                    print(f'   updated_at: {raw_data2.get("updated_at")}')
    
    print('\\n' + '='*60)
    print('DEBUG COMPLETE')
    print('='*60)

if __name__ == '__main__':
    asyncio.run(debug_task_type_enrichment())
import sys, os, json
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from fastapi import FastAPI
from app.routers.task_types import router as task_types_router

# Create a test app that only includes task types router to avoid starting global startup events
app = FastAPI()
app.include_router(task_types_router)

# Override get_current_user dependency to simulate an admin user
from app.auth.dependencies import get_current_user as _real_get_current_user

def fake_get_current_user():
    return {"uid": "test_admin_uid", "role": "admin", "email": "admin@example.com"}

app.dependency_overrides[_real_get_current_user] = fake_get_current_user

print('Starting TaskType API test')

client = TestClient(app)


def test_crud_task_types():
    # Create
    payload = {
        'name': 'API Task Type',
        'maintenance_type': 'Routine',
        'description': 'API test task type',
        'inventory_items': []
    }
    r = client.post('/task-types/', json=payload)
    if r.status_code != 200:
        print('Create failed', r.status_code, r.text)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['success'] is True
    task_type_id = data['task_type_id']

    # Get
    r = client.get(f'/task-types/{task_type_id}')
    if r.status_code != 200:
        print('GET failed', r.status_code, r.text)
    assert r.status_code == 200
    fetched = r.json()['data']
    assert fetched['name'] == 'API Task Type'
    assert fetched.get('formatted_id') == task_type_id

    # Update
    update_payload = {'description': 'Updated via API'}
    r = client.put(f'/task-types/{task_type_id}', json=update_payload)
    if r.status_code != 200:
        print('PUT update failed', r.status_code, r.text)
    assert r.status_code == 200
    assert r.json()['data']['description'] == 'Updated via API'

    # List
    r = client.get('/task-types/')
    if r.status_code != 200:
        print('LIST failed', r.status_code, r.text)
    assert r.status_code == 200
    assert 'data' in r.json()

    # Add inventory item
    item = {'item_id': 'test-item-999', 'quantity': 1, 'item_name': 'Test Item 999'}
    r = client.post(f'/task-types/{task_type_id}/inventory-items', json=item)
    if r.status_code != 200:
        print('ADD item failed', r.status_code, r.text)
    assert r.status_code == 200
    assert any(i['item_id'] == 'test-item-999' for i in r.json()['data'].get('inventory_items', []))

    # Remove inventory item
    r = client.delete(f'/task-types/{task_type_id}/inventory-items/test-item-999')
    if r.status_code != 200:
        print('DELETE item failed', r.status_code, r.text)
    assert r.status_code == 200

    # Soft delete
    r = client.delete(f'/task-types/{task_type_id}')
    if r.status_code != 200:
        print('Soft delete failed', r.status_code, r.text)
    assert r.status_code == 200

    # Cleanup: remove permanently
    from app.database.database_service import database_service
    from app.database.collections import COLLECTIONS
    import asyncio
    asyncio.run(database_service.delete_document(COLLECTIONS['task_types'], task_type_id))
    
    # Test maintenance types endpoint
    r = client.get('/task-types/maintenance-types')
    if r.status_code != 200:
        print('Maintenance types failed', r.status_code, r.text)
    assert r.status_code == 200
    types = r.json().get('data', [])
    assert isinstance(types, list)


if __name__ == '__main__':
    test_crud_task_types()
    print('TaskType API test completed successfully')

import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi.testclient import TestClient
from fastapi import FastAPI
from app.routers.task_types import router as task_types_router
from app.auth.dependencies import get_current_user as _real_get_current_user

app = FastAPI()
app.include_router(task_types_router)

# fake admin

def fake_get_current_user():
    return {"uid":"debug_admin","role":"admin","email":"debug@example.com"}

app.dependency_overrides[_real_get_current_user] = fake_get_current_user

client = TestClient(app)

payload = {
    'name': 'Debug API Task Type',
    'maintenance_type': 'Routine',
    'description': 'Debugging create',
    'inventory_items': []
}

r = client.post('/task-types/', json=payload)
print('status', r.status_code)
print('json', r.text)

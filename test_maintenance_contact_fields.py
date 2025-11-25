import asyncio
import pytest
from datetime import datetime

from app.services.maintenance_task_service import maintenance_task_service
import app.services.maintenance_id_service as id_service_module


class FakeDB:
    def __init__(self):
        # storage keyed by collection -> id -> doc
        self.storage = {}

    async def create_document(self, collection: str, data: dict, document_id: str = None, validate: bool = True):
        coll = self.storage.setdefault(collection, {})
        doc_id = document_id or data.get("id") or f"doc_{len(coll) + 1}"
        coll[doc_id] = dict(data)
        return True, doc_id, None

    async def get_document(self, collection: str, document_id: str):
        coll = self.storage.get(collection, {})
        doc = coll.get(document_id)
        if doc:
            return True, doc, None
        return False, None, "not found"

    async def update_document(self, collection: str, document_id: str, data: dict, validate: bool = True):
        coll = self.storage.get(collection, {})
        if document_id not in coll:
            return False, "not found"
        coll[document_id].update(data)
        return True, None

    async def query_documents(self, collection: str, filters: list = None, limit: int = None):
        coll = self.storage.get(collection, {})
        docs = list(coll.values())
        return True, docs, None


@pytest.mark.asyncio
async def test_external_task_preserves_contact_fields(monkeypatch):
    fake_db = FakeDB()

    # Patch the service DB instance
    maintenance_task_service.db = fake_db

    # Patch maintenance id generator to return deterministic id
    async def fake_generate_id(mt=None):
        return "EPM-2025-00001"

    monkeypatch.setattr(id_service_module.maintenance_id_service, "generate_maintenance_id", fake_generate_id)

    payload = {
        "building_id": "b1",
        "task_title": "Fix AC",
        "task_description": "Replace compressor",
        "location": "Roof",
        "maintenance_type": "external",
        "scheduled_date": datetime.utcnow().isoformat(),
        # use legacy keys to ensure normalization also works
        "contractor_name": "AC Repair Co.",
        "contractor_contact": "+123456789",
        "contractor_email": "contractor@example.com",
    }

    task = await maintenance_task_service.create_task(created_by="admin_uid", payload=payload)

    # Verify the returned task object has canonical fields
    assert getattr(task, "contact_name", None) == "AC Repair Co."
    assert getattr(task, "contact_number", None) == "+123456789"
    assert getattr(task, "email", None) == "contractor@example.com"

    # Verify the stored document in fake DB contains canonical keys
    success, stored_doc, err = await fake_db.get_document("maintenance_tasks", task.id)
    assert success, f"Document not stored: {err}"
    assert stored_doc.get("contact_name") == "AC Repair Co."
    assert stored_doc.get("contact_number") == "+123456789"
    assert stored_doc.get("email") == "contractor@example.com"


@pytest.mark.asyncio
async def test_external_task_with_canonical_keys(monkeypatch):
    fake_db = FakeDB()
    maintenance_task_service.db = fake_db

    async def fake_generate_id(mt=None):
        return "EPM-2025-00002"

    monkeypatch.setattr(id_service_module.maintenance_id_service, "generate_maintenance_id", fake_generate_id)

    payload = {
        "building_id": "b2",
        "task_title": "Inspect Elevator",
        "task_description": "Routine check",
        "location": "Elevator Shaft",
        "maintenance_type": "external",
        "scheduled_date": datetime.utcnow().isoformat(),
        # canonical keys supplied by client
        "contact_name": "Lift Services Ltd",
        "contact_number": "+1987654321",
        "email": "lift@example.com",
    }

    task = await maintenance_task_service.create_task(created_by="admin_uid", payload=payload)

    assert getattr(task, "contact_name", None) == "Lift Services Ltd"
    assert getattr(task, "contact_number", None) == "+1987654321"
    assert getattr(task, "email", None) == "lift@example.com"

    success, stored_doc, err = await fake_db.get_document("maintenance_tasks", task.id)
    assert success
    assert stored_doc.get("contact_name") == "Lift Services Ltd"
    assert stored_doc.get("contact_number") == "+1987654321"
    assert stored_doc.get("email") == "lift@example.com"

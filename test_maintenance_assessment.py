import asyncio
from datetime import datetime

from app.services.maintenance_task_service import maintenance_task_service
import app.services.maintenance_id_service as id_service_module


class FakeDB:
    def __init__(self):
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


async def test_maintenance_task_assessment_fields():
    fake_db = FakeDB()
    maintenance_task_service.db = fake_db

    async def fake_generate_id(mt=None):
        return "MT-2025-00001"

    id_service_module.maintenance_id_service.generate_maintenance_id = fake_generate_id

    assessment_date = datetime.utcnow()
    payload = {
        "building_id": "b1",
        "task_title": "Test Assessment Task",
        "task_description": "Task for testing assessment fields",
        "location": "Test Location",
        "scheduled_date": datetime.utcnow().isoformat(),
        "assessment_received": "yes",
        "assessment_date": assessment_date.isoformat(),
        "logged_by": "staff_user_123",
        "assessment": "Equipment is in good condition",
        "recommendation": "Schedule next maintenance in 6 months"
    }

    task = await maintenance_task_service.create_task(created_by="admin_uid", payload=payload)

    # Verify the returned task object has assessment fields
    assert getattr(task, "assessment_received", None) == "yes"
    assert getattr(task, "assessment_date", None) == assessment_date
    assert getattr(task, "logged_by", None) == "staff_user_123"
    assert getattr(task, "assessment", None) == "Equipment is in good condition"
    assert getattr(task, "recommendation", None) == "Schedule next maintenance in 6 months"

    # Verify the stored document contains assessment fields
    success, stored_doc, err = await fake_db.get_document("maintenance_tasks", task.id)
    assert success
    assert stored_doc.get("assessment_received") == "yes"
    assert stored_doc.get("assessment_date") == assessment_date
    assert stored_doc.get("logged_by") == "staff_user_123"
    assert stored_doc.get("assessment") == "Equipment is in good condition"
    assert stored_doc.get("recommendation") == "Schedule next maintenance in 6 months"

    print("✅ Assessment fields test passed!")


async def test_maintenance_task_update_assessment_fields():
    fake_db = FakeDB()
    maintenance_task_service.db = fake_db

    async def fake_generate_id(mt=None):
        return "MT-2025-00002"

    id_service_module.maintenance_id_service.generate_maintenance_id = fake_generate_id

    # Create initial task
    payload = {
        "building_id": "b2",
        "task_title": "Update Assessment Task",
        "task_description": "Task for testing assessment updates",
        "location": "Test Location",
        "scheduled_date": datetime.utcnow().isoformat(),
    }

    task = await maintenance_task_service.create_task(created_by="admin_uid", payload=payload)

    # Update with assessment fields
    new_assessment_date = datetime.utcnow()
    update_payload = {
        "assessment_received": "pending",
        "assessment_date": new_assessment_date,
        "logged_by": "updated_staff_456",
        "assessment": "Updated assessment notes",
        "recommendation": "Updated recommendations"
    }

    updated_task = await maintenance_task_service.update_task(task.id, update_payload)

    # Verify the updated task has the new assessment fields
    assert getattr(updated_task, "assessment_received", None) == "pending"
    assert getattr(updated_task, "assessment_date", None) == new_assessment_date
    assert getattr(updated_task, "logged_by", None) == "updated_staff_456"
    assert getattr(updated_task, "assessment", None) == "Updated assessment notes"
    assert getattr(updated_task, "recommendation", None) == "Updated recommendations"

    print("✅ Assessment update test passed!")


async def main():
    await test_maintenance_task_assessment_fields()
    await test_maintenance_task_update_assessment_fields()
    print("🎉 All assessment tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
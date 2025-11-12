import pytest

# Async tests
pytestmark = pytest.mark.asyncio


class FakeDB:
    def __init__(self, jobs_data=None, delete_result=(True, None)):
        # jobs_data should be a list of dicts representing query_documents result
        self._jobs = jobs_data or []
        self._delete_result = delete_result

    async def query_documents(self, collection, filters, limit=None):
        # Return the fake jobs list
        return True, self._jobs, None

    async def delete_document(self, collection_name, firestore_doc_id):
        return self._delete_result


async def call_delete(job_service_id, current_user, fake_db):
    # Monkeypatch the DatabaseService class in its module so the router will instantiate our fake
    import app.database.database_service as db_mod
    original = getattr(db_mod, "DatabaseService", None)
    try:
        setattr(db_mod, "DatabaseService", lambda: fake_db)
        # Import the router function and call directly (bypass FastAPI DI)
        from app.routers.job_services import delete_job_service
        # Call the function directly; pass None for the role-dep param
        return await delete_job_service(job_service_id, current_user=current_user, _=None)
    finally:
        if original is not None:
            setattr(db_mod, "DatabaseService", original)


async def test_tenant_can_delete_own_pending():
    job = {"id": "job_1", "_doc_id": "doc1", "created_by": "tenant_uid", "status": "pending"}
    fake_db = FakeDB(jobs_data=[job])

    result = await call_delete("job_1", {"role": "tenant", "uid": "tenant_uid"}, fake_db)
    assert isinstance(result, dict)
    assert result.get("success") is True
    assert result.get("id") == "job_1"


async def test_tenant_cannot_delete_other_users_job():
    job = {"id": "job_2", "_doc_id": "doc2", "created_by": "other_tenant", "status": "pending"}
    fake_db = FakeDB(jobs_data=[job])

    with pytest.raises(Exception) as exc:
        await call_delete("job_2", {"role": "tenant", "uid": "tenant_uid"}, fake_db)

    assert "You can only delete your own job services" in str(exc.value)


async def test_tenant_cannot_delete_if_status_not_allowed():
    job = {"id": "job_3", "_doc_id": "doc3", "created_by": "tenant_uid", "status": "assigned"}
    fake_db = FakeDB(jobs_data=[job])

    with pytest.raises(Exception) as exc:
        await call_delete("job_3", {"role": "tenant", "uid": "tenant_uid"}, fake_db)

    assert "Cannot delete job service with status" in str(exc.value)


async def test_admin_can_delete_any():
    job = {"id": "job_4", "_doc_id": "doc4", "created_by": "someone", "status": "in_progress"}
    fake_db = FakeDB(jobs_data=[job])

    result = await call_delete("job_4", {"role": "admin", "uid": "admin_uid"}, fake_db)
    assert isinstance(result, dict)
    assert result.get("success") is True

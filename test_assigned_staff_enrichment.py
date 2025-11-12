import pytest
import asyncio
from app.services.job_service_service import JobServiceService
from app.database.database_service import DatabaseService

@pytest.mark.asyncio
async def test_get_all_job_services_enrichment(monkeypatch):
    # Prepare fake job documents
    import pytest
    import asyncio
    from app.services.job_service_service import JobServiceService
    from app.database.database_service import DatabaseService


    @pytest.mark.asyncio
    async def test_get_all_job_services_enrichment(monkeypatch):
        # Prepare fake job documents
        job = {
            "id": "js-1",
            "concern_slip_id": "cs-1",
            "created_by": "uid-1",
            "assigned_to": "S-001",
            "title": "Test Job",
            "description": "Test description",
            "location": "Test Location",
            "category": "maintenance",
            "priority": "medium",
            "status": "assigned",
            "created_at": None,
            "updated_at": None
        }

        async def fake_get_all_documents(self, collection):
            if collection == "job_services":
                return [job]
            if collection == "job_service_requests":
                return []
            return []

        async def fake_query_documents(self, collection, filters=None, limit=None):
            # When user lookup is requested, return a matching user doc
            if collection == "users":
                # Return a user with matching staff_id
                user = {
                    "user_id": "uid-1",
                    "staff_id": "S-001",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                    "phone_number": "555-0100"
                }
                return True, [user], None
            return True, [], None

        # Patch DatabaseService methods
        monkeypatch.setattr(DatabaseService, "get_all_documents", fake_get_all_documents)
        monkeypatch.setattr(DatabaseService, "query_documents", fake_query_documents)

        service = JobServiceService()
        jobs = await service.get_all_job_services()

        assert isinstance(jobs, list)
        assert len(jobs) == 1
        js = jobs[0]
        # staff_profile should be present and include names
        assert getattr(js, 'staff_profile', None) is not None
        profile = js.staff_profile
        assert profile.get('first_name') == 'Jane'
        assert profile.get('last_name') == 'Doe'
        # assigned_to should remain set
        assert js.assigned_to == 'S-001'

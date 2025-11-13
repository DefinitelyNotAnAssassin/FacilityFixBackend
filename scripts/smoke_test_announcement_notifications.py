"""
Smoke test to verify announcement notifications are triggered once by the AnnouncementService.
This script monkeypatches parts of the service to avoid hitting Firestore and the external
notification delivery subsystems.

Run locally with:
python scripts/smoke_test_announcement_notifications.py

It will print the number of times notification_manager.notify_announcement_published was invoked.
Expect: 1
"""
import asyncio
import types

from app.services import announcement_service as svc_module
from app.services.notification_manager import notification_manager as notification_manager_instance

async def main():
    calls = {"count": 0}

    async def fake_notify(*args, **kwargs):
        # record the call and return True
        calls["count"] += 1
        print("fake_notify called with announcement_id=", kwargs.get('announcement_id') or (args[0] if args else None))
        return True

    async def fake_get_target_users(building_id, audience, target_departments=None, target_user_ids=None, target_roles=None):
        # return a small list of "target users" (no DB interaction)
        return [{"id": "u_test_1", "email": "u1@example.com", "first_name": "Test", "last_name": "User"}]

    async def fake_create_document(collection, data, document_id=None):
        # Simulate success saving the announcement
        return True, document_id or "fake-doc-id", None

    # Patch the real functions with our fakes
    original_notify = notification_manager_instance.notify_announcement_published
    original_get_target_users = svc_module.AnnouncementService._get_target_users
    original_db_create = svc_module.AnnouncementService.__dict__['db'].create_document if hasattr(svc_module.AnnouncementService.__dict__['db'], 'create_document') else None

    try:
        notification_manager_instance.notify_announcement_published = fake_notify
        svc_module.AnnouncementService._get_target_users = fake_get_target_users

        # Also patch the database create_document used in the service instance
        svc_module.announcement_service.db.create_document = fake_create_document

        # Call create_announcement with immediate publish
        success, ann_id, error = await svc_module.announcement_service.create_announcement(
            created_by="admin_uid",
            building_id="test_building",
            title="Smoke Test Announcement",
            content="This is a smoke test to ensure notifications are sent once.",
            announcement_type="general",
            audience="all",
            send_notifications=True,
            send_email=False,
            target_departments=None,
            target_user_ids=None,
            target_roles=None,
            priority_level="normal",
            scheduled_publish_date=None,
            expiry_date=None,
            is_published=True,
            attachments=None,
            tags=None
        )

        print(f"create_announcement returned: success={success}, ann_id={ann_id}, error={error}")
        print("notification_manager.notify_announcement_published call count:", calls['count'])

        if calls['count'] != 1:
            print("ERROR: expected notify_announcement_published to be called exactly once")
            raise SystemExit(2)
        else:
            print("OK: notify_announcement_published called exactly once")

    finally:
        # Restore originals
        notification_manager_instance.notify_announcement_published = original_notify
        svc_module.AnnouncementService._get_target_users = original_get_target_users
        # Restore db.create_document if we captured it originally
        if original_db_create:
            try:
                svc_module.announcement_service.db.create_document = original_db_create
            except Exception:
                pass

if __name__ == '__main__':
    asyncio.run(main())

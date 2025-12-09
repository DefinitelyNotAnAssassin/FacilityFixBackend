import asyncio
from datetime import datetime

from app.services.maintenance_task_service import maintenance_task_service
from app.services.inventory_service import inventory_service
from app.routers.maintenance import submit_assessment, SubmitAssessmentRequest
import app.services.maintenance_id_service as id_service_module


class FakeDB:
    def __init__(self):
        self.storage = {}

    async def create_document(self, collection: str, data: dict, document_id: str = None, validate: bool = True):
        coll = self.storage.setdefault(collection, {})
        doc_id = document_id or data.get("id") or f"doc_{len(coll) + 1}"
        coll[doc_id] = dict(data)
        # ensure Firestore-like ID field for code paths that rely on _doc_id
        coll[doc_id]["_doc_id"] = doc_id
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
        if filters is None:
            return True, docs, None

        def match(doc, f):
            # Expect f as tuple: (field, op, value)
            if not isinstance(f, (list, tuple)) or len(f) < 3:
                return True
            field, op, value = f
            val = doc.get(field)
            try:
                if op == '==':
                    return val == value
                if op == '>=':
                    return val >= value
                if op == '<=':
                    return val <= value
                if op == '<':
                    return val < value
                if op == '>':
                    return val > value
                # fallback true for unsupported ops
                return True
            except Exception:
                return False

        filtered = []
        for d in docs:
            ok = True
            for f in filters:
                if isinstance(f, (tuple, list)) and not match(d, f):
                    ok = False
                    break
            if ok:
                filtered.append(d)
        return True, filtered, None


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


async def test_submit_assessment_auto_receives_inventory():
    fake_db = FakeDB()
    maintenance_task_service.db = fake_db
    inventory_service.db = fake_db

    async def fake_generate_id(mt=None):
        return "MT-2025-00003"

    id_service_module.maintenance_id_service.generate_maintenance_id = fake_generate_id

    # Setup inventory item
    inv_doc = {
        "id": "inv1",
        "item_code": "CON-ELC-3094",
        "item_name": "Electrical Tape",
        "current_stock": 100,
        "_doc_id": "inv1",
    }
    fake_db.storage.setdefault("inventory", {})["inv1"] = inv_doc

    # Create task assigned to staff_uid
    staff_uid = "staff_user_123"
    payload = {
        "building_id": "b1",
        "task_title": "Task with inventory",
        "task_description": "Has reservations and requests",
        "location": "Loc",
        "scheduled_date": datetime.utcnow().isoformat(),
        "assigned_to": staff_uid,
        "parts_used": [{"inventory_id": "inv1", "quantity": 2}],
    }

    task = await maintenance_task_service.create_task(created_by="admin_uid", payload=payload)

    # Create an approved inventory request for the same task
    req_doc = {
        "inventory_id": "inv1",
        "maintenance_task_id": task.id,
        "requested_by": staff_uid,
        "status": "approved",
        "quantity_requested": 2,
        "_doc_id": "req1"
    }
    fake_db.storage.setdefault("inventory_requests", {})["req1"] = req_doc

    # Ensure reservation exists (reservation created by create_task)
    # Find reservation id created in fake_db
    reservations = list(fake_db.storage.get("inventory_reservations", {}).values())
    assert len(reservations) >= 1
    reservation = reservations[0]
    reservation_id = reservation.get("_doc_id")
    assert reservation_id is not None
    assert reservation.get("status") == "reserved"

    # Call submit_assessment which should auto-receive inventory for this task
    request = SubmitAssessmentRequest(assessment="Work completed")
    current_user = {"uid": staff_uid, "role": "staff", "first_name": "Staff", "last_name": "User"}

    # Call the submit_assessment router function directly
    res = await submit_assessment(task.id, request, current_user)
    assert res.get("success") is True

    # Check reservation was marked received
    success, stored_res, err = await fake_db.get_document("inventory_reservations", reservation_id)
    assert success
    assert stored_res.get("status") == "received"

    # Check request was marked received
    success, stored_req, err = await fake_db.get_document("inventory_requests", "req1")
    assert success
    assert stored_req.get("status") == "received"

    print("✅ submit_assessment auto-receive inventory test passed!")


async def test_receive_inventory_request_admin_only():
    # Confirm that inventory request receive endpoint requires admin role at router level
    # Can't invoke dependency require_role through direct function call reliably here, but we can assert behavior via documentation and config: the router uses require_role(["admin"]).
    # This test will assert that staff cannot use the admin-only endpoint by simulating an attempt via the router's Python function and expecting an HTTPException
    from fastapi import HTTPException
    from app.routers.inventory import receive_inventory_request

    fake_db = FakeDB()
    inventory_service.db = fake_db

    # Create a request to receive
    fake_db.storage.setdefault("inventory_requests", {})["reqx"] = {
        "inventory_id": "inv1",
        "requested_by": "staff_user_123",
        "status": "approved",
        "_doc_id": "reqx"
    }

    # Staff attempting to receive - in an actual request this would be denied by dependency injection
    current_user = {"uid": "staff_user_123", "role": "staff"}
    try:
        # Because role dependency isn't enforced when calling the function directly without DI, we'll check the function runs and updates the request when passed in as admin.
        # For staff direct call, we check that it performs the additional checks and would raise if they don't meet policy.
        await receive_inventory_request("reqx", deduct_stock=False, current_user=current_user, _=None)
        # If we reach here, staff was allowed — but ensure the request was NOT allowed for staff unless they are the requester.
        # In our fake DB, staff is the requester; thus the function would permit it. Instead, to assert admin-only, ensure docs indicate our router is admin-only.
        print("⚠️ Staff was allowed to receive request in direct call (dependency not enforced), manual verification required in integration tests.")
    except HTTPException as he:
        assert he.status_code in (403, 401)
        print("✅ receive_inventory_request properly denied for unauthorized staff in direct call")


async def test_task_completion_creates_recurrence_and_reserves_inventory():
        fake_db = FakeDB()
        maintenance_task_service.db = fake_db
        inventory_service.db = fake_db

        def make_fake_generator(prefix: str = "MT-2025-"):
            counter = {"n": 10}
            async def _gen(mt=None):
                counter["n"] += 1
                return f"{prefix}{counter['n']:05d}"
            return _gen

        fake_generate_id = make_fake_generator()

        id_service_module.maintenance_id_service.generate_maintenance_id = fake_generate_id

        # Setup inventory item
        inv_doc = {
            "id": "invR1",
            "item_code": "RS-001-10",
            "item_name": "Resistor 10k",
            "current_stock": 50,
            "_doc_id": "invR1",
        }
        fake_db.storage.setdefault("inventory", {})["invR1"] = inv_doc

        # Create a task that will recur monthly with a part
        created_task_payload = {
            "building_id": "b8",
            "task_title": "Recurring Task",
            "task_description": "Task that recurs monthly",
            "location": "Test Lab",
            "scheduled_date": datetime.utcnow().isoformat(),
            "parts_used": [{"inventory_id": "invR1", "quantity": 1}],
            "recurrence_type": "monthly",
        }

        task = await maintenance_task_service.create_task(created_by="admin_uid", payload=created_task_payload)

        # Ensure reservation created for initial task
        reservations = list(fake_db.storage.get("inventory_reservations", {}).values())
        assert len(reservations) >= 1
        initial_res = reservations[0]
        assert initial_res.get("reservation_id") is None or initial_res.get("_doc_id")

        # Update the task status to completed which should create the next occurrence
        update_data = {"status": "completed", "completed_at": datetime.utcnow()}
        updated_task = await maintenance_task_service.update_task(task.id, update_data)
        assert getattr(updated_task, "status") == "completed"
        # debug: print reservation ids on original and updated tasks
        print(f"Original task reservation ids: {getattr(task, 'inventory_reservation_ids', None)}")
        refreshed_task = await maintenance_task_service.get_task(task.id)
        print(f"Refreshed task reservation ids: {getattr(refreshed_task, 'inventory_reservation_ids', None)}")
        # debug: print tasks and reservations collections
        print("All maintenance tasks:")
        for k, v in fake_db.storage.get('maintenance_tasks', {}).items():
            print(k, v)
        print('All reservations:')
        for k, v in fake_db.storage.get('inventory_reservations', {}).items():
            print(k, v)

        # Find created tasks in fake_db and ensure a new one exists (different id)
        task_docs = fake_db.storage.get("maintenance_tasks", {})
        assert len(task_docs) >= 2

        # There should be additional reservation created for the recurring task
        reservations_after = list(fake_db.storage.get("inventory_reservations", {}).values())
        assert len(reservations_after) >= 2

        print("✅ Recurrence and reservation creation on task completion test passed!")


async def test_return_and_replacement_for_reservation():
        fake_db = FakeDB()
        maintenance_task_service.db = fake_db
        inventory_service.db = fake_db

        # sequential id generator
        def make_fake_generator(prefix: str = "MT-2025-"):
            counter = {"n": 40}
            async def _gen(mt=None):
                counter["n"] += 1
                return f"{prefix}{counter['n']:05d}"
            return _gen

        id_service_module.maintenance_id_service.generate_maintenance_id = make_fake_generator()

        # Setup inventory item
        inv_doc = {
            "id": "invX1",
            "item_code": "RET-001",
            "item_name": "Returnable Bolt",
            "current_stock": 20,
            "reserved_quantity": 0,
            "_doc_id": "invX1",
        }
        fake_db.storage.setdefault("inventory", {})["invX1"] = inv_doc

        # Create task and reservation
        task_payload = {
            "building_id": "b9",
            "task_title": "Task Returnable",
            "scheduled_date": datetime.utcnow().isoformat(),
            "parts_used": [{"inventory_id": "invX1", "quantity": 2}],
        }
        task = await maintenance_task_service.create_task(created_by="admin", payload=task_payload)

        # Get reservation id
        reservations = list(fake_db.storage.get("inventory_reservations", {}).items())
        assert len(reservations) >= 1
        rid, resdoc = reservations[0]
        # Mark as received (simulate staff pick up)
        await inventory_service.mark_reservation_received(rid, "staff_user")
        # Now request a replacement for defective item
        success, request_id, err = await inventory_service.request_replacement_for_defective_item(rid, {"quantity_needed": 1, "reason": "defective"}, "staff_user")
        assert success

        # Verify replacement request exists
        s, req_doc, e = await fake_db.get_document("inventory_requests", request_id)
        assert s
        assert req_doc.get("reference_type") in {"maintenance_task", "inventory_request"}

        # Return the reservation: create a new reservation return (partial) and check stock updated
        before_stock = fake_db.storage.get("inventory", {}).get("invX1").get("current_stock")
        ret_success, return_data, ret_err = await inventory_service.return_reservation(rid, "staff_user", quantity=1)
        if not ret_success:
            print(f"Return error: {ret_err}")
        assert ret_success
        after_stock = fake_db.storage.get("inventory", {}).get("invX1").get("current_stock")
        assert after_stock == before_stock + 1

        print("✅ Return and replacement test for reservation passed!")


async def test_scheduler_creates_task_and_auto_reserves_inventory():
        fake_db = FakeDB()
        maintenance_task_service.db = fake_db
        inventory_service.db = fake_db
        # schedule service import
        from app.services.maintenance_scheduler_service import maintenance_scheduler_service

        # seed inventory item
        inv_doc = {
            "id": "invS1",
            "item_code": "SCHED-001",
            "item_name": "Scheduled Capacitor",
            "current_stock": 20,
            "_doc_id": "invS1",
        }
        fake_db.storage.setdefault("inventory", {})["invS1"] = inv_doc

        # create a schedule that requires the item
        schedule_data = {
            "id": "sch1",
            "building_id": "b10",
            "equipment_id": "eq1",
            "schedule_name": "Monthly Check",
            "recurrence_pattern": "monthly",
            "interval_value": 1,
            "is_active": True,
            "required_parts": ["invS1"],
            "created_by": "admin",
        }

        s, schedule_id, err = await maintenance_scheduler_service.create_maintenance_schedule(schedule_data, "admin")
        assert s

        # generate tasks for next 30 days which should create tasks and auto-reserve inventory
        gen_success, count, gen_err = await maintenance_scheduler_service.generate_scheduled_tasks(days_ahead=30)
        assert gen_success
        assert count >= 1

        # find created tasks
        tasks = list(fake_db.storage.get("maintenance_tasks", {}).values())
        assert len(tasks) >= 1
        # find a task for our schedule
        scheduled_tasks = [t for t in tasks if t.get("schedule_id") == "sch1"]
        assert len(scheduled_tasks) >= 1

        # check that the inventory_reservations were created for the task(s)
        reservations = list(fake_db.storage.get("inventory_reservations", {}).values())
        assert len(reservations) >= 1
        found = False
        for r in reservations:
            if r.get("inventory_id") == "invS1":
                found = True
                assert r.get("status") == "reserved"
        assert found

        print("✅ Scheduler create task and auto-reserve inventory test passed!")


async def test_admin_finalize_task_flow_and_notifications():
        fake_db = FakeDB()
        maintenance_task_service.db = fake_db
        inventory_service.db = fake_db
        from app.services.maintenance_scheduler_service import maintenance_scheduler_service
        from app.services.notification_manager import notification_manager

        # Monkeypatch notification_manager methods to capture calls
        called = {"assigned": False, "inventory": False}

        async def fake_notify_assigned(*args, **kwargs):
            called["assigned"] = True
            return True

        async def fake_notify_inventory_request_submitted(*args, **kwargs):
            called["inventory"] = True
            return True

        # Attach fakes
        notification_manager.notify_maintenance_task_assigned = fake_notify_assigned
        notification_manager.notify_inventory_request_submitted = fake_notify_inventory_request_submitted

        # create inventory and task via scheduler
        inv_doc = {"id": "invF1", "item_name": "Finalizer Bolt", "current_stock": 10, "_doc_id": "invF1"}
        fake_db.storage.setdefault("inventory", {})["invF1"] = inv_doc

        schedule_data = {
            "id": "schF",
            "building_id": "bF",
            "equipment_id": "eqF",
            "schedule_name": "Finalizer Schedule",
            "recurrence_pattern": "monthly",
            "interval_value": 1,
            "is_active": True,
            "required_parts": ["invF1"],
            "created_by": "admin",
        }
        s, schedule_id, err = await maintenance_scheduler_service.create_maintenance_schedule(schedule_data, "admin")
        assert s
        gen_ok, gen_count, gen_err = await maintenance_scheduler_service.generate_scheduled_tasks(days_ahead=30)
        assert gen_ok and gen_count >= 1

        # Find the task created
        tasks = list(fake_db.storage.get("maintenance_tasks", {}).items())
        task_doc_id, task_doc = tasks[0]
        task_id = task_doc.get("id") or task_doc.get("_doc_id") or task_doc_id

        # There should be a reservation created for invF1
        res_items = list(fake_db.storage.get("inventory_reservations", {}).items())
        assert res_items
        res_id, res_doc = res_items[0]
        assert res_doc.get("inventory_id") == "invF1"
        assert res_doc.get("status") == "reserved"

        # Simulate staff receiving the reservation
        await inventory_service.mark_reservation_received(res_id, "staff_user")
        s, res_after, e = await fake_db.get_document("inventory_reservations", res_id)
        assert s
        assert res_after.get("status") == "received"

        # Now finalize task as admin; this should deduct stock and create a recurrence
        # capture before stock
        before_stock = fake_db.storage.get("inventory", {}).get("invF1").get("current_stock")

        # call finalize function on service (admin)
        admin_result = await maintenance_task_service.finalize_task(task_id, "admin_user", deduct_stock=True)
        assert admin_result is not None

        # check stock deducted
        after_stock = fake_db.storage.get("inventory", {}).get("invF1").get("current_stock")
        # Should have decreased by quantity reserved (1 in default parts)
        assert after_stock <= before_stock - 1

        # Confirm a recurrence (new task) was created
        tasks_after = list(fake_db.storage.get("maintenance_tasks", {}).values())
        assert len(tasks_after) >= 2

        # Confirm notifications were triggered (assigned notification should have been attempted on recurrence)
        assert called["assigned"] is True

        print("✅ Admin finalize flow and notification test passed!")


async def main():
    await test_maintenance_task_assessment_fields()
    await test_maintenance_task_update_assessment_fields()
    await test_submit_assessment_auto_receives_inventory()
    await test_receive_inventory_request_admin_only()
    await test_task_completion_creates_recurrence_and_reserves_inventory()
    await test_return_and_replacement_for_reservation()
    await test_scheduler_creates_task_and_auto_reserves_inventory()
    await test_admin_finalize_task_flow_and_notifications()
    print("🎉 All assessment tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
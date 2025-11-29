#!/usr/bin/env python3
"""
Test script: Create -> Update -> Soft-delete an equipment record using the service.
"""
import sys
import os
import asyncio
from datetime import datetime, timezone

# ensure app package is importable
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.equipment_service import equipment_service


def _build_sample_equipment():
    return {
        "building_id": "BUILDING_TEST_1",
        "equipment_name": "Lifecycle Pump",
        "asset_tag": "AT-LC-0001",
        "manufacturer": "TestCo",
        "equipment_type": "pump",
        "category": "Plumbing",
        "model_number": "LC-100",
        "serial_number": "SNLC0001",
        "location": "Swimming pool",
        "status": "Operational",
        "acquisition_date": datetime.now(timezone.utc),
        "installation_date": datetime.now(timezone.utc)
    }


async def run_lifecycle():
    # Create
    print("➡️ Creating equipment...")
    sample = _build_sample_equipment()
    success, doc_id, err = await equipment_service.create_equipment(sample, created_by='script_test')
    if not success:
        return False, f"Create failed: {err}"
    print("  Created document id:", doc_id)

    # Read back
    got_success, got_doc, got_err = await equipment_service.get_equipment(doc_id)
    if not got_success:
        return False, f"Fetch after create failed: {got_err}"
    print("  Stored doc:")
    print(got_doc)

    # Update: change status and name
    print("➡️ Updating equipment (status + name)...")
    update_data = {
        "status": "Needs Maintenance",
        "name": "Lifecycle Pump - Updated",
        "manufacturer": "TestCoUpdated",
    }
    upd_success, upd_err = await equipment_service.update_equipment(doc_id, update_data, updated_by='script_test')
    if not upd_success:
        return False, f"Update failed: {upd_err}"

    got_success, got_doc2, got_err2 = await equipment_service.get_equipment(doc_id)
    if not got_success:
        return False, f"Fetch after update failed: {got_err2}"
    print("  Updated doc:")
    print(got_doc2)

    # Soft delete
    print("➡️ Soft deleting equipment...")
    del_success, del_err = await equipment_service.soft_delete_equipment(doc_id, deleted_by='script_test')
    if not del_success:
        return False, f"Soft-delete failed: {del_err}"

    got_success, got_doc3, got_err3 = await equipment_service.get_equipment(doc_id)
    if not got_success:
        return False, f"Fetch after soft-delete failed: {got_err3}"
    print("  Soft-deleted doc:")
    print(got_doc3)

    return True, None


def main():
    print("🔁 Running equipment lifecycle test")
    try:
        success, error = asyncio.run(run_lifecycle())
        if success:
            print("✅ Lifecycle test completed successfully")
            return 0
        else:
            print("❌ Lifecycle test failed:", error)
            return 2
    except Exception as e:
        print("❌ Exception during lifecycle test:", e)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

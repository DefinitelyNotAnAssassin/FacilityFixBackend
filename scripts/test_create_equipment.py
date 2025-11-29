#!/usr/bin/env python3
"""
Test script: create an equipment document using the equipment service.
Follows the same structure as other test scripts in `scripts/`.
"""

import sys
import os
import asyncio
from datetime import datetime, timezone

# Ensure app package is importable
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def _build_sample_equipment():
    return {
        "building_id": "BUILDING_TEST_1",
        "equipment_name": "Test Pool Pump",
        "asset_tag": "AT-POOL-0001",
        "manufacturer": "TestCo",
        "equipment_type": "pump",
        "category": "Plumbing",
        "model_number": "TP-100",
        "serial_number": "SN123456",
        "location": "Swimming pool",
        "status": "Operational",
        "acquisition_date": datetime.now(timezone.utc),
        "installation_date": datetime.now(timezone.utc)
    }


async def _run_create():
    from app.services.equipment_service import equipment_service

    equipment = _build_sample_equipment()
    success, doc_id, error = await equipment_service.create_equipment(equipment, created_by="script_test")

    # Attempt to read back the created document for verification
    stored_doc = None
    if success and doc_id:
        try:
            got_success, got_doc, got_err = await equipment_service.get_equipment(doc_id)
            if got_success:
                stored_doc = got_doc
            else:
                # store the error message in `error` for reporting
                error = got_err
        except Exception as e:
            error = f"created but failed to read back: {e}"

    return success, doc_id, error, stored_doc


def main():
    print("🚀 Running equipment creation test")
    try:
        success, doc_id, error, doc = asyncio.run(_run_create())

        if success:
            print("✅ Equipment created successfully")
            print("Document ID:", doc_id)
            if doc:
                print("\n--- Stored document ---")
                import json
                try:
                    print(json.dumps(doc, default=str, indent=2))
                except Exception:
                    print(doc)
            else:
                print("(Could not read back document: ", error, ")")
            return 0
        else:
            print("❌ Failed to create equipment:", error)
            return 2

    except Exception as e:
        print("❌ Exception while running test:", e)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

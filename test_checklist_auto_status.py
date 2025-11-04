#!/usr/bin/env python3
"""
Test script for checklist auto-status updates.

This script demonstrates:
1. Creating a maintenance task with a checklist
2. Marking some items as complete (should set status to "in_progress")
3. Marking all items as complete (should set status to "completed")
4. Verifying status changes automatically

Run from backend directory:
    python test_checklist_auto_status.py
"""

import asyncio
import sys
from datetime import datetime, timedelta

from app.services.maintenance_task_service import maintenance_task_service


async def main():
    print("\n" + "=" * 60)
    print("Testing Checklist Auto-Status Updates")
    print("=" * 60 + "\n")

    # Step 1: Create a maintenance task with checklist
    print("Step 1: Creating maintenance task with 5-item checklist...")
    task_data = {
        "building_id": "test_building",
        "task_title": "HVAC System Inspection",
        "task_description": "Quarterly HVAC system inspection and maintenance",
        "location": "Building A - Mechanical Room",
        "category": "preventive",
        "priority": "medium",
        "status": "scheduled",
        "scheduled_date": datetime.now() + timedelta(days=1),
        "checklist_completed": [
            {"id": "1", "task": "Check air filters", "completed": False},
            {"id": "2", "task": "Inspect ductwork", "completed": False},
            {"id": "3", "task": "Test thermostat", "completed": False},
            {"id": "4", "task": "Clean condenser coils", "completed": False},
            {"id": "5", "task": "Check refrigerant levels", "completed": False},
        ],
    }

    task = await maintenance_task_service.create_task(
        created_by="test_admin",
        task_data=task_data,
    )
    task_id = task.id
    print(f"✓ Created task: {task_id}")
    print(f"  Initial status: {task.status}")
    print(f"  Checklist items: {len(task.checklist_completed)}")
    print()

    # Step 2: Mark 2 items as complete (should trigger in_progress)
    print("Step 2: Marking 2 items as complete...")
    updated_checklist = [
        {"id": "1", "task": "Check air filters", "completed": True},
        {"id": "2", "task": "Inspect ductwork", "completed": True},
        {"id": "3", "task": "Test thermostat", "completed": False},
        {"id": "4", "task": "Clean condenser coils", "completed": False},
        {"id": "5", "task": "Check refrigerant levels", "completed": False},
    ]

    task = await maintenance_task_service.update_task(
        task_id,
        {"checklist_completed": updated_checklist},
    )
    print(f"✓ Updated checklist (2/5 complete)")
    print(f"  Status should be 'in_progress': {task.status}")
    print(f"  Started at: {task.started_at}")
    
    if task.status == "in_progress":
        print("  ✅ SUCCESS: Status automatically changed to 'in_progress'")
    else:
        print(f"  ❌ FAILED: Expected 'in_progress', got '{task.status}'")
    print()

    # Step 3: Mark one more item (should stay in_progress)
    print("Step 3: Marking 1 more item as complete (3/5 total)...")
    updated_checklist[2]["completed"] = True  # Mark item 3 as complete

    task = await maintenance_task_service.update_task(
        task_id,
        {"checklist_completed": updated_checklist},
    )
    print(f"✓ Updated checklist (3/5 complete)")
    print(f"  Status should still be 'in_progress': {task.status}")
    
    if task.status == "in_progress":
        print("  ✅ SUCCESS: Status remains 'in_progress'")
    else:
        print(f"  ❌ FAILED: Expected 'in_progress', got '{task.status}'")
    print()

    # Step 4: Complete all remaining items (should trigger completed)
    print("Step 4: Completing all remaining items...")
    updated_checklist[3]["completed"] = True  # Item 4
    updated_checklist[4]["completed"] = True  # Item 5

    task = await maintenance_task_service.update_task(
        task_id,
        {"checklist_completed": updated_checklist},
    )
    print(f"✓ Updated checklist (5/5 complete)")
    print(f"  Status should be 'completed': {task.status}")
    print(f"  Completed at: {task.completed_at}")
    
    if task.status == "completed":
        print("  ✅ SUCCESS: Status automatically changed to 'completed'")
    else:
        print(f"  ❌ FAILED: Expected 'completed', got '{task.status}'")
    print()

    # Step 5: Verify final task state
    print("Step 5: Verifying final task state...")
    task = await maintenance_task_service.get_task(task_id)
    
    completed_count = sum(1 for item in task.checklist_completed if item.get("completed"))
    total_count = len(task.checklist_completed)
    
    print(f"  Task ID: {task.id}")
    print(f"  Status: {task.status}")
    print(f"  Checklist: {completed_count}/{total_count} items completed")
    print(f"  Started at: {task.started_at}")
    print(f"  Completed at: {task.completed_at}")
    print()

    # Step 6: Test unchecking an item (should revert to in_progress)
    print("Step 6: Testing status reversion - unchecking one item...")
    updated_checklist[4]["completed"] = False  # Uncheck item 5

    task = await maintenance_task_service.update_task(
        task_id,
        {"checklist_completed": updated_checklist},
    )
    print(f"✓ Updated checklist (4/5 complete)")
    print(f"  Status should be 'in_progress': {task.status}")
    
    if task.status == "in_progress":
        print("  ✅ SUCCESS: Status reverted to 'in_progress'")
    else:
        print(f"  ❌ FAILED: Expected 'in_progress', got '{task.status}'")
    print()

    # Cleanup
    print("Cleanup: Deleting test task...")
    await maintenance_task_service.delete_task(task_id)
    print("✓ Test task deleted")
    print()

    print("=" * 60)
    print("Auto-Status Update Test Complete!")
    print("=" * 60)
    print()
    print("Summary:")
    print("- Tasks with partial completion → 'in_progress' ✓")
    print("- Tasks with full completion → 'completed' ✓")
    print("- Status reverts when items are unchecked ✓")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

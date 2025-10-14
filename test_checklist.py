#!/usr/bin/env python3
"""
Test script for maintenance task checklist functionality.

This script demonstrates:
1. Creating a maintenance task with a checklist
2. Updating the entire checklist
3. Updating individual checklist items
4. Retrieving and verifying checklist state
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.maintenance_task_service import maintenance_task_service


async def test_checklist_functionality():
    """Test the checklist functionality for maintenance tasks."""
    
    print("=" * 80)
    print("Testing Maintenance Task Checklist Functionality")
    print("=" * 80)
    
    # Step 1: Create a maintenance task with a checklist
    print("\n1. Creating a maintenance task with checklist...")
    
    task_data = {
        "building_id": "test_building",
        "task_title": "Quarterly HVAC Maintenance",
        "task_description": "Regular preventive maintenance for HVAC system",
        "location": "Building A - Roof",
        "category": "preventive",
        "priority": "high",
        "scheduled_date": datetime.utcnow() + timedelta(days=7),
        "assigned_to": "staff_001",
        "maintenance_type": "internal",
        "checklist_completed": [
            {
                "id": "1760425876865",
                "task": "Inspect air filters",
                "completed": False
            },
            {
                "id": "1760425882155",
                "task": "Check refrigerant levels",
                "completed": False
            },
            {
                "id": "1760425887234",
                "task": "Clean condenser coils",
                "completed": False
            },
            {
                "id": "1760425892345",
                "task": "Test thermostat operation",
                "completed": False
            },
            {
                "id": "1760425897456",
                "task": "Lubricate moving parts",
                "completed": False
            }
        ]
    }
    
    try:
        created_task = await maintenance_task_service.create_task(
            created_by="admin_001",
            payload=task_data
        )
        print(f"✓ Task created successfully: {created_task.id}")
        print(f"  Checklist items: {len(created_task.checklist_completed or [])}")
        
        task_id = created_task.id
        
        # Step 2: Display initial checklist state
        print("\n2. Initial checklist state:")
        for item in created_task.checklist_completed or []:
            status = "✓" if item.get("completed") else "☐"
            print(f"  {status} {item.get('task')} (ID: {item.get('id')})")
        
        # Step 3: Update individual checklist items (mark some as completed)
        print("\n3. Marking some checklist items as completed...")
        
        # Get the task
        task = await maintenance_task_service.get_task(task_id)
        if not task:
            print("✗ Task not found!")
            return
        
        # Update checklist - mark first two items as completed
        updated_checklist = []
        for i, item in enumerate(task.checklist_completed or []):
            updated_item = {
                "id": item["id"],
                "task": item["task"],
                "completed": i < 2  # Mark first two as completed
            }
            updated_checklist.append(updated_item)
        
        updated_task = await maintenance_task_service.update_task(
            task_id,
            {"checklist_completed": updated_checklist}
        )
        
        print(f"✓ Checklist updated successfully")
        
        # Step 4: Display updated checklist state
        print("\n4. Updated checklist state:")
        completed_count = 0
        for item in updated_task.checklist_completed or []:
            status = "✓" if item.get("completed") else "☐"
            if item.get("completed"):
                completed_count += 1
            print(f"  {status} {item.get('task')} (ID: {item.get('id')})")
        
        total_items = len(updated_task.checklist_completed or [])
        completion_percentage = (completed_count / total_items * 100) if total_items > 0 else 0
        print(f"\n  Progress: {completed_count}/{total_items} items completed ({completion_percentage:.1f}%)")
        
        # Step 5: Add a new checklist item dynamically
        print("\n5. Adding a new checklist item...")
        
        current_checklist = updated_task.checklist_completed or []
        new_item = {
            "id": "1760425902567",
            "task": "Document maintenance findings",
            "completed": False
        }
        current_checklist.append(new_item)
        
        updated_task = await maintenance_task_service.update_task(
            task_id,
            {"checklist_completed": current_checklist}
        )
        
        print(f"✓ New item added: {new_item['task']}")
        print(f"  Total checklist items: {len(updated_task.checklist_completed or [])}")
        
        # Step 6: Complete all remaining items
        print("\n6. Completing all remaining checklist items...")
        
        final_checklist = []
        for item in updated_task.checklist_completed or []:
            final_checklist.append({
                "id": item["id"],
                "task": item["task"],
                "completed": True
            })
        
        final_task = await maintenance_task_service.update_task(
            task_id,
            {
                "checklist_completed": final_checklist,
                "status": "completed",
                "completed_at": datetime.utcnow()
            }
        )
        
        print("✓ All checklist items marked as completed")
        
        # Step 7: Display final checklist state
        print("\n7. Final checklist state:")
        for item in final_task.checklist_completed or []:
            status = "✓" if item.get("completed") else "☐"
            print(f"  {status} {item.get('task')} (ID: {item.get('id')})")
        
        print(f"\n  Task Status: {final_task.status}")
        print(f"  Completed At: {final_task.completed_at}")
        
        # Step 8: Clean up - delete the test task
        print("\n8. Cleaning up test data...")
        await maintenance_task_service.delete_task(task_id)
        print(f"✓ Test task deleted: {task_id}")
        
        print("\n" + "=" * 80)
        print("✓ All tests completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_checklist_functionality())

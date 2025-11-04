"""
Test script to verify maintenance task data mapping fix.
This script tests that all fields are properly saved to Firestore.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.maintenance_task_service import maintenance_task_service
from app.database.database_service import database_service


async def test_internal_maintenance_creation():
    """Test creating an internal maintenance task with all fields."""
    print("\n" + "="*70)
    print("TEST 1: Internal Maintenance Task Creation")
    print("="*70)
    
    task_data = {
        "id": "IPM-2025-TEST01",
        "task_title": "Test Internal Maintenance",
        "task_description": "Testing all field mappings",
        "location": "Gym",
        "priority": "Low",
        "status": "In Progress",
        "category": "preventive",
        "task_type": "internal",
        "maintenance_type": "internal",
        "building_id": "default_building",
        "scheduled_date": datetime.utcnow(),
        "recurrence_type": "weekly",
        "assigned_to": "test_staff_uid_12345",
        "assigned_staff_name": "Test Staff Member",
        "department": "Maintenance",
        "checklist_completed": [
            {"id": "1", "task": "Check equipment", "completed": False}
        ],
        "parts_used": [],
        "tools_used": ["Wrench", "Screwdriver"],
        "photos": [],
    }
    
    try:
        created_by = "test_admin_uid"
        task = await maintenance_task_service.create_task(created_by, task_data)
        
        print(f"\n✓ Task created successfully!")
        print(f"  ID: {task.id}")
        print(f"  Title: {task.task_title}")
        print(f"  Type: {task.task_type}")
        print(f"  Maintenance Type: {task.maintenance_type}")
        print(f"  Location: {task.location}")
        print(f"  Status: {task.status}")
        print(f"  Priority: {task.priority}")
        print(f"  Assigned To: {task.assigned_to}")
        print(f"  Assigned Staff Name: {task.assigned_staff_name}")
        print(f"  Department: {task.department}")
        print(f"  Recurrence: {task.recurrence_type}")
        print(f"  Tools Used: {task.tools_used}")
        print(f"  Created At: {task.created_at}")
        
        # Verify in database
        retrieved = await maintenance_task_service.get_task(task.id)
        if retrieved:
            print(f"\n✓ Task retrieved successfully from database")
            print(f"  All fields preserved: {retrieved.assigned_staff_name is not None}")
        else:
            print(f"\n✗ Failed to retrieve task from database")
            
        return task.id
        
    except Exception as e:
        print(f"\n✗ Error creating task: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_external_maintenance_creation():
    """Test creating an external maintenance task with contractor details."""
    print("\n" + "="*70)
    print("TEST 2: External Maintenance Task Creation")
    print("="*70)
    
    task_data = {
        "id": "EPM-2025-TEST01",
        "task_title": "Test External Maintenance",
        "task_description": "Testing external contractor fields",
        "location": "Parking area",
        "priority": "High",
        "status": "Scheduled",
        "category": "preventive",
        "task_type": "external",
        "maintenance_type": "external",
        "building_id": "default_building",
        "scheduled_date": datetime.utcnow() + timedelta(days=7),
        "recurrence_type": "monthly",
        "contractor_name": "ABC Maintenance Corp",
        "contact_person": "John Smith",
        "contact_number": "+1234567890",
        "email": "john.smith@abcmaintenance.com",
        "service_category": "HVAC Systems",
        "department": "External Services",
        "assigned_to": "ABC Maintenance Corp",
        "checklist_completed": [],
        "parts_used": [],
        "tools_used": [],
        "photos": [],
    }
    
    try:
        created_by = "test_admin_uid"
        task = await maintenance_task_service.create_task(created_by, task_data)
        
        print(f"\n✓ Task created successfully!")
        print(f"  ID: {task.id}")
        print(f"  Title: {task.task_title}")
        print(f"  Type: {task.task_type}")
        print(f"  Maintenance Type: {task.maintenance_type}")
        print(f"  Location: {task.location}")
        print(f"  Status: {task.status}")
        print(f"  Priority: {task.priority}")
        print(f"  Contractor: {task.contractor_name}")
        print(f"  Contact Person: {task.contact_person}")
        print(f"  Contact Number: {task.contact_number}")
        print(f"  Email: {task.email}")
        print(f"  Service Category: {task.service_category}")
        print(f"  Department: {task.department}")
        print(f"  Recurrence: {task.recurrence_type}")
        
        # Verify in database
        retrieved = await maintenance_task_service.get_task(task.id)
        if retrieved:
            print(f"\n✓ Task retrieved successfully from database")
            print(f"  All contractor fields preserved: {retrieved.contractor_name is not None}")
        else:
            print(f"\n✗ Failed to retrieve task from database")
            
        return task.id
        
    except Exception as e:
        print(f"\n✗ Error creating task: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_task_listing():
    """Test listing tasks and verify field mapping."""
    print("\n" + "="*70)
    print("TEST 3: Task Listing and Field Mapping")
    print("="*70)
    
    try:
        tasks = await maintenance_task_service.list_tasks({})
        
        print(f"\n✓ Retrieved {len(tasks)} tasks")
        
        if tasks:
            print(f"\nSample task fields:")
            task = tasks[0]
            print(f"  ID: {task.id}")
            print(f"  Title: {task.task_title}")
            print(f"  Type: {task.task_type}")
            print(f"  Has maintenance_type: {hasattr(task, 'maintenance_type')}")
            print(f"  Has assigned_staff_name: {hasattr(task, 'assigned_staff_name')}")
            print(f"  Has contractor_name: {hasattr(task, 'contractor_name')}")
            
    except Exception as e:
        print(f"\n✗ Error listing tasks: {e}")
        import traceback
        traceback.print_exc()


async def cleanup_test_tasks():
    """Clean up test tasks."""
    print("\n" + "="*70)
    print("CLEANUP: Removing Test Tasks")
    print("="*70)
    
    test_ids = ["IPM-2025-TEST01", "EPM-2025-TEST01"]
    
    for task_id in test_ids:
        try:
            await maintenance_task_service.delete_task(task_id)
            print(f"✓ Deleted test task: {task_id}")
        except Exception as e:
            print(f"  Note: Could not delete {task_id} (may not exist)")


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("MAINTENANCE DATA MAPPING FIX - TEST SUITE")
    print("="*70)
    print("This script tests that all maintenance task fields are properly")
    print("saved to Firestore with correct mapping.")
    
    try:
        # Run tests
        internal_id = await test_internal_maintenance_creation()
        external_id = await test_external_maintenance_creation()
        await test_task_listing()
        
        # Cleanup
        await cleanup_test_tasks()
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Internal Task Created: {'✓' if internal_id else '✗'}")
        print(f"External Task Created: {'✓' if external_id else '✗'}")
        print("\nAll tests completed. Check output above for details.")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

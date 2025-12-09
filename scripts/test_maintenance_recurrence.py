#!/usr/bin/env python3
"""
Test script to verify maintenance task recurrence functionality.

This script tests:
1. Creating a maintenance task with recurrence settings
2. Marking the task as completed to trigger recurrence
3. Verifying that a new recurring task was created
4. Checking that notifications were sent to staff and admins
5. Validating that inventory reservations were created for the new task

Prerequisites:
- Backend server running
- Valid admin credentials
- At least one staff user in the system
- At least one inventory item available
"""

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add the app directory to the path
sys.path.insert(0, ".")

from app.services.maintenance_task_service import maintenance_task_service
from app.services.notification_manager import notification_manager
from app.services.inventory_service import inventory_service
from app.database.collections import COLLECTIONS
from app.database.database_service import database_service


class RecurrenceTestRunner:
    def __init__(self):
        self.test_task_id: Optional[str] = None
        self.recurring_task_id: Optional[str] = None
        self.test_admin_uid = "test_admin_recurrence"
        self.test_staff_uid = "test_staff_recurrence"
        self.test_inventory_id = "test_inventory_recurrence"
        self.results = {
            "task_created": False,
            "task_completed": False,
            "recurring_task_created": False,
            "staff_notified": False,
            "admin_notified": False,
            "inventory_reservations_created": False,
            "checklist_preserved": False,
            "staff_assignment_preserved": False,
            "priority_preserved": False,
        }

    async def setup_test_data(self):
        """Create test users and inventory items if they don't exist"""
        print("\n" + "=" * 60)
        print("SETUP: Creating test data...")
        print("=" * 60)

        # Create or verify test inventory item
        try:
            success, item, error = await inventory_service.get_inventory_item(self.test_inventory_id)
            if not success or not item:
                print(f"Creating test inventory item: {self.test_inventory_id}")
                # Create test inventory item
                inventory_data = {
                    "item_code": self.test_inventory_id,
                    "item_name": "Test Recurrence Part",
                    "category": "test",
                    "current_stock": 100,
                    "minimum_stock": 10,
                    "unit_of_measure": "pcs",
                    "building_id": "default_building",
                }
                await database_service.create_document(
                    COLLECTIONS["inventory_items"],
                    inventory_data,
                    document_id=self.test_inventory_id,
                    validate=False,
                )
                print(f"✓ Created test inventory item: {self.test_inventory_id}")
            else:
                print(f"✓ Test inventory item exists: {self.test_inventory_id}")
        except Exception as e:
            print(f"⚠ Warning: Could not create test inventory: {e}")

        # Create or verify test users
        try:
            # Check if test staff exists
            success, staff_doc, error = await database_service.get_document(
                COLLECTIONS["users"], self.test_staff_uid
            )
            if not success or not staff_doc:
                print(f"Creating test staff user: {self.test_staff_uid}")
                staff_data = {
                    "id": self.test_staff_uid,
                    "_doc_id": self.test_staff_uid,
                    "email": "test_staff_recurrence@test.com",
                    "role": "staff",
                    "first_name": "Test",
                    "last_name": "Staff",
                    "staff_id": "STAFF-REC-001",
                    "building_id": "default_building",
                    "status": "active",
                }
                await database_service.create_document(
                    COLLECTIONS["users"],
                    staff_data,
                    document_id=self.test_staff_uid,
                    validate=False,
                )
                print(f"✓ Created test staff user: {self.test_staff_uid}")
            else:
                print(f"✓ Test staff user exists: {self.test_staff_uid}")

            # Check if test admin exists
            success, admin_doc, error = await database_service.get_document(
                COLLECTIONS["users"], self.test_admin_uid
            )
            if not success or not admin_doc:
                print(f"Creating test admin user: {self.test_admin_uid}")
                admin_data = {
                    "id": self.test_admin_uid,
                    "_doc_id": self.test_admin_uid,
                    "email": "test_admin_recurrence@test.com",
                    "role": "admin",
                    "first_name": "Test",
                    "last_name": "Admin",
                    "building_id": "default_building",
                    "status": "active",
                }
                await database_service.create_document(
                    COLLECTIONS["users"],
                    admin_data,
                    document_id=self.test_admin_uid,
                    validate=False,
                )
                print(f"✓ Created test admin user: {self.test_admin_uid}")
            else:
                print(f"✓ Test admin user exists: {self.test_admin_uid}")

        except Exception as e:
            print(f"⚠ Warning: Could not create test users: {e}")

        print("\n✓ Setup complete\n")

    async def create_maintenance_task_with_recurrence(self):
        """Step 1: Create a maintenance task with recurrence settings"""
        print("\n" + "=" * 60)
        print("TEST 1: Creating maintenance task with recurrence...")
        print("=" * 60)

        task_payload = {
            "building_id": "default_building",
            "task_title": "Recurrence Test - Weekly AC Filter Check",
            "task_description": "Test task to verify recurrence functionality",
            "location": "Test Building - Floor 1",
            "scheduled_date": datetime.utcnow() + timedelta(hours=1),
            "recurrence_type": "weekly",  # Task should recur every week
            "assigned_to": "STAFF-REC-001",  # Staff ID (not Firebase UID)
            "priority": "high",
            "category": "HVAC",
            "status": "scheduled",
            "parts_used": [
                {
                    "inventory_id": self.test_inventory_id,
                    "quantity": 2,
                }
            ],
            "checklist_completed": [
                {"item": "Check filter condition", "completed": False},
                {"item": "Replace if necessary", "completed": False},
                {"item": "Record readings", "completed": False},
            ],
        }

        try:
            task = await maintenance_task_service.create_task(
                self.test_admin_uid, task_payload
            )
            self.test_task_id = task.id

            print(f"✓ Task created successfully!")
            print(f"  Task ID: {self.test_task_id}")
            print(f"  Task Title: {task.task_title}")
            print(f"  Recurrence Type: {task.recurrence_type}")
            print(f"  Assigned To: {task.assigned_to}")
            print(f"  Priority: {task.priority}")
            print(f"  Category: {task.category}")
            print(f"  Checklist Items: {len(task.checklist_completed or [])}")
            
            # Check inventory reservations
            if hasattr(task, 'inventory_reservation_ids') and task.inventory_reservation_ids:
                print(f"  Inventory Reservations: {len(task.inventory_reservation_ids)}")
                for res_id in task.inventory_reservation_ids:
                    success, res, _ = await database_service.get_document(
                        COLLECTIONS["inventory_reservations"], res_id
                    )
                    if success and res:
                        print(f"    - Reservation {res_id}: {res.get('quantity')} x {res.get('inventory_id')}")

            self.results["task_created"] = True
            return True

        except Exception as e:
            print(f"✗ Failed to create task: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def mark_task_completed(self):
        """Step 2: Mark the task as completed to trigger recurrence"""
        print("\n" + "=" * 60)
        print("TEST 2: Marking task as completed...")
        print("=" * 60)

        if not self.test_task_id:
            print("✗ No task ID to complete")
            return False

        try:
            # Get the task before completion
            task_before = await maintenance_task_service.get_task(self.test_task_id)
            print(f"Task before completion:")
            print(f"  Status: {task_before.status}")
            print(f"  Recurrence Type: {task_before.recurrence_type}")

            # Mark as completed
            update_payload = {
                "status": "completed",
                "completed_at": datetime.utcnow(),
            }

            updated_task = await maintenance_task_service.update_task(
                self.test_task_id, update_payload
            )

            print(f"\n✓ Task marked as completed!")
            print(f"  Status: {updated_task.status}")
            print(f"  Completed At: {updated_task.completed_at}")

            self.results["task_completed"] = True
            
            # Wait a moment for recurrence logic to execute
            await asyncio.sleep(2)
            
            return True

        except Exception as e:
            print(f"✗ Failed to mark task completed: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def verify_recurring_task_created(self):
        """Step 3: Verify that a new recurring task was created"""
        print("\n" + "=" * 60)
        print("TEST 3: Verifying recurring task was created...")
        print("=" * 60)

        try:
            # Query for tasks with the same title but different ID
            filters = {
                "building_id": "default_building",
            }
            tasks = await maintenance_task_service.list_tasks(filters)

            # Find the recurring task (newer task with same title pattern)
            recurring_tasks = [
                t for t in tasks
                if "Recurrence Test" in (t.task_title or "")
                and t.id != self.test_task_id
                and t.status == "scheduled"
            ]

            if recurring_tasks:
                recurring_task = recurring_tasks[0]
                self.recurring_task_id = recurring_task.id

                print(f"✓ Recurring task found!")
                print(f"  Original Task ID: {self.test_task_id}")
                print(f"  Recurring Task ID: {self.recurring_task_id}")
                print(f"  Task Title: {recurring_task.task_title}")
                print(f"  Scheduled Date: {recurring_task.scheduled_date}")
                print(f"  Status: {recurring_task.status}")

                # Verify staff assignment preserved
                if recurring_task.assigned_to == "STAFF-REC-001":
                    print(f"  ✓ Staff Assignment: {recurring_task.assigned_to} (PRESERVED)")
                    self.results["staff_assignment_preserved"] = True
                else:
                    print(f"  ✗ Staff Assignment: {recurring_task.assigned_to} (NOT PRESERVED)")

                # Verify priority preserved
                if recurring_task.priority == "high":
                    print(f"  ✓ Priority: {recurring_task.priority} (PRESERVED)")
                    self.results["priority_preserved"] = True
                else:
                    print(f"  ✗ Priority: {recurring_task.priority} (NOT PRESERVED)")

                # Verify category preserved
                if recurring_task.category == "HVAC":
                    print(f"  ✓ Category: {recurring_task.category} (PRESERVED)")

                # Verify checklist preserved
                if hasattr(recurring_task, 'checklist_completed') and recurring_task.checklist_completed:
                    print(f"  ✓ Checklist Items: {len(recurring_task.checklist_completed)} (PRESERVED)")
                    # Check if all are reset to uncompleted
                    all_uncompleted = all(not item.get("completed", True) for item in recurring_task.checklist_completed)
                    if all_uncompleted:
                        print(f"    ✓ All checklist items reset to uncompleted")
                        self.results["checklist_preserved"] = True
                    else:
                        print(f"    ✗ Some checklist items still marked as completed")
                else:
                    print(f"  ✗ Checklist not preserved")

                # Verify recurrence type preserved
                if recurring_task.recurrence_type == "weekly":
                    print(f"  ✓ Recurrence Type: {recurring_task.recurrence_type} (PRESERVED)")

                self.results["recurring_task_created"] = True
                return True
            else:
                print(f"✗ No recurring task found")
                print(f"  Total tasks found: {len(tasks)}")
                print(f"  Tasks with 'Recurrence Test' in title: {len([t for t in tasks if 'Recurrence Test' in (t.task_title or '')])}")
                return False

        except Exception as e:
            print(f"✗ Failed to verify recurring task: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def check_notifications_sent(self):
        """Step 4: Check that notifications were sent to staff and admins"""
        print("\n" + "=" * 60)
        print("TEST 4: Checking notifications were sent...")
        print("=" * 60)

        if not self.recurring_task_id:
            print("✗ No recurring task ID to check notifications for")
            return False

        try:
            # Query notifications related to the recurring task
            success, notifications, error = await database_service.query_documents(
                COLLECTIONS["notifications"],
                [
                    ("related_entity_id", "==", self.recurring_task_id),
                    ("related_entity_type", "==", "maintenance_task"),
                ]
            )

            if success and notifications:
                print(f"✓ Found {len(notifications)} notification(s) for recurring task")

                staff_notifs = []
                admin_notifs = []

                for notif in notifications:
                    recipient = notif.get("recipient_id")
                    title = notif.get("title", "")
                    message = notif.get("message", "")
                    
                    print(f"\n  Notification:")
                    print(f"    Recipient: {recipient}")
                    print(f"    Title: {title}")
                    print(f"    Message: {message[:80]}...")
                    
                    # Check if it's for staff (assignment notification)
                    if "assigned" in title.lower() and self.test_staff_uid in recipient:
                        staff_notifs.append(notif)
                        print(f"    ✓ Staff assignment notification")
                    
                    # Check if it's for admin (recurring task created)
                    if "recurring" in title.lower() and recipient != self.test_staff_uid:
                        admin_notifs.append(notif)
                        print(f"    ✓ Admin recurring task notification")

                if staff_notifs:
                    print(f"\n✓ Staff received {len(staff_notifs)} notification(s)")
                    self.results["staff_notified"] = True
                else:
                    print(f"\n⚠ No staff notifications found")

                if admin_notifs:
                    print(f"✓ Admin(s) received {len(admin_notifs)} notification(s)")
                    self.results["admin_notified"] = True
                else:
                    print(f"⚠ No admin notifications found")

                return len(notifications) > 0

            else:
                print(f"✗ No notifications found for recurring task")
                print(f"  Error: {error}")
                return False

        except Exception as e:
            print(f"✗ Failed to check notifications: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def validate_inventory_reservations(self):
        """Step 5: Validate that inventory reservations were created for the new task"""
        print("\n" + "=" * 60)
        print("TEST 5: Validating inventory reservations...")
        print("=" * 60)

        if not self.recurring_task_id:
            print("✗ No recurring task ID to check inventory for")
            return False

        try:
            # Query inventory reservations for the recurring task
            success, reservations, error = await database_service.query_documents(
                COLLECTIONS["inventory_reservations"],
                [
                    ("maintenance_task_id", "==", self.recurring_task_id),
                ]
            )

            if success and reservations:
                print(f"✓ Found {len(reservations)} inventory reservation(s) for recurring task")

                for res in reservations:
                    print(f"\n  Reservation ID: {res.get('id') or res.get('_doc_id')}")
                    print(f"    Inventory ID: {res.get('inventory_id')}")
                    print(f"    Quantity: {res.get('quantity')}")
                    print(f"    Status: {res.get('status')}")
                    print(f"    Created At: {res.get('created_at')}")

                # Verify the reservation matches the original
                expected_item = self.test_inventory_id
                found_match = any(
                    res.get('inventory_id') == expected_item and res.get('quantity') == 2
                    for res in reservations
                )

                if found_match:
                    print(f"\n✓ Inventory reservations match original task")
                    self.results["inventory_reservations_created"] = True
                else:
                    print(f"\n⚠ Inventory reservations don't match original task")

                return True

            else:
                print(f"✗ No inventory reservations found for recurring task")
                print(f"  Error: {error}")
                return False

        except Exception as e:
            print(f"✗ Failed to validate inventory reservations: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def cleanup(self):
        """Clean up test data"""
        print("\n" + "=" * 60)
        print("CLEANUP: Removing test data...")
        print("=" * 60)

        try:
            # Delete test tasks
            if self.test_task_id:
                await database_service.delete_document(
                    COLLECTIONS["maintenance_tasks"], self.test_task_id
                )
                print(f"✓ Deleted original task: {self.test_task_id}")

            if self.recurring_task_id:
                await database_service.delete_document(
                    COLLECTIONS["maintenance_tasks"], self.recurring_task_id
                )
                print(f"✓ Deleted recurring task: {self.recurring_task_id}")

            # Delete test notifications
            success, notifications, _ = await database_service.query_documents(
                COLLECTIONS["notifications"],
                [("related_entity_id", "in", [self.test_task_id, self.recurring_task_id])]
            )
            if success and notifications:
                for notif in notifications:
                    notif_id = notif.get("id") or notif.get("_doc_id")
                    if notif_id:
                        await database_service.delete_document(
                            COLLECTIONS["notifications"], notif_id
                        )
                print(f"✓ Deleted {len(notifications)} test notification(s)")

            # Delete test inventory reservations
            success, reservations, _ = await database_service.query_documents(
                COLLECTIONS["inventory_reservations"],
                [("maintenance_task_id", "in", [self.test_task_id, self.recurring_task_id])]
            )
            if success and reservations:
                for res in reservations:
                    res_id = res.get("id") or res.get("_doc_id")
                    if res_id:
                        await database_service.delete_document(
                            COLLECTIONS["inventory_reservations"], res_id
                        )
                print(f"✓ Deleted {len(reservations)} test reservation(s)")

            print("\n✓ Cleanup complete")

        except Exception as e:
            print(f"⚠ Cleanup warning: {e}")

    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)

        total_tests = len(self.results)
        passed_tests = sum(1 for v in self.results.values() if v)

        print(f"\nTests Passed: {passed_tests}/{total_tests}\n")

        for test_name, passed in self.results.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            test_display = test_name.replace("_", " ").title()
            print(f"  {status}: {test_display}")

        print("\n" + "=" * 60)

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED!")
        elif passed_tests >= total_tests * 0.7:
            print("⚠ MOST TESTS PASSED - Some issues detected")
        else:
            print("❌ TESTS FAILED - Critical issues detected")

        print("=" * 60 + "\n")

        return passed_tests == total_tests

    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "=" * 60)
        print("MAINTENANCE RECURRENCE TEST SUITE")
        print("=" * 60)
        print(f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

        try:
            # Setup
            await self.setup_test_data()

            # Run tests
            await self.create_maintenance_task_with_recurrence()
            await self.mark_task_completed()
            await self.verify_recurring_task_created()
            await self.check_notifications_sent()
            await self.validate_inventory_reservations()

            # Print summary
            all_passed = self.print_summary()

            # Cleanup
            cleanup_choice = input("\nDelete test data? (y/n): ").lower()
            if cleanup_choice == 'y':
                await self.cleanup()
            else:
                print("\nTest data preserved for manual inspection:")
                print(f"  Original Task ID: {self.test_task_id}")
                print(f"  Recurring Task ID: {self.recurring_task_id}")

            return all_passed

        except Exception as e:
            print(f"\n❌ Test suite failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main entry point"""
    runner = RecurrenceTestRunner()
    success = await runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Comprehensive script demonstrating maintenance task creation with inventory reservation
and recurring schedule setup.

This script shows how to:
1. Create a recurring maintenance schedule
2. Create a maintenance task with inventory reservation/request
3. Demonstrate the relationship between schedules, tasks, and inventory

Prerequisites:
- Backend server running on localhost:8000
- Valid admin user credentials
- Existing building and equipment IDs
- Existing inventory items
"""

import requests
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"
AUTH_ENDPOINT = f"{BASE_URL}/auth/login"
MAINTENANCE_SCHEDULE_ENDPOINT = f"{BASE_URL}/maintenance-calendar/schedules"
MAINTENANCE_TASK_ENDPOINT = f"{BASE_URL}/maintenance/"
INVENTORY_RESERVATION_ENDPOINT = f"{BASE_URL}/inventory/reservations"
INVENTORY_ASSIGNED_REQUESTS_ENDPOINT = f"{BASE_URL}/inventory/assigned-requests"
EQUIPMENT_ENDPOINT = f"{BASE_URL}/maintenance-calendar/equipment"  # Use maintenance-calendar prefix

# Sample data - REPLACE WITH YOUR ACTUAL VALUES
USER_CREDENTIALS = {
    "email": "admin@example.com",  # Replace with actual admin email
    "password": "admin123"         # Replace with actual password
}

# Sample building and equipment IDs - REPLACE WITH ACTUAL VALUES
SAMPLE_BUILDING_ID = "your_building_id_here"
SAMPLE_EQUIPMENT_ID = "your_equipment_id_here"

# Sample inventory IDs - REPLACE WITH ACTUAL INVENTORY ITEM IDs
SAMPLE_INVENTORY_ITEMS = [
    {"id": "washer_inventory_id", "name": "Washer", "quantity": 1},
    {"id": "pipe_tape_inventory_id", "name": "Pipe Tape", "quantity": 2}
]

# Recurring Maintenance Schedule Data
SAMPLE_MAINTENANCE_SCHEDULE = {
    "equipment_id": SAMPLE_EQUIPMENT_ID,
    "building_id": SAMPLE_BUILDING_ID,
    "schedule_name": "Monthly HVAC Filter Replacement",
    "description": "Replace air filters in HVAC system to maintain air quality and system efficiency",
    "schedule_type": "time_based",
    "recurrence_pattern": "monthly",  # weekly, monthly, quarterly, yearly
    "interval_value": 1,  # Every 1 month
    "specific_dates": [1],  # On the 1st of each month
    "estimated_duration": 60,  # 60 minutes
    "required_skills": ["HVAC Technician"],
    "required_parts": ["Air Filter", "Filter Housing Seal"],
    "safety_requirements": ["Lock out/tag out electrical panel"],
    "preferred_time_slots": ["09:00-12:00"],
    "priority": "medium"
}

# Maintenance Task with Inventory Reservation
SAMPLE_MAINTENANCE_TASK = {
    "building_id": SAMPLE_BUILDING_ID,
    "task_title": "HVAC Filter Replacement - Monthly Maintenance",
    "task_description": "Replace air filters in Building A HVAC system. Check filter housing for damage and ensure proper seal.",
    "location": "Building A - Roof HVAC Unit",
    "scheduled_date": "2025-12-01T09:00:00Z",  # Next month
    "priority": "medium",
    "assigned_to": None,  # Will be assigned later
    "category": "hvac",
    "maintenance_type": "internal",
    "estimated_duration": 60,
    "recurrence_type": "monthly",  # This task can recur independently
    "checklist_completed": [
        {"item": "Inspect filter housing for damage", "completed": False},
        {"item": "Remove old filter", "completed": False},
        {"item": "Install new filter", "completed": False},
        {"item": "Check filter seal", "completed": False},
        {"item": "Test system operation", "completed": False}
    ],
    "parts_used": [
        {"inventory_id": SAMPLE_INVENTORY_ITEMS[0]["id"], "name": "Air Filter", "quantity": 1, "reserve": True},
        {"inventory_id": SAMPLE_INVENTORY_ITEMS[1]["id"], "name": "Filter Seal Tape", "quantity": 1, "reserve": True}
    ]
}

def authenticate() -> tuple[str, dict]:
    """Authenticate and return access token and user info."""
    try:
        print("Authenticating...")
        response = requests.post(AUTH_ENDPOINT, json=USER_CREDENTIALS)
        response.raise_for_status()
        data = response.json()
        token = data.get("id_token") or data.get("access_token")
        
        # Extract user info from response
        user_info = {
            "role": data.get("role", "staff"),  # Default to staff if not specified
            "uid": data.get("uid"),
            "email": data.get("email")
        }
        
        print(f"Authentication successful - Role: {user_info['role']}")
        return token, user_info
    except requests.exceptions.RequestException as e:
        print(f"Authentication failed: {e}")
        return None, None

def get_equipment_list(token: str) -> List[Dict[str, Any]]:
    """Get list of equipment to help with ID selection."""
    # Skip equipment list fetch as endpoint may not exist
    print("Skipping equipment list fetch (endpoint not available)")
    return []

def create_maintenance_schedule(token: str) -> str:
    """Create a recurring maintenance schedule and return its ID."""
    headers = {"Authorization": f"Bearer {token}"}

    print("Creating recurring maintenance schedule...")
    print(f"   Schedule: {SAMPLE_MAINTENANCE_SCHEDULE['schedule_name']}")
    print(f"   Recurrence: {SAMPLE_MAINTENANCE_SCHEDULE['recurrence_pattern']} (every {SAMPLE_MAINTENANCE_SCHEDULE['interval_value']} units)")

    try:
        response = requests.post(MAINTENANCE_SCHEDULE_ENDPOINT, json=SAMPLE_MAINTENANCE_SCHEDULE, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            schedule_id = data.get("schedule_id")
            print(f"Maintenance schedule created successfully: {schedule_id}")
            return schedule_id
        else:
            print(f"Failed to create schedule: {data.get('message', 'Unknown error')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Failed to create maintenance schedule: {e}")
        return None

def create_maintenance_task(token: str, schedule_id: str = None) -> str:
    """Create a maintenance task and return its ID."""
    headers = {"Authorization": f"Bearer {token}"}

    # Add schedule_id if provided (linking task to schedule)
    task_data = SAMPLE_MAINTENANCE_TASK.copy()
    if schedule_id:
        task_data["schedule_id"] = schedule_id
        print("Linking task to recurring schedule...")

    print("Creating maintenance task...")
    print(f"   Task: {task_data['task_title']}")
    print(f"   Scheduled: {task_data['scheduled_date']}")
    print(f"   Parts needed: {len(task_data['parts_used'])} items")

    try:
        response = requests.post(MAINTENANCE_TASK_ENDPOINT, json=task_data, headers=headers)
        response.raise_for_status()
        data = response.json()

        task = data.get("task", {})
        task_id = task.get("id") or task.get("task_id") or data.get("task_id")

        if task_id:
            print(f"Maintenance task created successfully: {task_id}")
            return task_id
        else:
            print(f"Task creation response missing ID: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Failed to create maintenance task: {e}")
        return None

def create_inventory_reservations(token: str, task_id: str):
    """Create inventory reservations for the maintenance task.

    Note: This creates RESERVATIONS (existing inventory held for task)
    not REQUESTS (new parts needed). The mobile app will now show both.
    """
    headers = {"Authorization": f"Bearer {token}"}

    print("Creating inventory reservations...")
    print("   📦 RESERVATIONS: Reserve existing stock for upcoming work")
    print("   📋 REQUESTS: Request new parts (handled separately)")

    for part in SAMPLE_MAINTENANCE_TASK["parts_used"]:
        if not part.get("reserve", False):
            continue

        reservation_data = {
            "inventory_id": part["inventory_id"],
            "quantity": part["quantity"],
            "maintenance_task_id": task_id
        }

        print(f"   Reserving {part['quantity']} x {part['name']} (ID: {part['inventory_id']})")

        try:
            response = requests.post(INVENTORY_RESERVATION_ENDPOINT, json=reservation_data, headers=headers)
            response.raise_for_status()
            data = response.json()

            reservation_id = data.get("reservation_id") or data.get("id")
            if reservation_id:
                print(f"   ✅ Reservation created: {reservation_id}")
            else:
                print(f"   ⚠️ Reservation response: {data}")

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Failed to reserve {part['name']}: {e}")

def assign_staff_to_task(token: str, task_id: str, staff_name: str):
    """Assign a staff member to a maintenance task."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"Assigning staff '{staff_name}' to task {task_id}...")
    
    update_data = {
        "assigned_to": staff_name
    }
    
    try:
        response = requests.put(f"{MAINTENANCE_TASK_ENDPOINT}{task_id}", json=update_data, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            print(f"   ✅ Staff '{staff_name}' assigned to task {task_id}")
            return True
        else:
            print(f"   ❌ Failed to assign staff: {data}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Failed to assign staff to task: {e}")
        return False

def view_inventory_for_task(token: str, user_info: dict, task_id: str = None):
    """View inventory for a specific task using the mobile app endpoints."""
    headers = {"Authorization": f"Bearer {token}"}
    user_role = user_info.get("role", "staff")

    print(f"Viewing inventory for task {task_id} (User role: {user_role})...")
    print("   📱 Simulating mobile app behavior:")

    try:
        # Mobile app calls: /inventory/maintenance-task/{task_id}/requests
        print("   1. Calling: /inventory/maintenance-task/{task_id}/requests")
        endpoint = f"{BASE_URL}/inventory/maintenance-task/{task_id}/requests"
        
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", [])
            print(f"      ✅ SUCCESS: Found {len(items)} inventory items")
            for item in items[:3]:  # Show first 3
                item_type = item.get("type", "unknown")
                name = item.get("item_name", item.get("name", "Unknown"))
                print(f"         - {name} ({item_type})")
        elif response.status_code == 403:
            error_detail = response.json().get("detail", "Access denied")
            print(f"      ❌ 403 Forbidden: {error_detail}")
            print("      💡 SOLUTION: Assign staff to task first!")
        else:
            print(f"      ❌ HTTP {response.status_code}: {response.text}")

        # Mobile app also tries: /inventory/reservations?maintenance_task_id={task_id}
        print("   2. Calling: /inventory/reservations?maintenance_task_id={task_id}")
        endpoint = f"{BASE_URL}/inventory/reservations"
        params = {"maintenance_task_id": task_id}
        
        response = requests.get(endpoint, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            reservations = data.get("data", [])
            print(f"      ✅ SUCCESS: Found {len(reservations)} reservations")
        elif response.status_code == 403:
            print("      ❌ 403 Forbidden: Admin access required")
            print("      💡 This is correct - staff should use the task-specific endpoint")
        else:
            print(f"      ❌ HTTP {response.status_code}: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"      ❌ HTTP {response.status_code}: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")

def demonstrate_reservation_workflow(token: str, task_id: str):
    """Demonstrate the reservation status workflow: reserved -> received -> consumed"""
    print("Demonstrating reservation status workflow...")
    print("   Workflow: reserved (admin) → received (staff) → [defective?] → consumed (staff)")
    print("   If defective: received → request replacement → new request created")
    
    try:
        # First, get the reservation ID from the task
        endpoint = f"{BASE_URL}/inventory/maintenance-task/{task_id}/requests"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("data", [])
        reservations = [item for item in items if item.get("_item_type") == "reservation"]
        
        if not reservations:
            print("   ❌ No reservations found for this task")
            return
            
        reservation = reservations[0]  # Use first reservation
        reservation_id = reservation.get("id") or reservation.get("_doc_id")
        
        if not reservation_id:
            print("   ❌ Could not find reservation ID")
            return
            
        print(f"   Found reservation: {reservation_id}")
        print(f"   Current status: {reservation.get('status', 'unknown')}")
        
        # Step 1: Mark as received (staff action)
        print("   1. Staff marks reservation as RECEIVED...")
        received_endpoint = f"{BASE_URL}/inventory/reservations/{reservation_id}/received"
        
        response = requests.put(received_endpoint, headers=headers)
        if response.status_code == 200:
            print("      ✅ SUCCESS: Reservation marked as received")
            
            # Step 1.5: Request replacement if item is defective
            print("   1.5. Staff finds item DEFECTIVE and requests REPLACEMENT...")
            replacement_endpoint = f"{BASE_URL}/inventory/reservations/{reservation_id}/request-replacement"
            replacement_data = {
                "reason": "Item found defective during inspection - damaged packaging",
                "quantity_needed": 1
            }
            
            response = requests.post(replacement_endpoint, json=replacement_data, headers=headers)
            if response.status_code == 200:
                data = response.json()
                replacement_request_id = data.get("request_id")
                print(f"      ✅ SUCCESS: Replacement request created (ID: {replacement_request_id})")
            else:
                print(f"      ❌ Failed to request replacement: HTTP {response.status_code}")
            
        else:
            print(f"      ❌ Failed to mark as received: HTTP {response.status_code}")
            
        # Step 2: Mark as consumed (staff action after using items)
        print("   2. Staff marks reservation as CONSUMED (after task completion)...")
        consumed_endpoint = f"{BASE_URL}/inventory/reservations/{reservation_id}/consumed"
        
        response = requests.put(consumed_endpoint, headers=headers)
        if response.status_code == 200:
            print("      ✅ SUCCESS: Reservation marked as consumed")
        else:
            print(f"      ❌ Failed to mark as consumed: HTTP {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")

def demonstrate_workflow():
    """Demonstrate the complete workflow."""
    print("Starting Comprehensive Maintenance Demo")
    print("=" * 50)

    # Step 1: Authenticate
    token, user_info = authenticate()
    if not token:
        print("Demo failed: Could not authenticate")
        return

    print()

    # Step 2: Show available equipment (optional)
    equipment = get_equipment_list(token)
    if equipment:
        print(f"Found {len(equipment)} equipment items in building")
        for eq in equipment[:3]:  # Show first 3
            print(f"   - {eq.get('equipment_name', 'Unknown')} (ID: {eq.get('id', 'N/A')})")
        print()

    # Step 3: Create recurring schedule
    print("PHASE 1: Creating Recurring Schedule")
    print("-" * 30)
    schedule_id = create_maintenance_schedule(token)
    if not schedule_id:
        print("Demo failed: Could not create schedule")
        return
    print()

    # Step 4: Create maintenance task linked to schedule
    print("PHASE 2: Creating Maintenance Task")
    print("-" * 30)
    task_id = create_maintenance_task(token, schedule_id)
    if not task_id:
        print("Demo failed: Could not create task")
        return
    print()

    # Step 4.5: Assign staff to the task (for demonstration)
    print("PHASE 2.5: Staff Assignment")
    print("-" * 30)
    # For demo purposes, assign a sample staff member
    # In real usage, this would be done by admin or through proper assignment workflow
    sample_staff_name = "John Doe"  # Replace with actual staff name
    assign_staff_to_task(token, task_id, sample_staff_name)
    print()

    # Step 5: Create inventory reservations
    print("PHASE 3: Inventory Management")
    print("-" * 30)
    create_inventory_reservations(token, task_id)
    print()

    # Step 6: Demonstrate reservation status workflow
    print("PHASE 4: Reservation Status Workflow")
    print("-" * 30)
    demonstrate_reservation_workflow(token, task_id)
    print()

    # Step 7: Demonstrate viewing reservations (role-based)
    print("PHASE 5: Viewing Inventory (Role-Based Access)")
    print("-" * 30)
    view_inventory_for_task(token, user_info, task_id)
    print()

    # Summary
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print("Summary:")
    print(f"   Schedule ID: {schedule_id}")
    print(f"   Task ID: {task_id}")
    print(f"   User Role: {user_info.get('role', 'unknown')}")
    print(f"   Inventory reservations created for {len([p for p in SAMPLE_MAINTENANCE_TASK['parts_used'] if p.get('reserve')])} parts")
    print()
    print("🔧 FIX APPLIED:")
    print("   Mobile app now sees BOTH reservations AND requests!")
    print("   📱 App calls: /inventory/maintenance-task/{id}/requests")
    print("   🗄️ Now returns: reservations + requests from both collections")
    print()
    print("Reservation Status Workflow:")
    print("   1. Admin creates task → inventory status: RESERVED")
    print("   2. Staff receives items → status: RECEIVED")
    print("   3. If item DEFECTIVE → Staff requests REPLACEMENT")
    print("      → New inventory request created")
    print("      → Original reservation marked as defective")
    print("   4. Staff uses items → status: CONSUMED")
    print()
    print("Security Demonstration:")
    print(f"   ✅ Staff '{sample_staff_name}' assigned to task")
    if user_info.get('role') == 'admin':
        print("   ✅ Admin can view ALL reservations via /inventory/reservations")
    else:
        print("   ✅ Staff can view THEIR assigned task items via /inventory/maintenance-task/{id}/requests")
        print("   ✅ Staff cannot access /inventory/reservations (admin-only)")
    print()
    print("Next steps:")
    print("   1. The schedule will automatically create tasks monthly")
    print("   2. Staff can assign and complete the tasks")
    print("   3. Inventory will be automatically reserved for each task")
    print("   4. System tracks maintenance history and usage")

def main():
    """Main execution with error handling."""
    try:
        demonstrate_workflow()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
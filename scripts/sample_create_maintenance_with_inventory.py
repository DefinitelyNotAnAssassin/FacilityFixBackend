#!/usr/bin/env python3
"""
Sample script to demonstrate creating a maintenance task with inventory reservation.

This script shows how to:
1. Authenticate and get a token
2. Create a maintenance task (assuming the endpoint exists)
3. Reserve inventory items for the maintenance task

Prerequisites:
- Backend server running
- Valid user credentials
- Existing inventory items and building IDs
"""

import requests
import json
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust if your server runs on a different port
AUTH_ENDPOINT = f"{BASE_URL}/auth/login"
MAINTENANCE_ENDPOINT = f"{BASE_URL}/maintenance/"  # Corrected endpoint
INVENTORY_RESERVATION_ENDPOINT = f"{BASE_URL}/inventory/reservations"

# Sample data
USER_CREDENTIALS = {
    "email": "tessa_deguzman@gmail.com",  # Replace with actual admin email
    "password": "admin123"    # Replace with actual password
}

SAMPLE_MAINTENANCE_TASK = {
    "building_id": "building_a_id",  # Replace with actual building ID
    "task_title": "Fix leaking faucet in Building A",
    "task_description": "Replace washer and check pipes",
    "location": "Building A - Floor 1",
    "scheduled_date": "2025-11-20T10:00:00Z",
    "priority": "medium",
    "assigned_to": "staff_user_id",  # Replace with actual staff user ID
    "category": "plumbing",
    "maintenance_type": "internal",
    "checklist_completed": [
        {"item": "Replace washer", "completed": False},
        {"item": "Check pipes", "completed": False}
    ],
    "parts_used": [
        {"name": "Washer", "quantity": 1},
        {"name": "Pipe tape", "quantity": 2}
    ]
}

# Inventory to reserve (separate from task creation)
REQUIRED_INVENTORY = [
    {"item_id": "washer_inventory_id", "quantity": 1},  # Replace with actual inventory IDs
    {"item_id": "pipe_tape_inventory_id", "quantity": 2}
]

def authenticate() -> str:
    """Authenticate and return access token."""
    try:
        response = requests.post(AUTH_ENDPOINT, json=USER_CREDENTIALS)
        response.raise_for_status()
        data = response.json()
        return data["id_token"]  # Changed from access_token to id_token
    except requests.exceptions.RequestException as e:
        print(f"Authentication failed: {e}")
        return None

def create_maintenance_task(token: str) -> str:
    """Create a maintenance task and return its ID."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.post(MAINTENANCE_ENDPOINT, json=SAMPLE_MAINTENANCE_TASK, headers=headers)
        response.raise_for_status()
        data = response.json()
        task_id = data.get("task_id") or data.get("id")
        print(f"Maintenance task created successfully: {task_id}")
        return task_id
    except requests.exceptions.RequestException as e:
        print(f"Failed to create maintenance task: {e}")
        return None

def reserve_inventory(token: str, task_id: str):
    """Reserve inventory items for the maintenance task."""
    headers = {"Authorization": f"Bearer {token}"}

    for inventory_item in REQUIRED_INVENTORY:
        reservation_data = {
            "inventory_id": inventory_item["item_id"],
            "quantity": inventory_item["quantity"],
            "maintenance_task_id": task_id
        }

        try:
            response = requests.post(INVENTORY_RESERVATION_ENDPOINT, json=reservation_data, headers=headers)
            response.raise_for_status()
            data = response.json()
            print(f"Inventory reserved: {data['reservation_id']} for item {inventory_item['item_id']}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to reserve inventory for {inventory_item['item_id']}: {e}")

def main():
    """Main execution flow."""
    print("Starting sample maintenance task creation with inventory reservation...")

    # Step 1: Authenticate
    token = authenticate()
    if not token:
        print("Exiting due to authentication failure.")
        return

    # Step 2: Create maintenance task
    task_id = create_maintenance_task(token)
    if not task_id:
        print("Exiting due to task creation failure.")
        return

    # Step 3: Reserve inventory for the task
    reserve_inventory(token, task_id)

    print("Sample script completed successfully!")

if __name__ == "__main__":
    main()
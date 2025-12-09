#!/usr/bin/env python3

import requests
import json
import sys

def test_task_types_format():
    """Test what the task types endpoint actually returns"""
    print("🔧 TESTING TASK TYPES ENDPOINT RESPONSE FORMAT")
    print("=" * 60)
    
    try:
        # Test the endpoint (assuming server is running)
        # You'll need proper auth token, but this shows the concept
        url = "http://localhost:8000/maintenance/task-types"
        
        # For testing without auth, we'll simulate the expected response format
        print("Expected response format based on our code:")
        print("=" * 40)
        
        sample_response = {
            "success": True,
            "data": [
                {
                    "id": "TT-2025-00016",
                    "name": "Light Replacement",  # This should be the actual name
                    "maintenance_type": "Corrective",
                    "description": "Replacing burned-out or non-functional lighting fixtures (bulbs/tubes).",
                    "inventory_items": [],
                    "formatted_id": "TT-2025-00016"
                }
            ],
            "count": 1
        }
        
        print(json.dumps(sample_response, indent=2))
        
        print("\n" + "=" * 40)
        print("Based on your screenshots:")
        print("- Table shows: 'Light Replacement' (correct)")
        print("- Dropdown shows: 'Corrective - Replacing burned-out...' (wrong)")
        print("\nThis suggests the FRONTEND is formatting the name incorrectly.")
        print("The frontend might be using: `${maintenance_type} - ${description}`")
        print("Instead of using: `${name}`")
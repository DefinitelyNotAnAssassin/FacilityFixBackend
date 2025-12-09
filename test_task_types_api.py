#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from fastapi.testclient import TestClient
from app.main import app

def test_task_types_endpoint():
    """Test the task types endpoint"""
    print("🔧 TESTING TASK TYPES ENDPOINT")
    print("=" * 40)
    
    try:
        client = TestClient(app)
        
        # Test the endpoint
        print("\n[TEST] Calling /maintenance/task-types...")
        
        response = client.get('/maintenance/task-types')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('success', False)}")
            print(f"📋 Count: {data.get('count', 0)}")
            
            task_types = data.get('data', [])
            if task_types:
                print(f"\n📦 Task Types Found:")
                for i, tt in enumerate(task_types[:3]):  # Show first 3
                    print(f"  [{i+1}] ID: {tt.get('id')}")
                    print(f"      Name: {tt.get('name')}")
                    print(f"      Type: {tt.get('maintenance_type')}")
                    print(f"      Inventory Items: {len(tt.get('inventory_items', []))}")
                    
                    # Show inventory items
                    inventory = tt.get('inventory_items', [])
                    for j, item in enumerate(inventory[:2]):  # Show first 2 items
                        print(f"        [{j+1}] {item.get('name')} (Stock: {item.get('stock_quantity')}, Unit: {item.get('unit')})")
            else:
                print("❌ No task types found")
        else:
            print(f"❌ Request failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_task_types_endpoint()
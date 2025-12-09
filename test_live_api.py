#!/usr/bin/env python3

import requests
import json

def test_api_endpoint():
    """Test the API endpoint directly"""
    print("🔧 TESTING API ENDPOINT DIRECTLY")
    print("=" * 40)
    
    try:
        # Test without auth first
        print("\n[TEST 1] Testing without authentication...")
        response = requests.get('http://localhost:8000/maintenance/task-types')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print("⚠️  Authentication required")
        elif response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Failed: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Server not running. Please start the server with: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    test_api_endpoint()
#!/usr/bin/env python3
"""
Debug script to test registration endpoints and identify validation issues
"""
import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_registration():
    """Test registration endpoints with detailed error reporting"""
    
    async with aiohttp.ClientSession() as session:
        
        # Test Admin Registration
        print("=== Testing Admin Registration ===")
        admin_data = {
            "email": "admin@test.com",
            "password": "password123",
            "first_name": "John",
            "last_name": "Admin"
        }
        
        try:
            async with session.post(f"{BASE_URL}/auth/register/admin", json=admin_data) as response:
                result = await response.json()
                print(f"Status: {response.status}")
                print(f"Response: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Admin registration error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test Tenant Registration
        print("=== Testing Tenant Registration ===")
        tenant_data = {
            "email": "tenant@test.com",
            "password": "password123",
            "first_name": "Jane",
            "last_name": "Tenant",
            "building_unit": "A-01"
        }
        
        try:
            async with session.post(f"{BASE_URL}/auth/register/tenant", json=tenant_data) as response:
                result = await response.json()
                print(f"Status: {response.status}")
                print(f"Response: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Tenant registration error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test Login and Token Generation
        print("=== Testing Login and Token Generation ===")
        login_data = {
            "identifier": "admin@test.com",
            "password": "password123"
        }
        
        try:
            async with session.post(f"{BASE_URL}/auth/generate-test-token", json=login_data) as response:
                result = await response.json()
                print(f"Status: {response.status}")
                print(f"Response: {json.dumps(result, indent=2)}")
                
                if response.status == 200 and "access_token" in result:
                    print(f"\n SUCCESS! Copy this token for FastAPI docs:")
                    print(f"Bearer {result['access_token']}")
                    print(f"\nInstructions:")
                    print(f"1. Go to http://localhost:8000/docs")
                    print(f"2. Click 'Authorize' button")
                    print(f"3. Paste this token: {result['access_token']}")
                    print(f"4. Click 'Authorize'")
                    
        except Exception as e:
            print(f"Token generation error: {e}")

if __name__ == "__main__":
    print("🔧 FacilityFix Registration Debug Tool")
    print("Make sure your FastAPI server is running on http://localhost:8000")
    print("="*60)
    
    asyncio.run(test_registration())

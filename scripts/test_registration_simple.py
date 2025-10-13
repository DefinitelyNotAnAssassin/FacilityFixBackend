#!/usr/bin/env python3
"""
Simple registration test script without authentication requirements
"""
import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_registration():
    """Test user registration endpoints"""
    
    async with aiohttp.ClientSession() as session:
        
        # Test Admin Registration
        print("Testing Admin Registration...")
        admin_data = {
            "email": f"admin.test.{int(datetime.now().timestamp())}@facilityfix.com",
            "password": "AdminPass123!",
            "first_name": "Test",
            "last_name": "Admin"
        }
        
        try:
            async with session.post(
                f"{BASE_URL}/auth/register/admin",
                json=admin_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                print(f"Admin Registration Status: {response.status}")
                print(f"Admin Registration Response: {json.dumps(result, indent=2)}")
                
                if response.status == 200:
                    print("Admin registration successful!")
                else:
                    print("Admin registration failed!")
                    
        except Exception as e:
            print(f"Admin registration error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test Tenant Registration
        print("Testing Tenant Registration...")
        tenant_data = {
            "email": f"tenant.test.{int(datetime.now().timestamp())}@facilityfix.com",
            "password": "TenantPass123!",
            "first_name": "Test",
            "last_name": "Tenant",
            "building_unit": "A-01"
        }
        
        try:
            async with session.post(
                f"{BASE_URL}/auth/register/tenant",
                json=tenant_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                print(f"Tenant Registration Status: {response.status}")
                print(f"Tenant Registration Response: {json.dumps(result, indent=2)}")
                
                if response.status == 200:
                    print("Tenant registration successful!")
                else:
                    print("Tenant registration failed!")
                    
        except Exception as e:
            print(f"Tenant registration error: {e}")
        
        print("\n" + "="*50 + "\n")
        
        # Test Login
        print("Testing Login...")
        login_data = {
            "identifier": admin_data["email"],
            "password": admin_data["password"]
        }
        
        try:
            async with session.post(
                f"{BASE_URL}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                print(f"Login Status: {response.status}")
                print(f"Login Response: {json.dumps(result, indent=2)}")
                
                if response.status == 200:
                    print("Login validation successful!")
                else:
                    print("Login validation failed!")
                    
        except Exception as e:
            print(f"Login error: {e}")

async def test_server_health():
    """Test if server is running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    print("Server is running!")
                    return True
                else:
                    print(f"Server health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"Cannot connect to server: {e}")
        return False

async def main():
    print("FacilityFix Registration Test")
    print("="*50)
    
    # Check server health first
    if not await test_server_health():
        print("Please make sure the FastAPI server is running:")
        print("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return
    
    print("\nStarting registration tests...\n")
    await test_registration()
    
    print("\n" + "="*50)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(main())

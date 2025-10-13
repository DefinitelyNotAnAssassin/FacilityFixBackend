import asyncio
import httpx
import json

async def test_complete_auth_flow():
    """Test the complete authentication flow"""
    
    base_url = "http://localhost:8000"  # Adjust if your server runs on different port
    
    print("=== Testing Complete Authentication Flow ===\n")
    
    # Test data
    test_admin = {
        "email": "admin@facilityfix.com",
        "password": "admin123456",
        "first_name": "Admin",
        "last_name": "User"
    }
    
    async with httpx.AsyncClient() as client:
        
        # Step 1: Register admin user
        print("1. Registering admin user...")
        try:
            response = await client.post(
                f"{base_url}/auth/register/admin",
                json=test_admin
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Admin registered: {result.get('user_id')}")
            else:
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Registration error: {e}")
        
        # Step 2: Get ID token for testing
        print("\n2. Getting ID token for API testing...")
        try:
            response = await client.post(
                f"{base_url}/auth/exchange-token",
                json={
                    "identifier": test_admin["email"],
                    "password": test_admin["password"]
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                token_data = response.json()
                id_token = token_data.get("id_token")
                print(f"   ✅ ID token obtained: {id_token[:50]}...")
                
                # Step 3: Test protected endpoint
                print("\n3. Testing protected endpoint...")
                headers = {"Authorization": f"Bearer {id_token}"}
                
                me_response = await client.get(
                    f"{base_url}/auth/me",
                    headers=headers
                )
                print(f"   Status: {me_response.status_code}")
                if me_response.status_code == 200:
                    user_info = me_response.json()
                    print(f"   ✅ Authentication successful!")
                    print(f"   User: {user_info.get('email')}")
                    print(f"   Role: {user_info.get('role')}")
                    print(f"   User ID: {user_info.get('user_id')}")
                else:
                    print(f"   ❌ Authentication failed: {me_response.text}")
            else:
                print(f"   ❌ Token exchange failed: {response.text}")
        except Exception as e:
            print(f"   ❌ Token exchange error: {e}")
    
    print("\n=== Test Complete ===")
    print("\nIf authentication is still failing:")
    print("1. Check that your FastAPI server is running on the correct port")
    print("2. Verify firebase-service-account.json is in the correct location")
    print("3. Check server logs for detailed error messages")
    print("4. Use the debug_auth.py script for more detailed diagnostics")

if __name__ == "__main__":
    asyncio.run(test_complete_auth_flow())

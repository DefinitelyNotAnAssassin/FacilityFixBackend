import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.auth.firebase_auth import firebase_auth
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

async def debug_authentication():
    """Debug script to test authentication and identify issues"""
    
    print("=== FacilityFix Authentication Debug ===\n")
    
    # Test 1: Check Firebase initialization
    print("1. Testing Firebase initialization...")
    try:
        # Try to get a non-existent user to test Firebase connection
        result = await firebase_auth.get_user_by_email("test@nonexistent.com")
        print("   ❌ Firebase connection issue - should have failed")
    except Exception as e:
        if "USER_NOT_FOUND" in str(e) or "There is no user record" in str(e):
            print("   ✅ Firebase connection working")
        else:
            print(f"   ❌ Firebase connection error: {e}")
    
    # Test 2: List existing users
    print("\n2. Checking existing users in Firestore...")
    try:
        success, users, error = await database_service.query_documents(
            COLLECTIONS['users'],
            []  # Get all users
        )
        
        if success and users:
            print(f"   Found {len(users)} users:")
            for user in users:
                print(f"   - Email: {user.get('email')}, Role: {user.get('role')}, User ID: {user.get('user_id')}")
        else:
            print(f"   ❌ Error fetching users: {error}")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
    
    # Test 3: Test token generation for existing admin
    print("\n3. Testing token generation...")
    try:
        success, users, error = await database_service.query_documents(
            COLLECTIONS['users'],
            [("role", "==", "admin")]
        )
        
        if success and users:
            admin_user = users[0]
            print(f"   Testing with admin user: {admin_user.get('email')}")
            
            # Generate custom token
            custom_token = await firebase_auth.create_custom_token(admin_user['id'])
            print(f"   ✅ Custom token generated: {custom_token[:50]}...")
            
            # Test token verification
            # Note: Custom tokens need to be exchanged for ID tokens to be verified
            print("   ⚠️  Custom tokens need to be exchanged for ID tokens for verification")
            
        else:
            print("   ❌ No admin users found")
    except Exception as e:
        print(f"   ❌ Token generation error: {e}")
    
    # Test 4: Check service account file
    print("\n4. Checking service account configuration...")
    service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH', 'firebase-service-account.json')
    if os.path.exists(service_account_path):
        print(f"   ✅ Service account file found: {service_account_path}")
    else:
        print(f"   ❌ Service account file missing: {service_account_path}")
        print("   Please download your Firebase service account key and save it as 'firebase-service-account.json'")
    
    print("\n=== Debug Complete ===")
    print("\nTo fix authentication issues:")
    print("1. Ensure firebase-service-account.json exists in the project root")
    print("2. Use /auth/exchange-token endpoint to get proper ID tokens for testing")
    print("3. Check that custom claims are set correctly during user registration")
    print("4. Verify that the token is being sent in the correct Bearer format")

if __name__ == "__main__":
    asyncio.run(debug_authentication())

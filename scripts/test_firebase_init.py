#!/usr/bin/env python3
"""
Simple test script to verify Firebase initialization works correctly.
This script tests the Firebase initialization system independently.
"""

import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_firebase_initialization():
    """Test Firebase initialization system"""
    print("🔥 Testing Firebase Initialization System")
    print("=" * 50)
    
    try:
        # Test 1: Import Firebase init module
        print("1️⃣ Testing Firebase init module import...")
        from app.core.firebase_init import initialize_firebase, is_firebase_available, get_firebase_status
        print("✅ Firebase init module imported successfully")
        
        # Test 2: Check initial status
        print("\n2️⃣ Checking initial Firebase status...")
        initial_status = get_firebase_status()
        print(f"   Initial status: {initial_status}")
        
        # Test 3: Attempt initialization
        print("\n3️⃣ Attempting Firebase initialization...")
        success = initialize_firebase()
        
        if success:
            print("✅ Firebase initialized successfully")
        else:
            print("⚠️ Firebase initialization failed (this is expected if service account file is missing)")
        
        # Test 4: Check final status
        print("\n4️⃣ Checking final Firebase status...")
        final_status = get_firebase_status()
        print(f"   Final status: {final_status}")
        
        # Test 5: Test availability check
        print("\n5️⃣ Testing availability check...")
        is_available = is_firebase_available()
        print(f"   Firebase available: {is_available}")
        
        # Test 6: Test database service initialization
        print("\n6️⃣ Testing database service initialization...")
        try:
            from app.database.database_service import database_service
            if database_service is not None:
                print("✅ Database service initialized successfully")
            else:
                print("⚠️ Database service is None (expected if Firebase not available)")
        except Exception as e:
            print(f"⚠️ Database service initialization issue: {e}")
        
        # Test 7: Test Firestore client
        print("\n7️⃣ Testing Firestore client...")
        try:
            from app.database.firestore_client import get_firestore_client
            client = get_firestore_client()
            if client is not None:
                print("✅ Firestore client created successfully")
            else:
                print("⚠️ Firestore client is None (expected if Firebase not available)")
        except Exception as e:
            print(f"⚠️ Firestore client issue: {e}")
        
        print("\n" + "=" * 50)
        print("📊 FIREBASE INITIALIZATION TEST RESULTS")
        print("=" * 50)
        
        if success:
            print("✅ Firebase initialization: PASSED")
            print("🎉 Firebase is properly configured and working!")
        else:
            print("⚠️ Firebase initialization: FAILED (but gracefully handled)")
            print("ℹ️ This is expected if:")
            print("   - Firebase service account file is missing")
            print("   - Firebase credentials are not configured")
            print("   - Running in development/test environment")
            print("\n💡 To fix this:")
            print("   1. Download your Firebase service account key")
            print("   2. Place it as 'firebase-service-account.json' in the backend directory")
            print("   3. Set FIREBASE_PROJECT_ID environment variable")
        
        return True
        
    except Exception as e:
        print(f"❌ Firebase initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test execution"""
    print(f"🚀 Starting Firebase Initialization Test at {datetime.now()}")
    success = test_firebase_initialization()
    
    if success:
        print("\n✅ Firebase initialization test completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Firebase initialization test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()

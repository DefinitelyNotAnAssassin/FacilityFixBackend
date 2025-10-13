#!/usr/bin/env python3
"""
Test script to isolate router import issues
"""
import sys
import traceback

def test_individual_imports():
    """Test each import individually to isolate the problem"""
    print("Testing individual imports...")
    
    try:
        print("1. Testing FastAPI imports...")
        from fastapi import APIRouter, HTTPException, status, Depends
        print("   ✅ FastAPI imports successful")
    except Exception as e:
        print(f"   ❌ FastAPI imports failed: {e}")
        return False
    
    try:
        print("2. Testing user models...")
        from app.models.user import UserLogin, UserResponse, UserRole, UserStatus
        print("   ✅ User models import successful")
    except Exception as e:
        print(f"   ❌ User models import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("3. Testing database models...")
        from app.models.database_models import UserProfile
        print("   ✅ Database models import successful")
    except Exception as e:
        print(f"   ❌ Database models import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("4. Testing Firebase auth...")
        from app.auth.firebase_auth import firebase_auth
        print("   ✅ Firebase auth import successful")
    except Exception as e:
        print(f"   ❌ Firebase auth import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("5. Testing auth dependencies...")
        from app.auth.dependencies import require_admin, get_current_user
        print("   ✅ Auth dependencies import successful")
    except Exception as e:
        print(f"   ❌ Auth dependencies import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("6. Testing database service...")
        from app.database.database_service import database_service
        print("   ✅ Database service import successful")
    except Exception as e:
        print(f"   ❌ Database service import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("7. Testing collections...")
        from app.database.collections import COLLECTIONS
        print("   ✅ Collections import successful")
    except Exception as e:
        print(f"   ❌ Collections import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("8. Testing user ID service...")
        from app.services.user_id_service import user_id_service
        print("   ✅ User ID service import successful")
    except Exception as e:
        print(f"   ❌ User ID service import failed: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("9. Testing config...")
        from app.core.config import settings
        print("   ✅ Config import successful")
    except Exception as e:
        print(f"   ❌ Config import failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_auth_router_import():
    """Test importing the complete auth router"""
    print("\nTesting complete auth router import...")
    
    try:
        from app.routers.auth import router
        print("✅ Auth router import successful!")
        print(f"   Router prefix: {router.prefix}")
        print(f"   Router tags: {router.tags}")
        print(f"   Number of routes: {len(router.routes)}")
        
        # List all routes
        print("   Routes:")
        for route in router.routes:
            print(f"     - {route.methods} {route.path}")
        
        return True
    except Exception as e:
        print(f"❌ Auth router import failed: {e}")
        traceback.print_exc()
        return False

def main():
    print("=== Router Import Diagnostic ===\n")
    
    # Test individual imports first
    if not test_individual_imports():
        print("\n❌ Individual imports failed. Fix the failing imports first.")
        return
    
    # Test complete router import
    if not test_auth_router_import():
        print("\n❌ Auth router import failed. Check the router implementation.")
        return
    
    print("\n✅ All imports successful! The auth router should work.")

if __name__ == "__main__":
    main()

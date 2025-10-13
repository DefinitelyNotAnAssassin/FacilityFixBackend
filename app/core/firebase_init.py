import firebase_admin
from firebase_admin import credentials
import os
from typing import Optional

_firebase_initialized = False

def initialize_firebase() -> bool:
    """
    Initialize Firebase Admin SDK if not already initialized.
    Returns True if successful, False otherwise.
    """
    global _firebase_initialized
    
    if _firebase_initialized or firebase_admin._apps:
        return True
    
    try:
        service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH', 'firebase-service-account.json')
        
        if not os.path.exists(service_account_path):
            print(f"Warning: Firebase service account file not found at {service_account_path}")
            print("Firebase will not be available for this session.")
            return False
        
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID', 'facilityfix-6d27a')
        })
        
        _firebase_initialized = True
        print("✅ Firebase initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        return False

def is_firebase_available() -> bool:
    """Check if Firebase is available and initialized."""
    return _firebase_initialized or bool(firebase_admin._apps)

def get_firebase_status() -> dict:
    """Get Firebase initialization status for debugging."""
    return {
        "initialized": _firebase_initialized,
        "apps_count": len(firebase_admin._apps) if firebase_admin._apps else 0,
        "available": is_firebase_available()
    }

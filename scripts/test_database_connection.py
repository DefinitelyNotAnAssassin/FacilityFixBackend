#!/usr/bin/env python3
"""
Test script to verify Firestore database connection and setup
"""
import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_database_connection():
    """Test the database connection with proper Firebase initialization"""
    try:
        print("Initializing Firebase...")
        
        from app.core.config import settings
        print(f"Configuration loaded for project: {settings.FIREBASE_PROJECT_ID}")
        
        # Import and initialize Firebase first
        from app.auth.firebase_auth import firebase_auth
        print("Firebase initialized successfully!")
        
        # Now we can safely create the Firestore client
        from app.database.firestore_client import FirestoreClient
        client = FirestoreClient()
        print("Firestore connection successful!")
        
        # Test basic operations
        print("\nTesting database operations...")
        
        # Test creating a test document
        test_data = {
            "test": True,
            "message": "Database connection test",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        doc_id = client.create_document("test_collection", "test_doc", test_data)
        print(f"Created test document with ID: {doc_id}")
        
        # Test reading the document
        retrieved_doc = client.get_document("test_collection", "test_doc")
        if retrieved_doc:
            print(f"Retrieved test document: {retrieved_doc['message']}")
        
        # Clean up test document
        client.delete_document("test_collection", "test_doc")
        print("Cleaned up test document")
        
        print("\nAll database tests passed successfully!")
        return True
        
    except FileNotFoundError as e:
        print(f"Firebase service account file not found: {e}")
        print("\nTo fix this:")
        print("1. Download your Firebase service account key from Firebase Console")
        print(f"2. Save it as '{settings.FIREBASE_SERVICE_ACCOUNT_PATH}' in the backend directory")
        print("3. Or update FIREBASE_SERVICE_ACCOUNT_PATH in your .env file")
        return False
        
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

def check_environment():
    """Check if required environment variables and files are present"""
    print("Checking environment setup...")
    
    from app.core.config import settings
    
    # Check for service account file
    if os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_PATH):
        print(f"Firebase service account found: {settings.FIREBASE_SERVICE_ACCOUNT_PATH}")
    else:
        print(f"Firebase service account not found: {settings.FIREBASE_SERVICE_ACCOUNT_PATH}")
        return False
    
    # Check for project ID
    if settings.FIREBASE_PROJECT_ID:
        print(f"Firebase project ID: {settings.FIREBASE_PROJECT_ID}")
    else:
        print("FIREBASE_PROJECT_ID not set in .env file")
        return False
    
    return True

if __name__ == "__main__":
    print("FacilityFix Database Connection Test")
    print("=" * 50)
    
    if check_environment():
        success = test_database_connection()
        if success:
            print("\nDatabase setup is working correctly!")
            sys.exit(0)
        else:
            print("\nDatabase setup needs attention.")
            sys.exit(1)
    else:
        print("\nEnvironment setup incomplete.")
        sys.exit(1)

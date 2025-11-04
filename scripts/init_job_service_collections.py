"""
Initialize Job Service Requests Collection in Firestore
This script creates the job_service_requests collection structure
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.auth.firebase_auth import firebase_auth  # Initialize Firebase first
import firebase_admin
from firebase_admin import firestore
from datetime import datetime

def init_job_service_requests_collection():
    """Initialize the job_service_requests collection"""
    try:
        # Get Firestore client from Firebase Admin
        db = firestore.client()
        
        print("Initializing job_service_requests collection...")
        
        # Check if collection exists by attempting to get its documents
        collection_ref = db.collection('job_service_requests')
        docs = list(collection_ref.limit(1).stream())
        
        if docs:
            print(f"✓ job_service_requests collection already exists with {len(list(collection_ref.stream()))} documents")
        else:
            # Create a placeholder document to initialize the collection
            # This will be deleted immediately after
            placeholder_id = '_placeholder_init'
            collection_ref.document(placeholder_id).set({
                '_initialized': True,
                'created_at': datetime.utcnow()
            })
            
            # Delete the placeholder
            collection_ref.document(placeholder_id).delete()
            
            print("✓ job_service_requests collection initialized successfully")
        
        # Display collection schema
        print("\nCollection Schema:")
        print("-------------------")
        print("Field Name              | Type      | Description")
        print("-" * 70)
        print("id                      | string    | Unique job service request ID (js_xxxxx)")
        print("formatted_id            | string    | Human-readable ID (JS-YYYY-NNNNN)")
        print("reported_by             | string    | User ID who submitted the request")
        print("title                   | string    | Request title")
        print("description             | string    | Detailed description/notes")
        print("location                | string    | Location for the service")
        print("category                | string    | Service category")
        print("priority                | string    | Priority level (low/medium/high)")
        print("status                  | string    | Current status (pending/in_progress/completed)")
        print("request_type            | string    | Always 'Job Service'")
        print("unit_id                 | string    | Associated unit ID (optional)")
        print("schedule_availability   | string    | Tenant's schedule availability (optional)")
        print("attachments             | array     | List of attachment URLs")
        print("created_at              | timestamp | Creation timestamp")
        print("updated_at              | timestamp | Last update timestamp")
        print("submitted_at            | string    | ISO format submission time")
        print("completed_at            | timestamp | Completion timestamp (optional)")
        
        return True
        
    except Exception as e:
        print(f"Error initializing job_service_requests collection: {e}")
        return False

def verify_firestore_rules():
    """Verify that Firestore rules include job_service_requests"""
    print("\nVerifying Firestore rules...")
    
    rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'firestore.rules')
    
    if os.path.exists(rules_path):
        with open(rules_path, 'r') as f:
            rules_content = f.read()
            
        if 'job_service_requests' in rules_content:
            print("✓ Firestore rules include job_service_requests collection")
            return True
        else:
            print("⚠ Warning: job_service_requests not found in firestore.rules")
            print("Please add security rules for this collection")
            return False
    else:
        print("⚠ Warning: firestore.rules file not found")
        return False

def main():
    """Main initialization function"""
    print("=== Job Service Requests Collection Initialization ===")
    print(f"Project: {settings.FIREBASE_PROJECT_ID}\n")
    
    # Initialize collection
    collection_init = init_job_service_requests_collection()
    
    # Verify rules
    rules_ok = verify_firestore_rules()
    
    print("\n=== Summary ===")
    if collection_init and rules_ok:
        print("✓ Job service requests collection is ready to use")
        print("\nNext steps:")
        print("1. Deploy Firestore rules: firebase deploy --only firestore:rules")
        print("2. Test creating a job service request via the API")
    else:
        print("⚠ Some issues were encountered during initialization")
        if not rules_ok:
            print("- Update firestore.rules to include job_service_requests collection")
            print("- Deploy rules: firebase deploy --only firestore:rules")

if __name__ == "__main__":
    main()

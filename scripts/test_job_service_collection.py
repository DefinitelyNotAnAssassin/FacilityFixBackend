"""
Test Job Service Requests API
Verifies that the job_service_requests collection is working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.database.database_service import DatabaseService
from datetime import datetime
import uuid

async def test_job_service_collection():
    """Test creating and retrieving a job service request"""
    print("=== Testing Job Service Requests Collection ===\n")
    
    db = DatabaseService()
    
    # Test 1: Create a job service request
    print("Test 1: Creating a job service request...")
    job_service_id = f"js_{str(uuid.uuid4())[:8]}"
    
    now = datetime.utcnow()
    year = now.year
    day_of_year = now.timetuple().tm_yday
    formatted_id = f"JS-{year}-{str(day_of_year).zfill(5)}"
    
    test_data = {
        "id": job_service_id,
        "formatted_id": formatted_id,
        "reported_by": "test_user_123",
        "title": "Test Job Service Request",
        "description": "This is a test job service request",
        "location": "Test Location",
        "category": "general",
        "priority": "medium",
        "status": "pending",
        "request_type": "Job Service",
        "unit_id": "test_unit_001",
        "schedule_availability": "Monday-Friday 9AM-5PM",
        "attachments": [],
        "created_at": now,
        "updated_at": now,
        "submitted_at": now.isoformat()
    }
    
    try:
        success, doc_id, error = await db.create_document(
            "job_service_requests",
            test_data,
            job_service_id
        )
        
        if success:
            print(f"✓ Successfully created job service request: {job_service_id}")
            print(f"  Formatted ID: {formatted_id}")
            print(f"  Document ID: {doc_id}")
        else:
            print(f"✗ Failed to create job service request: {error}")
            return False
    except Exception as e:
        print(f"✗ Error creating job service request: {e}")
        return False
    
    # Test 2: Retrieve the job service request
    print("\nTest 2: Retrieving the job service request...")
    try:
        success, jobs, error = await db.query_documents(
            "job_service_requests",
            [("id", job_service_id)]
        )
        
        if success and jobs:
            print(f"✓ Successfully retrieved job service request")
            job = jobs[0]
            print(f"  ID: {job.get('id')}")
            print(f"  Formatted ID: {job.get('formatted_id')}")
            print(f"  Title: {job.get('title')}")
            print(f"  Status: {job.get('status')}")
        else:
            print(f"✗ Failed to retrieve job service request: {error}")
            return False
    except Exception as e:
        print(f"✗ Error retrieving job service request: {e}")
        return False
    
    # Test 3: Update the job service request
    print("\nTest 3: Updating job service request status...")
    try:
        # Get all documents to find the Firebase document ID
        all_jobs = await db.get_all_documents("job_service_requests")
        firebase_doc_id = None
        
        for job in all_jobs:
            if job.get("id") == job_service_id:
                firebase_doc_id = job.get("_firebase_doc_id")
                break
        
        if firebase_doc_id:
            success, error = await db.update_document(
                "job_service_requests",
                firebase_doc_id,
                {
                    "status": "in_progress",
                    "updated_at": datetime.utcnow()
                }
            )
            
            if success:
                print(f"✓ Successfully updated job service request status")
            else:
                print(f"✗ Failed to update job service request: {error}")
                return False
        else:
            print("✗ Could not find Firebase document ID")
            return False
    except Exception as e:
        print(f"✗ Error updating job service request: {e}")
        return False
    
    # Test 4: Query by status
    print("\nTest 4: Querying job service requests by status...")
    try:
        success, jobs, error = await db.query_documents(
            "job_service_requests",
            [("status", "in_progress")]
        )
        
        if success:
            print(f"✓ Successfully queried job service requests")
            print(f"  Found {len(jobs)} in_progress requests")
        else:
            print(f"✗ Failed to query job service requests: {error}")
            return False
    except Exception as e:
        print(f"✗ Error querying job service requests: {e}")
        return False
    
    # Cleanup: Delete test document
    print("\nCleaning up test data...")
    try:
        if firebase_doc_id:
            success, error = await db.delete_document("job_service_requests", firebase_doc_id)
            if success:
                print(f"✓ Test data cleaned up successfully")
            else:
                print(f"⚠ Warning: Could not clean up test data: {error}")
    except Exception as e:
        print(f"⚠ Warning: Error during cleanup: {e}")
    
    print("\n=== All Tests Passed! ===")
    print("The job_service_requests collection is working correctly.")
    return True

async def main():
    """Run all tests"""
    try:
        result = await test_job_service_collection()
        if result:
            print("\n✓ Job service requests collection is ready for use!")
        else:
            print("\n✗ Some tests failed. Please check the errors above.")
    except Exception as e:
        print(f"\n✗ Test execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())

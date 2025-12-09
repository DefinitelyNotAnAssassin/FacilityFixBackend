"""
Migration script to add formatted IDs to existing inventory requests
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.database_service import DatabaseService
from app.database.collections import COLLECTIONS
from app.services.inventory_request_id_service import inventory_request_id_service
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
cred = credentials.Certificate("firebase-service-account.json")
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

# Initialize database service
db_service = DatabaseService()

async def migrate_inventory_request_ids():
    """Add formatted IDs to all existing inventory requests that don't have them"""
    
    print("=" * 70)
    print("MIGRATION: Add Formatted IDs to Inventory Requests")
    print("=" * 70)
    
    # Get all inventory requests
    success, requests, error = await db_service.query_documents(
        COLLECTIONS['inventory_requests'],
        []
    )
    
    if not success:
        print(f"Failed to fetch inventory requests: {error}")
        return
    
    print(f"\nFound {len(requests)} total inventory requests")
    
    # Filter requests that don't have formatted_id
    requests_without_id = [r for r in requests if not r.get('formatted_id')]
    print(f"{len(requests_without_id)} requests need formatted IDs")
    
    if len(requests_without_id) == 0:
        print("\nAll inventory requests already have formatted IDs!")
        return
    
    # Sort by created_at to assign IDs in chronological order
    requests_without_id.sort(key=lambda x: x.get('created_at', datetime.min))
    
    updated_count = 0
    failed_count = 0
    
    print("\nStarting migration...\n")
    
    for request in requests_without_id:
        request_id = request.get('_doc_id') or request.get('id')
        created_at = request.get('created_at', datetime.now())
        
        try:
            # Generate formatted ID
            formatted_id = await inventory_request_id_service.generate_inventory_request_id()
            
            # Update the request
            update_success, update_error = await db_service.update_document(
                COLLECTIONS['inventory_requests'],
                request_id,
                {'formatted_id': formatted_id},
                validate=False
            )
            
            if update_success:
                print(f"[OK] {request_id} -> {formatted_id}")
                updated_count += 1
            else:
                print(f"[FAIL] {request_id}: {update_error}")
                failed_count += 1
                
        except Exception as e:
            print(f"[ERROR] {request_id}: {str(e)}")
            failed_count += 1
    
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"Successfully updated: {updated_count}")
    print(f"Failed: {failed_count}")
    print(f"Total processed: {len(requests_without_id)}")
    print(f"Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_inventory_request_ids())

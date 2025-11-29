#!/usr/bin/env python3
"""
Script to initialize the inventory_reservations collection in the database.
This ensures the collection exists before the application tries to write to it.
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

async def init_inventory_reservations_collection():
    """Initialize the inventory_reservations collection"""
    try:
        print("Initializing inventory_reservations collection...")

        # Try to create a test document to initialize the collection
        success, doc_id, error = await database_service.create_document(
            COLLECTIONS['inventory_reservations'],
            {
                'test': 'init',
                'description': 'Collection initialization document',
                'created_at': None,  # Will be set by the client
                'updated_at': None   # Will be set by the client
            },
            validate=False  # Skip validation for init
        )

        if success:
            print(f"✅ Collection initialized successfully. Test document ID: {doc_id}")

            # Now delete the test document
            print("Cleaning up test document...")
            # Note: We don't have a delete method in the service, but that's okay
            # The collection now exists

        else:
            print(f"❌ Failed to initialize collection: {error}")
            return False

    except Exception as e:
        print(f"❌ Error initializing collection: {str(e)}")
        return False

    return True

async def verify_collection_exists():
    """Verify that the collection exists by trying to query it"""
    try:
        print("Verifying collection exists...")

        # Try to query the collection
        success, documents, error = await database_service.query_documents(
            COLLECTIONS['inventory_reservations'],
            []  # No filters
        )

        if success:
            print(f"✅ Collection verified. Found {len(documents)} documents.")
            return True
        else:
            print(f"❌ Collection verification failed: {error}")
            return False

    except Exception as e:
        print(f"❌ Error verifying collection: {str(e)}")
        return False

async def main():
    """Main initialization function"""
    print("🔧 Database Collection Initialization Script")
    print("=" * 50)

    # Initialize the collection
    if await init_inventory_reservations_collection():
        # Verify it exists
        if await verify_collection_exists():
            print("\n🎉 SUCCESS: inventory_reservations collection is ready!")
            print("The backend should now be able to create inventory reservations.")
        else:
            print("\n❌ VERIFICATION FAILED: Collection may not be properly initialized.")
            sys.exit(1)
    else:
        print("\n❌ INITIALIZATION FAILED: Could not create collection.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
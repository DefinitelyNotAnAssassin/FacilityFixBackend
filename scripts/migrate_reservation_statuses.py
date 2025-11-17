#!/usr/bin/env python3
"""
Migration script to update existing inventory reservation statuses from 'active' to 'reserved'
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.database_service import DatabaseService
from app.database.collections import COLLECTIONS

async def migrate_reservation_statuses():
    """Update all inventory reservations with status 'active' to 'reserved'"""
    db = DatabaseService()

    try:
        # Connect to database
        await db.connect()

        # Query for reservations with status 'active'
        query = [('status', '==', 'active')]
        success, documents, error = await db.query_documents(COLLECTIONS['inventory_reservations'], query)

        if not success:
            print(f"Error querying reservations: {error}")
            return

        print(f"Found {len(documents)} reservations with status 'active'")

        # Update each reservation
        updated_count = 0
        for doc in documents:
            update_data = {'status': 'reserved'}
            success, error = await db.update_document(
                COLLECTIONS['inventory_reservations'],
                doc['id'],
                update_data
            )

            if success:
                updated_count += 1
                print(f"Updated reservation {doc['id']}: active -> reserved")
            else:
                print(f"Error updating reservation {doc['id']}: {error}")

        print(f"Successfully updated {updated_count} reservations")

    except Exception as e:
        print(f"Migration failed: {str(e)}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate_reservation_statuses())
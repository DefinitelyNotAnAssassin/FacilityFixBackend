"""
Migration script to fix announcement document IDs.

This script updates existing announcements so that their Firestore document ID
matches the 'id' field in their data. This ensures announcements can be
retrieved by their ID.

NOTE: This is optional now since the backend automatically normalizes IDs
in the get_announcements() response. However, running this will fix the
underlying data for consistency.

Run this once to fix legacy announcements created before the fix.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.database_service import database_service
from app.database.collections import COLLECTIONS


async def migrate_announcements():
    """Migrate announcement document IDs to match their data 'id' field"""
    
    print("Starting announcement ID migration...")
    
    try:
        # Get all announcements
        success, announcements, error = await database_service.query_documents(
            COLLECTIONS['announcements'],
            limit=1000
        )
        
        if not success:
            print(f"❌ Failed to fetch announcements: {error}")
            return
        
        print(f"Found {len(announcements)} announcements to check")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for ann in announcements:
            doc_id = ann.get('_doc_id')
            data_id = ann.get('id')
            formatted_id = ann.get('formatted_id', 'N/A')
            
            if not doc_id or not data_id:
                print(f"⚠️  Skipping announcement with missing IDs: {formatted_id}")
                skipped_count += 1
                continue
            
            # Check if migration is needed
            if doc_id == data_id:
                print(f"✓ Already correct: {formatted_id} (ID: {doc_id})")
                skipped_count += 1
                continue
            
            print(f"→ Migrating {formatted_id}: {doc_id} → {data_id}")
            
            try:
                # Create new document with correct ID
                # Remove _doc_id from data before copying
                ann_data = {k: v for k, v in ann.items() if k != '_doc_id'}
                
                success_create, new_doc_id, error_create = await database_service.create_document(
                    COLLECTIONS['announcements'],
                    ann_data,
                    document_id=data_id
                )
                
                if not success_create:
                    print(f"  ❌ Failed to create new document: {error_create}")
                    error_count += 1
                    continue
                
                # Delete old document
                success_delete, error_delete = await database_service.delete_document(
                    COLLECTIONS['announcements'],
                    doc_id
                )
                
                if not success_delete:
                    print(f"  ⚠️  Created new but failed to delete old: {error_delete}")
                    # This is not critical - the new one exists
                
                print(f"  ✓ Migrated successfully")
                migrated_count += 1
                
            except Exception as e:
                print(f"  ❌ Error migrating: {e}")
                error_count += 1
        
        print("\n" + "="*60)
        print("Migration Summary:")
        print(f"  Total announcements: {len(announcements)}")
        print(f"  ✓ Migrated: {migrated_count}")
        print(f"  - Skipped (already correct): {skipped_count}")
        print(f"  ❌ Errors: {error_count}")
        print("="*60)
        
        if error_count > 0:
            print("\n⚠️  Some announcements failed to migrate. Check the output above.")
        elif migrated_count > 0:
            print("\n✅ Migration completed successfully!")
        else:
            print("\n✓ No migration needed - all announcements already have correct IDs.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Announcement ID Migration Tool")
    print("=" * 60)
    asyncio.run(migrate_announcements())

"""
Firebase Storage initialization and utilities.
Handles bucket setup and storage configuration.
"""

from firebase_admin import storage
from google.cloud.exceptions import NotFound
import logging
from typing import Optional
import os

logger = logging.getLogger(__name__)

_storage_bucket = None

def initialize_storage() -> Optional[object]:
    """
    Initialize Firebase Storage bucket.
    Must be called after Firebase Admin SDK initialization.
    
    Returns:
        Storage bucket object if successful, None otherwise
    """
    global _storage_bucket
    
    if _storage_bucket is not None:
        logger.info("✅ Storage bucket already initialized")
        return _storage_bucket
    
    try:
        # Use the same default bucket format that Firebase client config uses
        # (firebasestorage.app). This avoids mismatches where the frontend
        # firebase_options uses '...firebasestorage.app' but backend defaulted
        # to '...appspot.com'. Prefer environment variable when set.
        bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET', 'facilityfix-6d27a.firebasestorage.app')
        _storage_bucket = storage.bucket(bucket_name)
        
        # If possible, perform an explicit existence check using google-cloud-storage client
        try:
            from google.cloud import storage as gcs_storage
            gcs_client = gcs_storage.Client()
            try:
                gcs_client.get_bucket(bucket_name)
            except Exception as be:
                logger.error(f"❌ Configured bucket '{bucket_name}' is not accessible: {be}")
                return None
        except Exception:
            # google-cloud-storage not available or client failed; fall back to best-effort
            pass
        
        if not _storage_bucket:
            logger.error("❌ Failed to get storage bucket - bucket is None")
            return None
        
        # Verify bucket exists by checking if it's accessible
        bucket_name = _storage_bucket.name
        logger.info(f"✅ Firebase Storage initialized: gs://{bucket_name}")
        
        return _storage_bucket
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase Storage: {e}")
        logger.error("Ensure:")
        logger.error("  1. Firebase project has Cloud Storage enabled")
        logger.error("  2. Default bucket is set in Firebase Console")
        logger.error("  3. Service account has storage.buckets.get permissions")
        logger.error(f"  4. Bucket name: {os.getenv('FIREBASE_STORAGE_BUCKET', 'facilityfix-6d27a.firebasestorage.app')}")
        return None

def get_storage_bucket() -> Optional[object]:
    """
    Get the Firebase Storage bucket.
    Initializes on first call if not already initialized.
    """
    global _storage_bucket
    
    if _storage_bucket is None:
        _storage_bucket = initialize_storage()
    
    return _storage_bucket

def is_storage_available() -> bool:
    """Check if Firebase Storage is available and initialized."""
    bucket = get_storage_bucket()
    return bucket is not None

def get_bucket_info() -> dict:
    """Get storage bucket information for debugging."""
    bucket = get_storage_bucket()
    
    if not bucket:
        return {
            "available": False,
            "error": "Storage bucket not initialized"
        }
    
    try:
        return {
            "available": True,
            "bucket_name": bucket.name,
            "bucket_path": f"gs://{bucket.name}",
            "location": getattr(bucket, 'location', 'unknown'),
            "storage_class": getattr(bucket, 'storage_class', 'STANDARD')
        }
    except Exception as e:
        logger.error(f"Error getting bucket info: {e}")
        return {
            "available": False,
            "error": str(e)
        }

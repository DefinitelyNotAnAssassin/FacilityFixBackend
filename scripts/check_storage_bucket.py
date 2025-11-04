from app.services.firebase_storage_init import get_bucket_info
from app.core.firebase_init import initialize_firebase
import json

if __name__ == '__main__':
    # Ensure Firebase Admin is initialized using local service account if present
    initialize_firebase()
    print(json.dumps(get_bucket_info(), indent=2, default=str))

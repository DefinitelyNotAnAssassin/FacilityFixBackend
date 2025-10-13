from firebase_admin import firestore
from typing import Optional, Dict, List, Any
import firebase_admin
from datetime import datetime
from ..core.firebase_init import initialize_firebase, is_firebase_available

class FirestoreClient:
    def __init__(self):
        # Try to initialize Firebase if not already done
        if not is_firebase_available():
            if not initialize_firebase():
                raise Exception("Firebase initialization failed - Firestore not available")
        
        self.db = firestore.client()
    
    def create_document(self, collection: str, document_id: str = None, data: Dict[str, Any] = None) -> str:
        """Create a new document in a collection"""
        try:
            data = data or {}
            data['created_at'] = datetime.utcnow()
            data['updated_at'] = datetime.utcnow()
            
            if document_id:
                doc_ref = self.db.collection(collection).document(document_id)
                doc_ref.set(data)
                return document_id
            else:
                doc_ref = self.db.collection(collection).add(data)
                return doc_ref[1].id
        except Exception as e:
            raise Exception(f"Error creating document: {e}")
    
    def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            return None
        except Exception as e:
            raise Exception(f"Error getting document: {e}")
    
    def update_document(self, collection: str, document_id: str, data: Dict[str, Any]) -> bool:
        """Update a document"""
        try:
            data['updated_at'] = datetime.utcnow()
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.update(data)
            return True
        except Exception as e:
            raise Exception(f"Error updating document: {e}")
    
    def delete_document(self, collection: str, document_id: str) -> bool:
        """Delete a document"""
        try:
            doc_ref = self.db.collection(collection).document(document_id)
            doc_ref.delete()
            return True
        except Exception as e:
            raise Exception(f"Error deleting document: {e}")
    
    def get_collection(self, collection: str, filters: List[tuple] = None, limit: int = None) -> List[Dict[str, Any]]:
        """Get documents from a collection with optional filters"""
        try:
            query = self.db.collection(collection)
            
            if filters:
                for field, operator, value in filters:
                    query = query.where(field, operator, value)
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                results.append(data)
            
            return results
        except Exception as e:
            raise Exception(f"Error getting collection: {e}")

firestore_client = None

def get_firestore_client():
    """Get or create Firestore client instance"""
    global firestore_client
    if firestore_client is None:
        try:
            firestore_client = FirestoreClient()
        except Exception as e:
            print(f"Warning: Firestore client not initialized: {e}")
            return None
    return firestore_client

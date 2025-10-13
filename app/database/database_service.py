from typing import Dict, Any, List, Optional, Sequence, Tuple
from .firestore_client import get_firestore_client
from .schema_validator import schema_validator
from .collections import COLLECTIONS
from datetime import datetime
import anyio
from ..core.firebase_init import initialize_firebase, is_firebase_available

class DatabaseService:
    """High-level database service with validation and error handling"""
    
    def __init__(self):
        if not is_firebase_available():
            initialize_firebase()
        
        self.client = get_firestore_client()
        if not self.client:
            print("Warning: Firestore client not available - database operations will fail")
            self.client = None
    
    def _check_client_available(self):
        """Check if Firestore client is available, raise exception if not"""
        if not self.client:
            raise Exception("Firestore client not available - ensure Firebase is properly initialized")
    
    # ── helper: try to get a raw Firestore client that supports .collection() ──
    def _raw_firestore(self):
        for attr in ("db", "client", "_client"):
            raw = getattr(self.client, attr, None)
            if raw is not None and hasattr(raw, "collection"):
                return raw
        # Some wrappers *are* the raw client already
        if hasattr(self.client, "collection"):
            return self.client
        return None
    
    async def create_document(self, collection: str, data: Dict[str, Any], 
                            document_id: str = None, validate: bool = True) -> tuple[bool, str, Optional[str]]:
        """
        Create a document with validation
        
        Args:
            collection: Collection name
            data: Document data
            document_id: Optional custom document ID (if None, auto-generates)
            validate: Whether to validate against schema
            
        Returns:
            Tuple of (success, document_id_or_error, error_message)
        """
        try:
            self._check_client_available()
            
            # Validate schema if requested
            if validate:
                is_valid, error_msg = schema_validator.validate_document(collection, data)
                if not is_valid:
                    return False, f"Validation failed: {error_msg}", error_msg
            
            # Create document with custom ID if provided
            doc_id = self.client.create_document(collection, document_id=document_id, data=data)
            return True, doc_id, None
            
        except Exception as e:
            error_msg = f"Failed to create document in {collection}: {str(e)}"
            return False, error_msg, error_msg
    
    async def get_document(self, collection: str, document_id: str) -> tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Get a document by ID
        
        Returns:
            Tuple of (success, document_data, error_message)
        """
        try:
            self._check_client_available()
            
            doc_data = self.client.get_document(collection, document_id)
            if doc_data:
                return True, doc_data, None
            else:
                return False, None, f"Document {document_id} not found in {collection}"
                
        except Exception as e:
            error_msg = f"Failed to get document {document_id} from {collection}: {str(e)}"
            return False, None, error_msg
    
    async def update_document(self, collection: str, document_id: str, 
                            data: Dict[str, Any], validate: bool = True) -> tuple[bool, Optional[str]]:
        """
        Update a document with validation
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get existing document for validation
            if validate:
                existing_doc = self.client.get_document(collection, document_id)
                if not existing_doc:
                    return False, f"Document {document_id} not found in {collection}"
                
                # Merge with existing data for validation
                merged_data = {**existing_doc, **data}
                is_valid, error_msg = schema_validator.validate_document(collection, merged_data)
                if not is_valid:
                    return False, f"Validation failed: {error_msg}"
            
            # Update document
            success = self.client.update_document(collection, document_id, data)
            if success:
                return True, None
            else:
                return False, "Update operation failed"
                
        except Exception as e:
            error_msg = f"Failed to update document {document_id} in {collection}: {str(e)}"
            return False, error_msg
    
    async def delete_document(self, collection: str, document_id: str) -> tuple[bool, Optional[str]]:
        """
        Delete a document
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            success = self.client.delete_document(collection, document_id)
            if success:
                return True, None
            else:
                return False, "Delete operation failed"
                
        except Exception as e:
            error_msg = f"Failed to delete document {document_id} from {collection}: {str(e)}"
            return False, error_msg
    
    async def query_collection(self, collection: str, filters: List[tuple] = None, 
                             limit: int = None) -> tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Query a collection with filters (delegates to query_documents)."""
        return await self.query_documents(collection, filters, limit)
    
    async def query_documents(self, collection: str, filters: List[tuple] = None, 
                            limit: int = None) -> tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Query documents in a collection.

        filters: list of tuples. Each tuple can be:
          - (field, value) -> uses '=='
          - (field, op, value) -> explicit operator (==, >, >=, <, <=, array_contains, in, etc.)
        limit: optional max number of docs.
        Returns: (success, [docs], error). Each doc includes '_doc_id'.
        """
        try:
            self._check_client_available()
        except Exception as e:
            return False, [], str(e)
        
        raw = self._raw_firestore()

        # If we can reach the raw client, use it (fastest & includes doc ids)
        if raw is not None:
            def _run():
                q = raw.collection(collection)
                if filters:
                    for f in filters:
                        if len(f) == 3:
                            field, op, value = f
                        elif len(f) == 2:
                            field, value = f
                            op = "=="
                        else:
                            raise ValueError("Invalid filter tuple format")
                        q = q.where(field, op, value)
                if limit:
                    q = q.limit(limit)
                # stream() yields DocumentSnapshot; add Firestore doc id
                out = []
                for snap in q.stream():
                    data = snap.to_dict() or {}
                    data["_doc_id"] = snap.id
                    out.append(data)
                return out

            try:
                docs = await anyio.to_thread.run_sync(_run)
                return True, docs, None
            except Exception as e:
                return False, [], f"Failed to query {collection}: {e}"

        # Fallback: use your wrapper's get_collection()
        try:
            documents = self.client.get_collection(collection, filters, limit)
            # Best-effort: ensure a _doc_id field if wrapper returns an 'id'
            normalized = []
            for d in documents or []:
                if isinstance(d, dict):
                    if "_doc_id" not in d and "id" in d:
                        d = {**d, "_doc_id": d["id"]}
                normalized.append(d)
            return True, normalized, None
        except Exception as e:
            return False, [], f"Failed to query collection {collection}: {e}"
    
    async def get_all_documents(self, collection: str) -> List[Dict[str, Any]]:
        """
        Get all documents from a Firestore collection.
        Returns a list of dictionaries with Firestore doc IDs included as '_doc_id'.
        """
        raw = self._raw_firestore()

        if raw is not None:
            # Use the raw firestore client
            def _run():
                out = []
                for snap in raw.collection(collection).stream():
                    data = snap.to_dict() or {}
                    data["_doc_id"] = snap.id
                    out.append(data)
                return out

            try:
                docs = await anyio.to_thread.run_sync(_run)
                return docs
            except Exception as e:
                raise Exception(f"Failed to fetch documents from {collection}: {e}")

        # Fallback: if wrapper client exposes get_collection()
        try:
            documents = self.client.get_collection(collection)
            normalized = []
            for d in documents or []:
                if isinstance(d, dict):
                    if "_doc_id" not in d and "id" in d:
                        d = {**d, "_doc_id": d["id"]}
                normalized.append(d)
            return normalized
        except Exception as e:
            raise Exception(f"Failed to fetch documents from {collection}: {e}")
    
    async def get_building_data(self, building_id: str) -> tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Get comprehensive building data including units, equipment, etc.
        
        Returns:
            Tuple of (success, building_data, error_message)
        """
        try:
            # Get building info
            building_success, building_data, building_error = await self.get_document('buildings', building_id)
            if not building_success:
                return False, {}, building_error
            
            # Get related data
            units_success, units, _ = await self.query_collection('units', [('building_id', '==', building_id)])
            equipment_success, equipment, _ = await self.query_collection('equipment', [('building_id', '==', building_id)])
            inventory_success, inventory, _ = await self.query_collection('inventory', [('building_id', '==', building_id)])
            
            # Combine data
            comprehensive_data = {
                'building': building_data,
                'units': units if units_success else [],
                'equipment': equipment if equipment_success else [],
                'inventory': inventory if inventory_success else []
            }
            
            return True, comprehensive_data, None
            
        except Exception as e:
            error_msg = f"Failed to get building data for {building_id}: {str(e)}"
            return False, {}, error_msg

try:
    database_service = DatabaseService()
except Exception as e:
    print(f"Warning: Failed to initialize database service: {e}")
    database_service = None

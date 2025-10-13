import os
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import mimetypes
from pathlib import Path

from firebase_admin import storage
from google.cloud.exceptions import NotFound
from fastapi import HTTPException, UploadFile
import logging

from ..core.firebase_init import is_firebase_available
from ..database.firestore_client import get_firestore_client
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)

class FileStorageService:
    """
    Service for managing file uploads, downloads, and organization in Firebase Storage.
    Implements secure access controls and proper file organization.
    """
    
    def __init__(self):
        self.bucket = None
        if is_firebase_available():
            try:
                self.bucket = ""
                logger.info("✅ Firebase Storage initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Firebase Storage: {e}")

        # Define allowed file types and size limits
        self.allowed_image_types = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'
        }
        self.allowed_document_types = {
            'application/pdf', 'application/msword', 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain', 'text/csv'
        }
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.max_image_size = 5 * 1024 * 1024   # 5MB
    
    def _validate_file(self, file: UploadFile, file_type: str = "any") -> bool:
        """Validate file type and size"""
        if not file.content_type:
            raise HTTPException(status_code=400, detail="Unable to determine file type")
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_type == "image":
            if file.content_type not in self.allowed_image_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid image type. Allowed: {', '.join(self.allowed_image_types)}"
                )
            if file_size > self.max_image_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Image too large. Maximum size: {self.max_image_size / (1024*1024):.1f}MB"
                )
        elif file_type == "document":
            if file.content_type not in self.allowed_document_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid document type. Allowed: {', '.join(self.allowed_document_types)}"
                )
            if file_size > self.max_file_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Document too large. Maximum size: {self.max_file_size / (1024*1024):.1f}MB"
                )
        else:  # any file type
            allowed_types = self.allowed_image_types.union(self.allowed_document_types)
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid file type"
                )
            if file_size > self.max_file_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File too large. Maximum size: {self.max_file_size / (1024*1024):.1f}MB"
                )
        
        return True
    
    def _generate_file_path(self, entity_type: str, entity_id: str, 
                          file_type: str, original_filename: str) -> str:
        """Generate organized file path based on entity type and ID"""
        # Get file extension
        file_ext = Path(original_filename).suffix.lower()
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{unique_id}{file_ext}"
        
        # Organize by entity type as specified in requirements
        path_mapping = {
            "repair_requests": f"repair_requests/{entity_id}/attachments/{filename}",
            "concern_slips": f"repair_requests/{entity_id}/attachments/{filename}",
            "maintenance_tasks": f"maintenance_tasks/{entity_id}/reports/{filename}",
            "job_services": f"maintenance_tasks/{entity_id}/reports/{filename}",
            "work_order_permits": f"maintenance_tasks/{entity_id}/reports/{filename}",
            "announcements": f"announcements/{entity_id}/attachments/{filename}",
            "inventory": f"inventory/{entity_id}/documents/{filename}",
            "equipment": f"equipment/{entity_id}/documents/{filename}",
            "user_profiles": f"users/{entity_id}/documents/{filename}",
            "maintenance_reports": f"reports/{entity_id}/{filename}",
            "admin_documents": f"admin/documents/{filename}"
        }
        
        return path_mapping.get(entity_type, f"general/{entity_type}/{entity_id}/{filename}")
    
    async def upload_file(self, file: UploadFile, entity_type: str, entity_id: str, 
                         uploaded_by: str, file_type: str = "any", 
                         description: str = None) -> Dict[str, Any]:
        """
        Upload file to Firebase Storage with metadata tracking
        
        Args:
            file: The uploaded file
            entity_type: Type of entity (repair_requests, maintenance_tasks, etc.)
            entity_id: ID of the related entity
            uploaded_by: User ID who uploaded the file
            file_type: Expected file type (image, document, any)
            description: Optional file description
        
        Returns:
            Dict containing file metadata
        """
        if not self.bucket:
            raise HTTPException(status_code=500, detail="File storage not available")
        
        # Validate file
        self._validate_file(file, file_type)
        
        try:
            # Generate file path
            file_path = self._generate_file_path(entity_type, entity_id, file_type, file.filename)
            
            # Upload to Firebase Storage
            blob = self.bucket.blob(file_path)
            
            # Set metadata
            blob.metadata = {
                'uploaded_by': uploaded_by,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'original_filename': file.filename,
                'file_type': file_type,
                'description': description or '',
                'upload_timestamp': datetime.now().isoformat()
            }
            
            # Upload file content
            file_content = await file.read()
            blob.upload_from_string(file_content, content_type=file.content_type)
            
            # Make file accessible with signed URL (valid for 1 hour by default)
            signed_url = blob.generate_signed_url(
                expiration=datetime.now() + timedelta(hours=1),
                method='GET'
            )
            
            # Store file metadata in Firestore
            file_metadata = {
                'id': str(uuid.uuid4()),
                'file_path': file_path,
                'original_filename': file.filename,
                'file_size': len(file_content),
                'content_type': file.content_type,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'uploaded_by': uploaded_by,
                'file_type': file_type,
                'description': description,
                'storage_url': f"gs://{self.bucket.name}/{file_path}",
                'public_url': signed_url,
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Save metadata to Firestore
            db = get_firestore_client()
            doc_ref = db.collection('file_attachments').document(file_metadata['id'])
            doc_ref.set(file_metadata)
            
            logger.info(f"✅ File uploaded successfully: {file_path}")
            return file_metadata
            
        except Exception as e:
            logger.error(f"❌ File upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    async def get_file_url(self, file_id: str, user_id: str, 
                          expiration_hours: int = 1) -> str:
        """
        Generate signed URL for file access with permission checking
        
        Args:
            file_id: File metadata ID
            user_id: User requesting access
            expiration_hours: URL expiration time in hours
        
        Returns:
            Signed URL for file access
        """
        if not self.bucket:
            raise HTTPException(status_code=500, detail="File storage not available")
        
        try:
            # Get file metadata
            db = get_firestore_client()
            doc_ref = db.collection('file_attachments').document(file_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise HTTPException(status_code=404, detail="File not found")
            
            file_data = doc.to_dict()
            
            # Check access permissions
            if not await self._check_file_access(file_data, user_id):
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Generate signed URL
            blob = self.bucket.blob(file_data['file_path'])
            signed_url = blob.generate_signed_url(
                expiration=datetime.now() + timedelta(hours=expiration_hours),
                method='GET'
            )
            
            return signed_url
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to generate file URL: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate file URL")
    
    async def _check_file_access(self, file_data: Dict[str, Any], user_id: str) -> bool:
        """
        Check if user has access to the file based on access rules
        
        Access Rules:
        - Tenants: Can access their own request images and related announcements
        - Staff: Can access reports tied to assigned tasks and inventory files
        - Admins: Full access to all files
        """
        try:
            # Get user profile to determine role
            db = get_firestore_client()
            user_doc = db.collection(COLLECTIONS['user_profiles']).document(user_id).get()
            
            if not user_doc.exists:
                return False
            
            user_data = user_doc.to_dict()
            user_role = user_data.get('role', '').lower()
            
            # Admin has full access
            if user_role == 'admin':
                return True
            
            entity_type = file_data.get('entity_type')
            entity_id = file_data.get('entity_id')
            uploaded_by = file_data.get('uploaded_by')
            
            # User can always access files they uploaded
            if uploaded_by == user_id:
                return True
            
            # Role-based access control
            if user_role == 'tenant':
                # Tenants can access their own repair request attachments
                if entity_type in ['repair_requests', 'concern_slips']:
                    # Check if the concern slip belongs to the tenant
                    concern_doc = db.collection(COLLECTIONS['concern_slips']).document(entity_id).get()
                    if concern_doc.exists:
                        concern_data = concern_doc.to_dict()
                        return concern_data.get('reported_by') == user_id
                
                # Tenants can access public announcements
                elif entity_type == 'announcements':
                    announcement_doc = db.collection(COLLECTIONS['announcements']).document(entity_id).get()
                    if announcement_doc.exists:
                        announcement_data = announcement_doc.to_dict()
                        audience = announcement_data.get('audience', 'all')
                        return audience in ['all', 'tenants']
            
            elif user_role == 'staff':
                # Staff can access files related to their assigned tasks
                if entity_type in ['maintenance_tasks', 'job_services']:
                    task_doc = db.collection(COLLECTIONS[entity_type]).document(entity_id).get()
                    if task_doc.exists:
                        task_data = task_doc.to_dict()
                        return task_data.get('assigned_to') == user_id
                
                # Staff can access inventory and equipment files
                elif entity_type in ['inventory', 'equipment']:
                    return True
                
                # Staff can access announcements for staff
                elif entity_type == 'announcements':
                    announcement_doc = db.collection(COLLECTIONS['announcements']).document(entity_id).get()
                    if announcement_doc.exists:
                        announcement_data = announcement_doc.to_dict()
                        audience = announcement_data.get('audience', 'all')
                        return audience in ['all', 'staff']
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking file access: {e}")
            return False
    
    async def list_files(self, entity_type: str, entity_id: str, 
                        user_id: str) -> List[Dict[str, Any]]:
        """
        List all files for a specific entity with access control
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            user_id: User requesting the list
        
        Returns:
            List of file metadata
        """
        try:
            db = get_firestore_client()
            
            # Query files for the entity
            files_ref = db.collection('file_attachments')
            query = files_ref.where('entity_type', '==', entity_type)\
                            .where('entity_id', '==', entity_id)\
                            .where('is_active', '==', True)
            
            files = []
            for doc in query.stream():
                file_data = doc.to_dict()
                file_data['id'] = doc.id
                
                # Check access permissions
                if await self._check_file_access(file_data, user_id):
                    # Remove sensitive data
                    safe_file_data = {
                        'id': file_data['id'],
                        'original_filename': file_data['original_filename'],
                        'file_size': file_data['file_size'],
                        'content_type': file_data['content_type'],
                        'file_type': file_data['file_type'],
                        'description': file_data.get('description', ''),
                        'created_at': file_data['created_at'],
                        'uploaded_by': file_data['uploaded_by']
                    }
                    files.append(safe_file_data)
            
            return files
            
        except Exception as e:
            logger.error(f"❌ Error listing files: {e}")
            raise HTTPException(status_code=500, detail="Failed to list files")
    
    async def delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Delete file with permission checking
        
        Args:
            file_id: File metadata ID
            user_id: User requesting deletion
        
        Returns:
            True if successful
        """
        if not self.bucket:
            raise HTTPException(status_code=500, detail="File storage not available")
        
        try:
            # Get file metadata
            db = get_firestore_client()
            doc_ref = db.collection('file_attachments').document(file_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise HTTPException(status_code=404, detail="File not found")
            
            file_data = doc.to_dict()
            
            # Check if user can delete (admin or file owner)
            user_doc = db.collection(COLLECTIONS['user_profiles']).document(user_id).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_role = user_data.get('role', '').lower()
                
                if user_role != 'admin' and file_data.get('uploaded_by') != user_id:
                    raise HTTPException(status_code=403, detail="Access denied")
            else:
                raise HTTPException(status_code=403, detail="Access denied")
            
            # Delete from Firebase Storage
            blob = self.bucket.blob(file_data['file_path'])
            blob.delete()
            
            # Mark as inactive in Firestore (soft delete)
            doc_ref.update({
                'is_active': False,
                'deleted_at': datetime.now(),
                'deleted_by': user_id
            })
            
            logger.info(f"✅ File deleted successfully: {file_data['file_path']}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ File deletion failed: {e}")
            raise HTTPException(status_code=500, detail="File deletion failed")

# Global instance
file_storage_service = FileStorageService()

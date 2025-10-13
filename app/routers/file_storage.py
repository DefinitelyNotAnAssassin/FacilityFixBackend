from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from typing import List, Optional
import logging

from ..auth.dependencies import get_current_user
from ..services.file_storage_service import file_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["File Storage"])

@router.post("/upload")
async def upload_file(
    entity_type: str = Form(..., description="Type of entity (repair_requests, maintenance_tasks, etc.)"),
    entity_id: str = Form(..., description="ID of the related entity"),
    file_type: str = Form(default="any", description="Expected file type (image, document, any)"),
    description: Optional[str] = Form(None, description="Optional file description"),
    file: UploadFile = File(..., description="File to upload"),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a file and associate it with an entity.
    
    **Supported entity types:**
    - repair_requests / concern_slips: Repair request photos and documents
    - maintenance_tasks / job_services: Maintenance reports and completion photos
    - work_order_permits: Work permit documents
    - announcements: Announcement attachments
    - inventory: Inventory item photos and documents
    - equipment: Equipment manuals and photos
    - admin_documents: Official administrative documents
    
    **File types:**
    - image: JPEG, PNG, GIF, WebP (max 5MB)
    - document: PDF, Word, Excel, Text, CSV (max 10MB)
    - any: Any supported file type
    """
    try:
        user_id = current_user.get('uid')
        
        result = await file_storage_service.upload_file(
            file=file,
            entity_type=entity_type,
            entity_id=entity_id,
            uploaded_by=user_id,
            file_type=file_type,
            description=description
        )
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "file_id": result['id'],
            "filename": result['original_filename'],
            "file_size": result['file_size'],
            "content_type": result['content_type']
        }
        
    except Exception as e:
        logger.error(f"❌ File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{file_id}")
async def get_file_download_url(
    file_id: str,
    expiration_hours: int = Query(default=1, ge=1, le=24, description="URL expiration in hours"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a signed URL to download a file.
    
    The URL will be valid for the specified number of hours (1-24).
    Access is controlled based on user role and file ownership.
    """
    try:
        user_id = current_user.get('uid')
        
        signed_url = await file_storage_service.get_file_url(
            file_id=file_id,
            user_id=user_id,
            expiration_hours=expiration_hours
        )
        
        return {
            "success": True,
            "download_url": signed_url,
            "expires_in_hours": expiration_hours
        }
        
    except Exception as e:
        logger.error(f"❌ File download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list/{entity_type}/{entity_id}")
async def list_entity_files(
    entity_type: str,
    entity_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    List all files associated with a specific entity.
    
    Returns only files that the current user has permission to access.
    """
    try:
        user_id = current_user.get('uid')
        
        files = await file_storage_service.list_files(
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id
        )
        
        return {
            "success": True,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "files": files,
            "total_files": len(files)
        }
        
    except Exception as e:
        logger.error(f"❌ File listing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a file.
    
    Only admins and file owners can delete files.
    This performs a soft delete - the file is marked as inactive.
    """
    try:
        user_id = current_user.get('uid')
        
        success = await file_storage_service.delete_file(
            file_id=file_id,
            user_id=user_id
        )
        
        return {
            "success": success,
            "message": "File deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ File deletion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage-info")
async def get_storage_info(current_user: dict = Depends(get_current_user)):
    """
    Get information about file storage capabilities and limits.
    """
    return {
        "success": True,
        "storage_info": {
            "max_file_size_mb": 10,
            "max_image_size_mb": 5,
            "allowed_image_types": ["image/jpeg", "image/png", "image/gif", "image/webp"],
            "allowed_document_types": [
                "application/pdf", 
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "text/plain", 
                "text/csv"
            ],
            "organization_structure": {
                "repair_requests": "repair_requests/{request_id}/attachments/",
                "maintenance_tasks": "maintenance_tasks/{task_id}/reports/",
                "announcements": "announcements/{announcement_id}/attachments/",
                "inventory": "inventory/{item_id}/documents/",
                "equipment": "equipment/{equipment_id}/documents/",
                "admin_documents": "admin/documents/"
            }
        }
    }

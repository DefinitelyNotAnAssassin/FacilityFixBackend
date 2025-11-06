from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
from app.services.file_storage_service import file_storage_service
from app.auth.dependencies import get_current_user
from datetime import datetime, timedelta
import urllib.parse

router = APIRouter(prefix="/api/v1/attachments", tags=["attachments"])
logger = logging.getLogger(__name__)

def get_firebase_public_url(bucket_name: str, file_path: str) -> str:
    """
    Generate proper Firebase Storage public URL that works with CORS.
    Format: https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_path}?alt=media
    """
    # URL encode the file path (replace / with %2F)
    encoded_path = urllib.parse.quote(file_path, safe='')
    # Use the firebasestorage.googleapis.com domain which has proper CORS headers
    public_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_path}?alt=media"
    return public_url

@router.post("/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Upload a single file to Firebase Storage.
    Returns the download URL.
    Accessible by: tenant, staff, admin (all authenticated users)
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please login to upload files."
            )
        
        user_id = current_user.get('uid')
        logger.info(f"[Attachment] Uploading file: {file.filename} for user: {user_id}")
        
        # Validate file type
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx']
        file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type .{file_extension} not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 10MB limit"
            )
        
        file_metadata = await file_storage_service.upload_file(
            file=file,
            entity_type="attachments",
            entity_id="temp",
            uploaded_by=user_id,
            file_type="any",
            description=f"Uploaded by {current_user.get('email', 'unknown')}"
        )
        
        download_url = file_metadata.get('download_url')
        
        logger.info(f"[Attachment] ✅ File uploaded with token-based URL: {download_url}")
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "url": download_url,
                "download_url": download_url,
                "filename": file.filename,
                "file_id": file_metadata['id'],
                "file_path": file_metadata['file_path'],
                "message": "File uploaded successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Attachment] ❌ Upload failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}"
        )

@router.post("/upload-multiple")
async def upload_multiple_attachments(
    files: List[UploadFile] = File(...),
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Upload multiple files to Firebase Storage.
    Returns a list of download URLs.
    Accessible by: tenant, staff, admin (all authenticated users)
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please login to upload files."
            )
        
        logger.info(f"[Attachment] Uploading {len(files)} files for user: {current_user.get('uid')}")
        
        uploaded_files = []
        
        for file in files:
            # Validate file type
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx']
            file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
            
            if file_extension not in allowed_extensions:
                logger.warning(f"[Attachment] Skipping file {file.filename}: invalid type")
                continue
            
            file_metadata = await file_storage_service.upload_file(
                file=file,
                entity_type="attachments",
                entity_id="temp",
                uploaded_by=current_user.get('uid'),
                file_type="any",
                description=f"Uploaded by {current_user.get('email', 'unknown')}"
            )
            
            download_url = file_metadata.get('download_url')
            
            uploaded_files.append({
                "filename": file.filename,
                "url": download_url,
                "file_id": file_metadata['id'],
                "file_path": file_metadata['file_path']
            })
        
        logger.info(f"[Attachment] ✅ Uploaded {len(uploaded_files)} files successfully")
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "files": uploaded_files,
                "count": len(uploaded_files),
                "message": f"Successfully uploaded {len(uploaded_files)} file(s)"
            }
        )
        
    except Exception as e:
        logger.error(f"[Attachment] ❌ Multiple upload failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload files: {str(e)}"
        )

@router.delete("/delete/{file_id}")
async def delete_attachment(
    file_id: str,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Delete a file from Firebase Storage.
    Accessible by: tenant, staff, admin (all authenticated users)
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please login to delete files."
            )
        
        logger.info(f"[Attachment] Deleting file: {file_id}")
        
        success = await file_storage_service.delete_file(
            file_id=file_id,
            user_id=current_user.get('uid')
        )
        
        logger.info(f"[Attachment] ✅ File deleted successfully")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "File deleted successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Attachment] ❌ Delete failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class FileAttachment(BaseModel):
    """Model for file attachment metadata"""
    id: Optional[str] = None
    file_path: str
    original_filename: str
    file_size: int
    content_type: str
    entity_type: str  # repair_requests, maintenance_tasks, announcements, etc.
    entity_id: str    # ID of the related entity
    uploaded_by: str  # user_id who uploaded the file
    file_type: str = Field(default="any")  # image, document, any
    description: Optional[str] = None
    storage_url: str  # gs:// URL for Firebase Storage
    public_url: Optional[str] = None  # Signed URL (temporary)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

class FileUploadRequest(BaseModel):
    """Request model for file upload"""
    entity_type: str
    entity_id: str
    file_type: str = Field(default="any")
    description: Optional[str] = None

class FileUploadResponse(BaseModel):
    """Response model for file upload"""
    success: bool
    message: str
    file_id: str
    filename: str
    file_size: int
    content_type: str

class FileListResponse(BaseModel):
    """Response model for file listing"""
    success: bool
    entity_type: str
    entity_id: str
    files: List[dict]
    total_files: int

class FileDownloadResponse(BaseModel):
    """Response model for file download URL"""
    success: bool
    download_url: str
    expires_in_hours: int

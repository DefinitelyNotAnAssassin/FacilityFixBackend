from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.database_models import JobService
from app.services.job_service_service import JobServiceService
from app.services.schedule_formatter import normalize_schedule_availability
from app.auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/job-services", tags=["job-services"])

# Request Models
class CreateJobServiceRequest(BaseModel):
    # Optional notes from the requester; can be omitted
    notes: Optional[str] = None
    location: str
    schedule_availability: Optional[str] = None
    # Structured time fields for better scheduling
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    unit_id: Optional[str] = None
    attachments: Optional[List[str]] = []
    
class CreateJobServiceFromConcernRequest(BaseModel):
    concern_slip_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    schedule_availability: Optional[str] = None
    estimated_hours: Optional[float] = None
    additional_notes: Optional[str] = None

class AssignJobServiceRequest(BaseModel):
    assigned_to: str

class UpdateJobStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class AddNotesRequest(BaseModel):
    notes: str

class SubmitCompletionAssessmentRequest(BaseModel):
    assessment: str
    attachments: Optional[List[str]] = []

async def _create_job_service_logic(
    request: CreateJobServiceRequest,
    current_user: dict
) -> dict:
    """Shared logic for creating job service requests"""
    from app.database.database_service import DatabaseService
    from app.services.job_service_id_service import job_service_id_service
    import uuid
    
    db = DatabaseService()
    job_service_id = f"js_{str(uuid.uuid4())[:8]}"
    
    formatted_id = await job_service_id_service.generate_job_service_id()
    
    job_service_data = {
        "id": job_service_id,
        "formatted_id": formatted_id,
        "reported_by": current_user["uid"],
        "title": "Job Service Request",
        # If notes were not provided, default to empty string
        "description": request.notes or "",
        "location": request.location,
        "category": "",
        "priority": "",
        "status": "pending",
        "request_type": "Job Service",
        "unit_id": request.unit_id,
        "schedule_availability": normalize_schedule_availability(request.schedule_availability),
        "start_time": request.start_time.isoformat() if request.start_time else None,
        "end_time": request.end_time.isoformat() if request.end_time else None,
        "attachments": request.attachments or [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "submitted_at": datetime.utcnow().isoformat()
    }
    
    # Store in dedicated job_service_requests collection
    success, doc_id, error = await db.create_document(
        "job_service_requests",
        job_service_data,
        job_service_id,
        validate=False
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to create job service: {error}")
    
    return {
        "success": True,
        "id": job_service_id,
        "formatted_id": formatted_id,
        "message": "Job service request created successfully"
    }

@router.post("/", response_model=dict)
async def create_job_service_request_post(
    request: CreateJobServiceRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Create a new job service request via POST (stored as concern slip with type 'Job Service')"""
    try:
        return await _create_job_service_logic(request, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job service: {str(e)}")

@router.patch("/", response_model=dict)
async def create_job_service_request_patch(
    request: CreateJobServiceRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Create a new job service request via PATCH (stored as concern slip with type 'Job Service')"""
    try:
        return await _create_job_service_logic(request, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job service: {str(e)}")

@router.post("/from-concern", response_model=JobService)
async def create_job_service_from_concern(
    request: CreateJobServiceFromConcernRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Create a new job service from an approved concern slip (Admin only)"""
    try:
        service = JobServiceService()
        # Prepare job data and ensure we include a formatted job service id and any additional notes
        from app.services.job_service_id_service import job_service_id_service

        job_data = request.dict(exclude_unset=True)
        
        # Normalize schedule_availability if present
        if job_data.get("schedule_availability"):
            job_data["schedule_availability"] = normalize_schedule_availability(job_data["schedule_availability"])
        
        # Generate a formatted job service id (JS-YYYY-NNNNN) and attach it to the payload
        try:
            formatted_id = await job_service_id_service.generate_job_service_id()
            job_data["formatted_id"] = formatted_id
        except Exception:
            # If ID generation fails, continue and let service handle or fail gracefully
            pass

        # Ensure additional_notes is present in the job data (if provided)
        if request.additional_notes:
            job_data["additional_notes"] = request.additional_notes

        job_service = await service.create_job_service(
            concern_slip_id=request.concern_slip_id,
            created_by=current_user["uid"],
            job_data=job_data
        )
        return job_service
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job service: {str(e)}")

@router.patch("/{job_service_id}/assign", response_model=JobService)
async def assign_job_service(
    job_service_id: str,
    request: AssignJobServiceRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Assign job service to internal staff (Admin only)"""
    try:
        service = JobServiceService()
        job_service = await service.assign_job_service(
            job_service_id=job_service_id,
            assigned_to=request.assigned_to,
            assigned_by=current_user["uid"]
        )
        return job_service
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign job service: {str(e)}")

@router.patch("/{job_service_id}/status", response_model=JobService)
async def update_job_status(
    job_service_id: str,
    request: UpdateJobStatusRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Update job service status (Admin and assigned Staff only)"""
    try:
        service = JobServiceService()
        job_service = await service.update_job_status(
            job_service_id=job_service_id,
            status=request.status,
            updated_by=current_user["uid"],
            notes=request.notes
        )
        return job_service
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update job status: {str(e)}")

@router.post("/{job_service_id}/notes", response_model=JobService)
async def add_work_notes(
    job_service_id: str,
    request: AddNotesRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Add work notes to job service (Admin and assigned Staff only)"""
    try:
        service = JobServiceService()
        job_service = await service.add_work_notes(
            job_service_id=job_service_id,
            notes=request.notes,
            added_by=current_user["uid"]
        )
        return job_service
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add notes: {str(e)}")

@router.get("/{job_service_id}", response_model=dict)
async def get_job_service(
    job_service_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff", "tenant"]))
):
    """Get job service by ID with enriched user information"""
    try:
        service = JobServiceService()
        job_service = await service.get_job_service(job_service_id)
        if not job_service:
            raise HTTPException(status_code=404, detail="Job service not found")
        
        # Result is now a dict, return it directly
        print(f"[DEBUG] API Response schedule_availability: {job_service.get('schedule_availability')} (type: {type(job_service.get('schedule_availability'))})")
        return job_service
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job service: {str(e)}")

@router.get("/staff/{staff_id}", response_model=List[JobService])
async def get_job_services_by_staff(
    staff_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Get all job services assigned to a staff member"""
    try:
        # Staff can only view their own assignments, admins can view any
        user_role = current_user.get("role")
        if user_role == "staff" and current_user["uid"] != staff_id:
            raise HTTPException(status_code=403, detail="Staff can only view their own assignments")
        
        service = JobServiceService()
        job_services = await service.get_job_services_by_staff(staff_id)
        return job_services
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job services: {str(e)}")

@router.get("/status/{status}", response_model=List[JobService])
async def get_job_services_by_status(
    status: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all job services with specific status (Admin only)"""
    try:
        service = JobServiceService()
        job_services = await service.get_job_services_by_status(status)
        return job_services
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job services: {str(e)}")

@router.patch("/{job_service_id}/complete", response_model=dict)
async def complete_job_service_request(
    job_service_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Mark a standalone job service request as completed"""
    try:
        from app.database.database_service import DatabaseService
        
        db = DatabaseService()
    
        
     
        if job_service_id:
            await db.update_document("job_services", job_service_id, {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }, validate=False)
            
            return {
                "success": True,
                "message": "Job service request marked as completed"
            }
        else:
            # If no Firebase doc ID, update by creating a new entry (fallback)
            raise HTTPException(status_code=500, detail="Could not find Firebase document ID")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete job service: {str(e)}")

@router.get("/next-id", response_model=dict)
async def get_next_job_service_id(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Get next available job service ID"""
    try:
        from app.services.job_service_id_service import job_service_id_service
        
        formatted_id = await job_service_id_service.generate_job_service_id()
        
        return {
            "next_id": formatted_id,
            "message": "Next job service ID generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate next ID: {str(e)}")

@router.get("/", response_model=List[JobService])
async def get_all_job_services(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all job services (Admin only)"""
    try:
        service = JobServiceService()
        job_services = await service.get_all_job_services()
        return job_services
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job services: {str(e)}")

# File attachment endpoints for job services
@router.post("/{job_service_id}/attachments")
async def upload_job_service_attachment(
    job_service_id: str,
    current_user: dict = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """
    Upload an attachment to a job service.
    - Staff can attach files to their assigned job services
    - Admin can attach files to any job service
    """
    try:
        service = JobServiceService()
        file_metadata = await service.upload_attachment(
            job_service_id=job_service_id,
            file=file,
            uploaded_by=current_user.get("uid")
        )
        
        return {
            "message": "File uploaded successfully",
            "attachment_id": file_metadata.get('id'),
            "file_url": file_metadata.get('public_url')
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload attachment: {str(e)}")

@router.get("/{job_service_id}/attachments")
async def list_job_service_attachments(
    job_service_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List all attachments for a job service"""
    try:
        service = JobServiceService()
        attachments = await service.list_attachments(
            job_service_id=job_service_id,
            user_id=current_user.get("uid")
        )
        
        return {
            "job_service_id": job_service_id,
            "attachments": attachments
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list attachments: {str(e)}")

@router.get("/{job_service_id}/attachments/{file_id}")
async def get_job_service_attachment_url(
    job_service_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a signed URL for accessing a specific attachment"""
    try:
        service = JobServiceService()
        signed_url = await service.get_attachment_url(
            job_service_id=job_service_id,
            file_id=file_id,
            user_id=current_user.get("uid")
        )
        
        return {"url": signed_url}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attachment URL: {str(e)}")

@router.delete("/{job_service_id}/attachments/{file_id}")
async def delete_job_service_attachment(
    job_service_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific attachment from a job service"""
    try:
        service = JobServiceService()
        success = await service.delete_attachment(
            job_service_id=job_service_id,
            file_id=file_id,
            user_id=current_user.get("uid")
        )
        
        return {"message": "Attachment deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete attachment: {str(e)}")

@router.delete("/{job_service_id}")
async def delete_job_service(
    job_service_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant", "admin"]))
):
    """Delete a job service.
    - Tenants can delete their own job services only when status is 'pending' or 'completed'.
    - Admins can delete any job service.
    """
    try:
        from app.database.database_service import DatabaseService

        db = DatabaseService()

        # Query by business id field
        success, results, error = await db.query_documents("job_services", [("id", "==", job_service_id)])
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to query job services: {error}")

        if not results or len(results) == 0:
            # Fallback: maybe the job service exists in job_service_requests collection
            success, results, error = await db.query_documents("job_service_requests", [("id", "==", job_service_id)])
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to query job service requests: {error}")
            if not results or len(results) == 0:
                raise HTTPException(status_code=404, detail="Job service not found")

        job = results[0]

        # Firestore document id (internal) may be provided as _doc_id
        doc_id = job.get("_doc_id") or job.get("id") or job_service_id

        # Determine owner field (some flows use created_by, reported_by or requested_by)
        owner_uid = job.get("created_by") or job.get("reported_by") or job.get("requested_by")
        # Determine if current user is admin
        is_admin = current_user.get("role") == "admin" or current_user.get("is_admin") is True

        # If tenant, enforce ownership and status == pending (concern-slip behavior)
        if not is_admin:
            if not owner_uid or owner_uid != current_user.get("uid"):
                raise HTTPException(status_code=403, detail="Tenants can only delete their own job services")
            if job.get("status") not in ["pending", "completed"]:
                raise HTTPException(status_code=403, detail="Tenants may only delete job services while status is 'pending' or 'completed'")

        # Perform delete
        delete_success, delete_error = await db.delete_document("job_services", doc_id)
        if not delete_success:
            # Try deleting from job_service_requests if it exists there
            delete_success, delete_error = await db.delete_document("job_service_requests", doc_id)
            if not delete_success:
                raise HTTPException(status_code=500, detail=f"Failed to delete job service: {delete_error}")

        return {"success": True, "message": "Job service deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete job service: {str(e)}")

@router.patch("/{job_service_id}/submit-completion-assessment", response_model=dict)
async def submit_completion_assessment(
    job_service_id: str,
    request: SubmitCompletionAssessmentRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Submit completion assessment for job service and mark as completed (Staff only)"""
    try:
        from app.database.database_service import DatabaseService
        
        db = DatabaseService()
        
        # Get the job service to verify it exists and get concern slip ID
        success, jobs_data, error = await db.query_documents("job_services", [("id", "==", job_service_id)])
        
        if not success or not jobs_data or len(jobs_data) == 0:
            # Try job_service_requests collection
            success, jobs_data, error = await db.query_documents("job_service_requests", [("id", "==", job_service_id)])
            collection_name = "job_service_requests"
        else:
            collection_name = "job_services"
        
        if not success or not jobs_data or len(jobs_data) == 0:
            raise HTTPException(status_code=404, detail="Job service not found")
        
        job_data = jobs_data[0]
        
        # Update job service with completion assessment and set status to completed
        update_data = {
            "completion_notes": request.assessment,
            "assessment_attachments": request.attachments,
            "assessed_by": current_user["uid"],
            "assessed_at": datetime.utcnow(),
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Update job service
        firestore_doc_id = job_data.get("_doc_id")
        if not firestore_doc_id:
            raise HTTPException(status_code=500, detail="Could not find Firestore document ID")
        
        success, error = await db.update_document(collection_name, firestore_doc_id, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to update job service: {error}")
        
        # Update related concern slip status to completed if it exists
        concern_slip_id = job_data.get("concern_slip_id")
        if concern_slip_id:
            try:
                await db.update_document("concern_slips", concern_slip_id, {
                    "status": "completed",
                    "updated_at": datetime.utcnow()
                }, validate=False)
            except Exception as e:
                print(f"Failed to update concern slip status: {e}")
        
        # Send completion notification to admin and tenant
        try:
            from app.services.notification_manager import notification_manager
            
            job_title = job_data.get("title", "Job Service")
            created_by = job_data.get("created_by") or job_data.get("requested_by")
            
            print(f"[Job Service Completion] job_title: {job_title}, created_by: {created_by}")
            
            if not created_by:
                print(f"[Job Service Completion] No tenant ID found in job data. Available keys: {list(job_data.keys())}")
            
            # Get admin users using notification_manager's method
            try:
                admin_users = await notification_manager._get_users_by_role("admin")
                print(f"[Job Service Completion] Found {len(admin_users) if admin_users else 0} admin users")
                admin_id = admin_users[0]["_doc_id"] if admin_users else None
            except Exception as e:
                print(f"[Job Service Completion] Error getting admin users: {str(e)}")
                import traceback
                traceback.print_exc()
                admin_id = None
            
            if admin_id and created_by:
                print(f"[Job Service Completion] Calling notify_job_service_completed with staff_id={current_user['uid']}, tenant_id={created_by}, admin_id={admin_id}")
                result = await notification_manager.notify_job_service_completed(
                    job_service_id=job_service_id,
                    staff_id=current_user["uid"],
                    tenant_id=created_by,
                    admin_id=admin_id,
                    title=job_title,
                    completion_notes=request.assessment
                )
                print(f"[Job Service Completion] Notification result: {result}")
                print(f"[Job Service Completion] Sent notifications for job service {job_service_id}")
            else:
                print(f"[Job Service Completion] Missing admin_id={admin_id} or created_by={created_by}")
        except Exception as e:
            print(f"[Job Service Completion] Error sending notifications: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return {
            "success": True,
            "message": "Job service marked as completed with assessment",
            "job_service_id": job_service_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit completion assessment: {str(e)}")

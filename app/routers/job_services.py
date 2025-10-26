from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.database_models import JobService
from app.services.job_service_service import JobServiceService
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
    estimated_hours: Optional[float] = None

class AssignJobServiceRequest(BaseModel):
    assigned_to: str

class UpdateJobStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class AddNotesRequest(BaseModel):
    notes: str

async def _create_job_service_logic(
    request: CreateJobServiceRequest,
    current_user: dict
) -> dict:
    """Shared logic for creating job service requests"""
    from app.database.database_service import DatabaseService
    import uuid
    
    db = DatabaseService()
    job_service_id = f"js_{str(uuid.uuid4())[:8]}"
    
    # Generate formatted ID
    now = datetime.utcnow()
    year = now.year
    day_of_year = now.timetuple().tm_yday
    formatted_id = f"JS-{year}-{str(day_of_year).zfill(5)}"
    
    job_service_data = {
        "id": job_service_id,
        "formatted_id": formatted_id,
        "reported_by": current_user["uid"],
        "title": "Job Service Request",
        # If notes were not provided, default to empty string
        "description": request.notes or "",
        "location": request.location,
        "category": "general",
        "priority": "medium",
        "status": "pending",
        "request_type": "Job Service",
        "unit_id": request.unit_id,
        "schedule_availability": request.schedule_availability,
        "start_time": request.start_time.isoformat() if request.start_time else None,
        "end_time": request.end_time.isoformat() if request.end_time else None,
        "attachments": request.attachments or [],
        "created_at": now,
        "updated_at": now,
        "submitted_at": now.isoformat()
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
        job_service = await service.create_job_service(
            concern_slip_id=request.concern_slip_id,
            created_by=current_user["uid"],
            job_data=request.dict(exclude_unset=True)
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
        # Return as dict to include enriched fields
        return job_service.model_dump() if hasattr(job_service, 'model_dump') else job_service
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
        now = datetime.utcnow()
        year = now.year
        day_of_year = now.timetuple().tm_yday
        next_id = f"JS-{year}-{str(day_of_year).zfill(5)}"
        
        return {
            "next_id": next_id,
            "year": year,
            "sequence": day_of_year
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

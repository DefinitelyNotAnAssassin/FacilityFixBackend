from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.database_models import JobService
from app.services.job_service_service import JobServiceService
from app.services.concern_slip_service import ConcernSlipService
from app.auth.dependencies import get_current_user, require_role
import logging

router = APIRouter(prefix="/tenant-job-services", tags=["tenant-job-services"])
logger = logging.getLogger(__name__)

# Request Models
class CreateTenantJobServiceRequest(BaseModel):
    concern_slip_id: str
    notes: str
    location: str
    unit_id: Optional[str] = None
    schedule_availability: Optional[str] = None
    attachments: Optional[list] = []

@router.post("/", response_model=dict)
async def create_tenant_job_service(
    request: CreateTenantJobServiceRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant"]))
):
    """
    Create a new job service request from a concern slip with 'sent' status (Tenant only).
    This allows tenants to follow up on their concern slips that have been marked as 'sent'
    with a job service request containing additional details.
    """
    try:
        # Verify the concern slip exists and belongs to the current user
        concern_slip_service = ConcernSlipService()
        concern_slip = await concern_slip_service.get_concern_slip(request.concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Verify the concern slip belongs to the current user
        if concern_slip.reported_by != current_user["uid"]:
            raise HTTPException(status_code=403, detail="You can only create job services for your own concern slips")
        
        # Check if concern slip has the right resolution type (should be 'job_service')
        if concern_slip.resolution_type != 'job_service':
            raise HTTPException(
                status_code=400, 
                detail="This concern slip has not been designated for job service resolution"
            )
        
        # Check if concern slip status allows job service creation
        if concern_slip.status not in ['evaluated', 'approved', 'sent']:
            raise HTTPException(
                status_code=400, 
                detail=f"Concern slip status '{concern_slip.status}' does not allow job service creation. Status must be 'evaluated', 'approved', or 'sent'."
            )
        
        # Prepare job service data
        job_data = {
            "title": f"Job Service for: {concern_slip.title}",
            "description": request.notes,
            "location": request.location,
            "category": concern_slip.category,
            "priority": concern_slip.priority,
            "scheduled_date": None,
            "estimated_hours": None,
        }
        
        # Create the job service using the tenant as the creator
        # Note: This is different from admin-created job services
        job_service_service = JobServiceService()
        job_service = await job_service_service.create_tenant_job_service(
            concern_slip_id=request.concern_slip_id,
            created_by=current_user["uid"],
            job_data=job_data
        )
        
        # Update concern slip status to 'complete' since tenant has submitted the job service
        await concern_slip_service.update_concern_slip_status(
            concern_slip_id=request.concern_slip_id,
            status='completed',
            updated_by=current_user["uid"]
        )
        
        logger.info(f"[TENANT_JOB_SERVICE] Created job service {job_service.id} for concern slip {request.concern_slip_id}")
        
        return {
            'success': True,
            'message': 'Job service request submitted successfully',
            'id': job_service.id,
            'formatted_id': f"JS-{datetime.now().year}-{job_service.id[:5]}",
            'data': job_service.dict(),
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"[TENANT_JOB_SERVICE] Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[TENANT_JOB_SERVICE] Error creating tenant job service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create job service: {str(e)}")
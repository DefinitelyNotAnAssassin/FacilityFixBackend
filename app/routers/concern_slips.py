from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from fastapi import File, UploadFile
from pydantic import BaseModel
from datetime import datetime
from app.models.database_models import ConcernSlip
from app.services.concern_slip_service import ConcernSlipService
from app.auth.dependencies import get_current_user, require_role
from app.services.user_id_service import UserIdService
import logging 

router = APIRouter(prefix="/concern-slips", tags=["concern-slips"])

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

UserService = UserIdService()

# Request Models
class CreateConcernSlipRequest(BaseModel):
    title: str
    description: str
    location: str
    category: str  # electrical, plumbing, hvac, carpentry, maintenance, security, fire_safety, general
    priority: str = "medium"  # low, medium, high, critical
    unit_id: Optional[str] = None
    attachments: Optional[List[str]] = []

class EvaluateConcernSlipRequest(BaseModel):
    status: str  # approved, rejected
    urgency_assessment: Optional[str] = None
    resolution_type: Optional[str] = None  # job_service, work_permit
    admin_notes: Optional[str] = None

class AssignStaffRequest(BaseModel):
    assigned_to: str  # staff user_id

class SubmitAssessmentRequest(BaseModel):
    assessment: str
    resolution_type: str  # job_service, work_order - Required
    attachments: Optional[List[str]] = []

class SetResolutionTypeRequest(BaseModel):
    resolution_type: str  # job_service, work_order
    admin_notes: Optional[str] = None

class AIReprocessRequest(BaseModel):
    force_translate: bool = False

@router.post("/{concern_slip_id}/attachments")
async def upload_concern_slip_attachment(
    concern_slip_id: str,
    current_user: dict = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """
    Upload an attachment to a concern slip.
    - Tenants can only attach files to their own pending concern slips
    - Staff can attach assessment files to their assigned concern slips
    - Admin can attach files to any concern slip
    """
    try:
        concern_service = ConcernSlipService()
        concern_slip = await concern_service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Check permissions
        user_role = current_user.get("role", "").lower()
        user_id = current_user.get("uid")
        
        # Tenant can only upload to their own pending slips
        if user_role == "tenant":
            if concern_slip.reported_by != user_id:
                raise HTTPException(status_code=403, detail="You can only upload attachments to your own concern slips")
            if concern_slip.status != "pending":
                raise HTTPException(status_code=400, detail="Attachments can only be added to pending concern slips")
                
        # Staff can only upload to their assigned slips during assessment
        elif user_role == "staff":
            if concern_slip.assigned_to != user_id:
                raise HTTPException(status_code=403, detail="You can only upload attachments to concern slips assigned to you")
            if concern_slip.status != "assigned":
                raise HTTPException(status_code=400, detail="Staff can only add attachments during assessment phase")
                
        # Admin can upload to any slip
        elif user_role != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

        file_metadata = await concern_service.upload_attachment(
            concern_slip_id=concern_slip_id,
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

@router.get("/{concern_slip_id}/attachments")
async def list_concern_slip_attachments(
    concern_slip_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    List all attachments for a concern slip.
    - Tenants can only view their own concern slip attachments
    - Staff can view attachments for assigned concern slips
    - Admin can view all attachments
    """
    try:
        concern_service = ConcernSlipService()
        concern_slip = await concern_service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Check permissions
        user_role = current_user.get("role", "").lower()
        user_id = current_user.get("uid")
        
        if user_role == "tenant" and concern_slip.reported_by != user_id:
            raise HTTPException(status_code=403, detail="You can only view attachments for your own concern slips")
            
        if user_role == "staff" and concern_slip.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="You can only view attachments for concern slips assigned to you")
            
        attachments = await concern_service.list_attachments(
            concern_slip_id=concern_slip_id,
            user_id=current_user.get("uid")
        )
        
        return {
            "concern_slip_id": concern_slip_id,
            "attachments": attachments
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list attachments: {str(e)}")

@router.get("/{concern_slip_id}/attachments/{file_id}")
async def get_attachment_url(
    concern_slip_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a signed URL for accessing a specific attachment.
    Access rules:
    - Tenants can access their own concern slip attachments
    - Staff can access attachments for assigned concern slips
    - Admin can access all attachments
    """
    try:
        concern_service = ConcernSlipService()
        concern_slip = await concern_service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Check permissions
        user_role = current_user.get("role", "").lower()
        user_id = current_user.get("uid")
        
        if user_role == "tenant" and concern_slip.reported_by != user_id:
            raise HTTPException(status_code=403, detail="You can only access attachments for your own concern slips")
            
        if user_role == "staff" and concern_slip.assigned_to != user_id:
            raise HTTPException(status_code=403, detail="You can only access attachments for concern slips assigned to you")
        
        signed_url = await concern_service.get_attachment_url(
            concern_slip_id=concern_slip_id,
            file_id=file_id,
            user_id=current_user.get("uid")
        )
        
        return {"url": signed_url}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attachment URL: {str(e)}")

@router.delete("/{concern_slip_id}/attachments/{file_id}")
async def delete_attachment(
    concern_slip_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific attachment from a concern slip.
    Delete rules:
    - Tenants can only delete their own pending concern slip attachments
    - Staff cannot delete attachments
    - Admin can delete any attachment
    """
    try:
        concern_service = ConcernSlipService()
        concern_slip = await concern_service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Check permissions
        user_role = current_user.get("role", "").lower()
        user_id = current_user.get("uid")
        
        # Only tenants and admins can delete attachments
        if user_role == "staff":
            raise HTTPException(status_code=403, detail="Staff members cannot delete attachments")
            
        # Tenants can only delete their own pending concern slip attachments
        if user_role == "tenant":
            if concern_slip.reported_by != user_id:
                raise HTTPException(status_code=403, detail="You can only delete attachments from your own concern slips")
            if concern_slip.status != "pending":
                raise HTTPException(status_code=400, detail="Attachments can only be deleted from pending concern slips")
        
        success = await concern_service.delete_attachment(
            concern_slip_id=concern_slip_id,
            file_id=file_id,
            user_id=current_user.get("uid")
        )
        
        return {"message": "Attachment deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete attachment: {str(e)}")

@router.get("/")
async def fetch_concern_slips(
    current_user: dict = Depends(get_current_user),
): 
    service = ConcernSlipService()
    print(current_user)

    if current_user and current_user.get('role') == 'staff': 
        concern_slips = await service.get_concern_slips_by_staff(user_id=current_user.get('user_id'))

    else: 
        concern_slips = await service.get_all_concern_slips() 
        
    
    logger.info(f"[DEBUG] Found {len(concern_slips)} concern slips in database")
    return concern_slips
    
    


@router.post("/", response_model=ConcernSlip)
async def submit_concern_slip(
    request: CreateConcernSlipRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant"]))
):
    """
    Submit a new concern slip (Tenant only).
    Tenants report repair/maintenance issues here.
    The system automatically processes the description with AI for translation and categorization.
    """
    try:
        
        
        service = ConcernSlipService()
        concern_slip = await service.create_concern_slip(
            reported_by=current_user["uid"],
            concern_data=request.dict(),
            
        )
        return concern_slip

    except ValueError as e:
        # Raised if a non-tenant tries to access this
        raise HTTPException(status_code=403, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error while submitting concern slip: {str(e)}"
        )

@router.patch("/{concern_slip_id}/evaluate", response_model=ConcernSlip)
async def evaluate_concern_slip(
    concern_slip_id: str,
    request: EvaluateConcernSlipRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """
    Evaluate concern slip (Admin only):
    - Approve or reject
    - Set resolution type (job_service, work_permit, etc.)
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.evaluate_concern_slip(
            concern_slip_id=concern_slip_id,
            evaluated_by=current_user["uid"],
            evaluation_data=request.dict()
        )
        return concern_slip
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to evaluate concern slip: {str(e)}"
        )

@router.patch("/{concern_slip_id}/assign-staff", response_model=ConcernSlip)
async def assign_staff_to_concern_slip(
    concern_slip_id: str,
    request: AssignStaffRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """
    Assign a staff member to assess a concern slip (Admin only).
    This is step 2 of the workflow after tenant submits.
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.assign_staff_for_assessment(
            concern_slip_id=concern_slip_id,
            assigned_to=request.assigned_to,
            assigned_by=current_user["uid"]
        )
        return concern_slip
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to assign staff: {str(e)}"
        )

@router.get("/{concern_slip_id}")
async def get_concern_slip_by_id(
    concern_slip_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific concern slip by ID"""
    try:
        concern_service = ConcernSlipService()
        concern_slip = await concern_service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        return {
            "id": concern_slip.id,
            "formatted_id": concern_slip.formatted_id,
            "title": concern_slip.title,
            "description": concern_slip.description,
            "location": concern_slip.location,
            "category": concern_slip.category,
            "priority": concern_slip.priority,
            "status": concern_slip.status,
            "unit_id": concern_slip.unit_id,
            "reported_by": concern_slip.reported_by,
            "assigned_to": concern_slip.assigned_to,
            "resolution_type": concern_slip.resolution_type,
            "resolution_set_by": concern_slip.resolution_set_by,
            "resolution_set_at": concern_slip.resolution_set_at.isoformat() if concern_slip.resolution_set_at else None,
            "urgency_assessment": concern_slip.urgency_assessment,
            "evaluated_by": concern_slip.evaluated_by,
            "evaluated_at": concern_slip.evaluated_at.isoformat() if concern_slip.evaluated_at else None,
            "assessed_by": concern_slip.assessed_by,
            "assessed_at": concern_slip.assessed_at.isoformat() if concern_slip.assessed_at else None,
            "assigned_at": concern_slip.assigned_at.isoformat() if concern_slip.assigned_at else None,
            "returned_to_tenant_at": concern_slip.returned_to_tenant_at.isoformat() if concern_slip.returned_to_tenant_at else None,
            "created_at": concern_slip.created_at.isoformat() if concern_slip.created_at else None,
            "updated_at": concern_slip.updated_at.isoformat() if concern_slip.updated_at else None,
            "request_type": getattr(concern_slip, 'request_type', 'Concern Slip'),
            "attachments": getattr(concern_slip, 'attachments', []),
            "assessment_attachments": getattr(concern_slip, 'assessment_attachments', []),
            "staff_assessment": getattr(concern_slip, 'staff_assessment', None),
            "staff_recommendation": getattr(concern_slip, 'staff_recommendation', None),
            "admin_notes": getattr(concern_slip, 'admin_notes', None),
            "ai_processed": getattr(concern_slip, 'ai_processed', False),
            "detected_language": getattr(concern_slip, 'detected_language', 'en'),
            "translation_applied": getattr(concern_slip, 'translation_applied', False),
            "ai_confidence_scores": getattr(concern_slip, 'ai_confidence_scores', {}),
            "schedule_availability": getattr(concern_slip, 'schedule_availability', None),
            "submitted_at": getattr(concern_slip, 'submitted_at', None),
        }
        
    except Exception as e:
        logger.error(f"Error getting concern slip {concern_slip_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get concern slip: {str(e)}")

@router.get("/{concern_slip_id}/ai-history")
async def get_ai_processing_history(
    concern_slip_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """
    Get AI processing history for a concern slip (Admin only).
    Shows translation attempts, categorization results, and confidence scores.
    """
    try:
        service = ConcernSlipService()
        
        # Verify concern slip exists
        concern_slip = await service.get_concern_slip(concern_slip_id)
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Get AI processing history
        ai_history = await service.get_ai_processing_history(concern_slip_id)
        if not ai_history:
            raise HTTPException(status_code=404, detail="No AI processing history found")
        
        return ai_history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get AI processing history: {str(e)}")

@router.post("/{concern_slip_id}/reprocess-ai")
async def reprocess_concern_with_ai(
    concern_slip_id: str,
    request: AIReprocessRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """
    Reprocess a concern slip with AI (Admin only).
    Useful for re-analyzing descriptions with updated models or forcing translation.
    """
    try:
        service = ConcernSlipService()
        
        # Verify concern slip exists
        concern_slip = await service.get_concern_slip(concern_slip_id)
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Reprocess with AI
        success = await service.reprocess_with_ai(concern_slip_id, request.force_translate)
        
        if success:
            # Return updated concern slip
            updated_concern = await service.get_concern_slip(concern_slip_id)
            return {
                "message": "AI reprocessing completed successfully",
                "concern_slip": updated_concern,
                "reprocessed_at": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="AI reprocessing failed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reprocess with AI: {str(e)}")

@router.patch("/{concern_slip_id}/submit-assessment", response_model=ConcernSlip)
async def submit_staff_assessment(
    concern_slip_id: str,
    request: SubmitAssessmentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit assessment with resolution type for a concern slip (Staff only).
    Required fields: assessment, resolution_type, attachments (optional)
    Status will be set to 'sent' and resolution type will be recorded.
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.submit_staff_assessment(
            concern_slip_id=concern_slip_id,
            assessed_by=current_user["uid"],
            assessment=request.assessment,
            resolution_type=request.resolution_type,
            attachments=request.attachments
        )
        return concern_slip
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit assessment: {str(e)}"
        )

@router.patch("/{concern_slip_id}/set-resolution-type", response_model=ConcernSlip)
async def set_resolution_type(
    concern_slip_id: str,
    request: SetResolutionTypeRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """
    Set resolution type for an assessed concern slip (Admin only).
    This determines if it becomes a Job Service or Work Order.
    Status will be changed to 'sent' after setting resolution type.
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.set_resolution_type(
            concern_slip_id=concern_slip_id,
            resolution_type=request.resolution_type,
            admin_user_id=current_user["uid"],
            admin_notes=request.admin_notes
        )
        return concern_slip
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set resolution type: {str(e)}"
        )

@router.patch("/{concern_slip_id}/return-to-tenant", response_model=ConcernSlip)
async def return_concern_slip_to_tenant(
    concern_slip_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """
    Return assessed concern slip to tenant (Admin only).
    This is step 4 of the workflow after admin reviews staff assessment.
    Tenant can then proceed with Job Service or Work Order Permit.
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.return_to_tenant(
            concern_slip_id=concern_slip_id,
            returned_by=current_user["uid"]
        )
        return concern_slip
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to return concern slip to tenant: {str(e)}"
        )

@router.get("/tenant/{tenant_id}", response_model=List[ConcernSlip])
async def get_concern_slips_by_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Get all concern slips for a tenant"""
    try:
        # Tenants can only view their own concern slips
        if current_user.get("role") == "tenant" and current_user["uid"] != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = ConcernSlipService()
        concern_slips = await service.get_concern_slips_by_tenant(tenant_id)
        return concern_slips
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get concern slips: {str(e)}")

@router.get("/status/{status}", response_model=List[ConcernSlip])
async def get_concern_slips_by_status(
    status: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all concern slips with specific status (Admin only)"""
    try:
        service = ConcernSlipService()
        concern_slips = await service.get_concern_slips_by_status(status)
        return concern_slips
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get concern slips: {str(e)}")

@router.get("/pending/all", response_model=List[ConcernSlip])
async def get_pending_concern_slips(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all pending concern slips awaiting evaluation (Admin only)"""
    try:
        service = ConcernSlipService()
        concern_slips = await service.get_pending_concern_slips()
        return concern_slips
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pending concern slips: {str(e)}")

@router.get("/staff/{staff_id}", response_model=List[ConcernSlip])
async def get_concern_slips_by_staff(
    staff_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Get all concern slips assigned to a staff member"""
    try:
        # Staff can only view their own assignments
        if current_user.get("role") == "staff" and current_user["uid"] != staff_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = ConcernSlipService()
        concern_slips = await service.get_concern_slips_by_staff(staff_id)
        return concern_slips
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get concern slips: {str(e)}")

@router.get("/")
async def get_all_concern_slips(current_user: dict = Depends(get_current_user)):
    """Get all concern slips - works for both admin and tenant views"""
    try:
        logger.info(f"[DEBUG] Fetching concern slips for user: {current_user.get('email')} with role: {current_user.get('role')}")
        
        concern_service = ConcernSlipService()
        
        # Get all concern slips from Firebase
        concern_slips = await concern_service.get_all_concern_slips()
        
        logger.info(f"[DEBUG] Found {len(concern_slips)} concern slips in database")
        
        # Convert to dict format for API response
        result = []
        for slip in concern_slips:
            reported_by = slip.reported_by 
            reported_by = await UserService.get_user_profile(reported_by)
            print("Reported By:", reported_by)
            slip_dict = {
                "id": slip.id,
                "formatted_id": slip.formatted_id,
                "title": slip.title,
                "description": slip.description,
                "location": slip.location,
                "category": slip.category,
                "priority": slip.priority,
                "status": slip.status,
                "unit_id": slip.unit_id,
                "reported_by": f"{reported_by.full_name if reported_by else 'Unknown'}",
                "assigned_to": slip.assigned_to,
                "created_at": slip.created_at.isoformat() if slip.created_at else None,
                "updated_at": slip.updated_at.isoformat() if slip.updated_at else None,
                "request_type": getattr(slip, 'request_type', 'Concern Slip'),
                "attachments": getattr(slip, 'attachments', []),
                "staff_assessment": getattr(slip, 'staff_assessment', None),
                "staff_recommendation": getattr(slip, 'staff_recommendation', None),
                "admin_notes": getattr(slip, 'admin_notes', None),
                "ai_processed": getattr(slip, 'ai_processed', False),
                "detected_language": getattr(slip, 'detected_language', 'en'),
                "translation_applied": getattr(slip, 'translation_applied', False),
                "ai_confidence_scores": getattr(slip, 'ai_confidence_scores', {}),
                "schedule_availability": getattr(slip, 'schedule_availability', None),
                "submitted_at": getattr(slip, 'submitted_at', None),
            }
            result.append(slip_dict)
        
        logger.info(f"[DEBUG] Returning {len(result)} concern slips")
        return result
        
    except Exception as e:
        logger.error(f"Error getting concern slips: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get concern slips: {str(e)}")
    
@router.patch("/{concern_slip_id}", response_model=ConcernSlip)
async def update_concern_slip(
    concern_slip_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    unit_id: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant", "admin"]))
):
    """
    Update a concern slip (Tenant can update their own, Admin can update any).
    Only pending concern slips can be updated by tenants.
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Tenants can only update their own concern slips
        if current_user.get("role") == "tenant":
            if concern_slip.reported_by != current_user["uid"]:
                raise HTTPException(status_code=403, detail="You can only update your own concern slips")
            
            # Tenants can only update pending concern slips
            if concern_slip.status != "pending":
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot update concern slip with status: {concern_slip.status}. Only pending concern slips can be updated."
                )
        
        # Build update data
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
            update_data["original_description"] = description
        if location is not None:
            update_data["location"] = location
        if category is not None:
            update_data["category"] = category
        if priority is not None:
            update_data["priority"] = priority
        if unit_id is not None:
            update_data["unit_id"] = unit_id
        if attachments is not None:
            update_data["attachments"] = attachments
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Update the concern slip
        from app.database.database_service import database_service
        success, error = await database_service.update_document(
            "concern_slips", 
            concern_slip_id, 
            update_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to update concern slip: {error}")
        
        # Return updated concern slip
        updated_concern = await service.get_concern_slip(concern_slip_id)
        return updated_concern
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update concern slip: {str(e)}"
        )

@router.delete("/{concern_slip_id}")
async def delete_concern_slip(
    concern_slip_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant", "admin"]))
):
    """
    Delete a concern slip (Tenant can delete their own, Admin can delete any).
    Only pending concern slips can be deleted by tenants.
    """
    try:
        service = ConcernSlipService()
        concern_slip = await service.get_concern_slip(concern_slip_id)
        
        if not concern_slip:
            raise HTTPException(status_code=404, detail="Concern slip not found")
        
        # Tenants can only delete their own concern slips
        if current_user.get("role") == "tenant":
            if concern_slip.reported_by != current_user["uid"]:
                raise HTTPException(status_code=403, detail="You can only delete your own concern slips")
            
            # Tenants can only delete pending concern slips
            if concern_slip.status != "pending":
                raise HTTPException(
                    status_code=400, 
                    detail=f"Cannot delete concern slip with status: {concern_slip.status}. Only pending concern slips can be deleted."
                )
        
        # Delete the concern slip
        from app.database.database_service import database_service
        success, error = await database_service.delete_document("concern_slips", concern_slip_id)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to delete concern slip: {error}")
        
        return {
            "success": True,
            "message": "Concern slip deleted successfully",
            "id": concern_slip_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete concern slip: {str(e)}"
        )
    
@router.post("/")
async def create_concern_slip(
    concern_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Create a new concern slip"""
    try:
        concern_service = ConcernSlipService()
        
        # Create concern slip
        concern_slip = await concern_service.create_concern_slip(
            reported_by=current_user.get('uid'),
            concern_data=concern_data
        )
        
        return {
            "success": True,
            "message": "Concern slip created successfully",
            "id": concern_slip.id,
            "formatted_id": concern_slip.formatted_id
        }
        
    except Exception as e:
        logger.error(f"Error creating concern slip: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create concern slip: {str(e)}")

@router.get("/next-id")
async def get_next_concern_slip_id(current_user: dict = Depends(get_current_user)):
    """Get the next available concern slip ID"""
    try:
        logger.info(f"[ConcernSlip] Generating next ID for user: {current_user.get('uid')}")
        
        from app.services.concern_slip_id_service import concern_slip_id_service
        next_id = await concern_slip_id_service.generate_concern_slip_id()
        
        logger.info(f"[ConcernSlip] Generated ID: {next_id}")
        
        return {"next_id": next_id, "success": True}
    except Exception as e:
        logger.error(f"Error generating next concern slip ID: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate ID: {str(e)}")

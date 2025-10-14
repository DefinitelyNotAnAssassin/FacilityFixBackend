from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.models.database_models import WorkOrderPermit
from app.services.work_order_permit_service import WorkOrderPermitService
from app.auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/work-order-permits", tags=["work-order-permits"])

# Request Models
class CreateWorkOrderPermitRequest(BaseModel):
    request_type_detail: str
    location: str
    valid_from: str
    valid_to: str
    contractors: List[dict]
    unit_id: Optional[str] = None
    concern_slip_id: Optional[str] = None  # Optional link to concern slip
    attachments: Optional[List[str]] = []

class CreateWorkOrderPermitFromConcernRequest(BaseModel):
    concern_slip_id: str
    unit_id: str
    contractor_name: str
    contractor_contact: str
    contractor_company: Optional[str] = None
    work_description: str
    proposed_start_date: datetime
    estimated_duration: str
    specific_instructions: str
    entry_requirements: Optional[str] = None

class ApprovePermitRequest(BaseModel):
    conditions: Optional[str] = None

class DenyPermitRequest(BaseModel):
    reason: str

class UpdatePermitStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None

async def _create_work_order_permit_logic(
    request: CreateWorkOrderPermitRequest,
    current_user: dict
) -> dict:
    """Shared logic for creating work order permit requests"""
    from app.database.database_service import DatabaseService
    import uuid
    
    db = DatabaseService()
    work_order_id = f"wp_{str(uuid.uuid4())[:8]}"
    
    # Generate formatted ID
    now = datetime.utcnow()
    year = now.year
    day_of_year = now.timetuple().tm_yday
    formatted_id = f"WP-{year}-{str(day_of_year).zfill(5)}"
    
    # If concern_slip_id is provided, get the concern slip and format title
    title = "Work Order Permit"
    concern_slip_id = request.concern_slip_id
    
    if concern_slip_id:
        success, concern_slip, error = await db.get_document("concern_slips", concern_slip_id)
        if success and concern_slip:
            concern_slip_title = concern_slip.get("title", "Untitled Concern")
            title = f"Work Order for: {concern_slip_title}"
    
    work_order_data = {
        "id": work_order_id,
        "formatted_id": formatted_id,
        "concern_slip_id": concern_slip_id,  # Include concern_slip_id if provided
        "requested_by": current_user["uid"],
        "title": title,
        "description": request.request_type_detail,
        "location": request.location,
        "category": "general",
        "priority": "medium",
        "status": "pending",
        "request_type": "Work Order Permit",
        "unit_id": request.unit_id,
        "valid_from": request.valid_from,
        "valid_to": request.valid_to,
        "contractors": request.contractors,
        "attachments": request.attachments or [],
        "created_at": now,
        "updated_at": now,
        "submitted_at": now.isoformat()
    }
    
    # Store in dedicated work_order_permits collection
    success, doc_id, error = await db.create_document(
        "work_order_permits",
        work_order_data,
        work_order_id
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to create work order permit: {error}")
    
    # If created from concern slip, update concern slip status to completed
    if concern_slip_id:
        update_success, update_error = await db.update_document("concern_slips", concern_slip_id, {
            "status": "completed",
            "resolution_type": "work_permit",
            "updated_at": datetime.utcnow()
        })
        if update_success:
            print(f"[Work Order Permit] Updated concern slip {concern_slip_id} status to completed")
        else:
            print(f"[Work Order Permit] Warning: Failed to update concern slip status: {update_error}")
    
    return {
        "success": True,
        "id": work_order_id,
        "formatted_id": formatted_id,
        "message": "Work order permit created successfully"
    }

@router.post("/", response_model=dict)
async def create_work_order_permit_post(
    request: CreateWorkOrderPermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant", "admin"]))
):
    """Create a new work order permit request via POST"""
    try:
        return await _create_work_order_permit_logic(request, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create work order permit: {str(e)}")

@router.patch("/", response_model=dict)
async def create_work_order_permit_patch(
    request: CreateWorkOrderPermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant", "admin"]))
):
    """Create a new work order permit request via PATCH"""
    try:
        return await _create_work_order_permit_logic(request, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create work order permit: {str(e)}")

@router.post("/from-concern", response_model=WorkOrderPermit)
async def create_work_order_permit_from_concern(
    request: CreateWorkOrderPermitFromConcernRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant"]))
):
    """Create a new work order permit from a concern slip (Tenant only)"""
    try:
        service = WorkOrderPermitService()
        permit = await service.create_work_order_permit(
            concern_slip_id=request.concern_slip_id,
            requested_by=current_user["uid"],
            permit_data=request.dict()
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create work order permit: {str(e)}")

@router.patch("/{permit_id}/approve", response_model=WorkOrderPermit)
async def approve_permit(
    permit_id: str,
    request: ApprovePermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Approve work order permit (Admin only)"""
    try:
        service = WorkOrderPermitService()
        permit = await service.approve_permit(
            permit_id=permit_id,
            approved_by=current_user["uid"],
            conditions=request.conditions
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve permit: {str(e)}")

@router.patch("/{permit_id}/deny", response_model=WorkOrderPermit)
async def deny_permit(
    permit_id: str,
    request: DenyPermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Deny work order permit (Admin only)"""
    try:
        service = WorkOrderPermitService()
        permit = await service.deny_permit(
            permit_id=permit_id,
            denied_by=current_user["uid"],
            reason=request.reason
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deny permit: {str(e)}")

@router.patch("/{permit_id}/status", response_model=WorkOrderPermit)
async def update_permit_status(
    permit_id: str,
    request: UpdatePermitStatusRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Update work order permit status (Admin only)"""
    try:
        service = WorkOrderPermitService()
        permit = await service.update_permit_status(
            permit_id=permit_id,
            status=request.status,
            updated_by=current_user["uid"],
            notes=request.notes
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update permit status: {str(e)}")

@router.patch("/{permit_id}/start-work", response_model=WorkOrderPermit)
async def start_work(
    permit_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Mark work as started (updates actual start date)"""
    try:
        service = WorkOrderPermitService()
        permit = await service.start_work(
            permit_id=permit_id,
            started_by=current_user["uid"]
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start work: {str(e)}")

@router.get("/{permit_id}", response_model=WorkOrderPermit)
async def get_work_order_permit(
    permit_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Get work order permit by ID"""
    try:
        service = WorkOrderPermitService()
        permit = await service.get_work_order_permit(permit_id)
        if not permit:
            raise HTTPException(status_code=404, detail="Work order permit not found")
        
        # Tenants can only view their own permits
        if current_user.get("role") == "tenant" and permit.requested_by != current_user["uid"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return permit
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get work order permit: {str(e)}")

@router.get("/tenant/{tenant_id}", response_model=List[WorkOrderPermit])
async def get_permits_by_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Get all work order permits for a tenant"""
    try:
        # Tenants can only view their own permits
        if current_user.get("role") == "tenant" and current_user["uid"] != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = WorkOrderPermitService()
        permits = await service.get_permits_by_tenant(tenant_id)
        return permits
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get permits: {str(e)}")

@router.get("/status/{status}", response_model=List[WorkOrderPermit])
async def get_permits_by_status(
    status: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all work order permits with specific status (Admin only)"""
    try:
        service = WorkOrderPermitService()
        permits = await service.get_permits_by_status(status)
        return permits
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get permits: {str(e)}")

@router.get("/pending/all", response_model=List[WorkOrderPermit])
async def get_pending_permits(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all pending work order permits (Admin only)"""
    try:
        service = WorkOrderPermitService()
        permits = await service.get_pending_permits()
        return permits
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pending permits: {str(e)}")

class CompleteWorkOrderRequest(BaseModel):
    completion_notes: Optional[str] = None

@router.patch("/{work_order_id}/complete", response_model=dict)
async def complete_work_order_request(
    work_order_id: str,
    request: CompleteWorkOrderRequest = None,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Mark a standalone work order permit as completed"""
    try:
        from app.database.database_service import DatabaseService
        
        db = DatabaseService()
        
        # Try both formatted_id and id fields to find the document
        # First try by formatted_id (WP-YYYY-XXXXX format)
        success, permits_data, error = await db.query_documents(
            "work_order_permits", 
            [("formatted_id", "==", work_order_id)]
        )
        
        # If not found by formatted_id, try by id field
        if not success or not permits_data or len(permits_data) == 0:
            success, permits_data, error = await db.query_documents(
                "work_order_permits", 
                [("id", "==", work_order_id)]
            )
        
        if success and permits_data and len(permits_data) > 0:
            permit_data = permits_data[0]
            
            # Get the Firestore document ID from the query result
            # The document ID is typically stored as the key in Firestore
            # DatabaseService should return it with the query result
            firebase_doc_id = (
                permit_data.get("_doc_id") or 
                permit_data.get("_firebase_doc_id") or 
                permit_data.get("doc_id") or
                permit_data.get("id") or  # Try the id field
                work_order_id  # fallback to the work_order_id itself
            )
            
            print(f"[Work Order Complete] Found permit with ID: {work_order_id}")
            print(f"[Work Order Complete] Using Firebase doc ID: {firebase_doc_id}")
            print(f"[Work Order Complete] Available fields: {list(permit_data.keys())}")
            
            update_data = {
                "status": "completed",
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "completed_by": current_user["uid"]
            }
            
            # Add completion notes if provided
            if request and request.completion_notes:
                update_data["completion_notes"] = request.completion_notes
            
            print(f"[Work Order Complete] Updating document {firebase_doc_id} with data: {update_data}")
            
            success, error = await db.update_document("work_order_permits", firebase_doc_id, update_data)
            
            if not success:
                print(f"[Work Order Complete] Update failed: {error}")
                raise HTTPException(status_code=500, detail=f"Failed to update document: {error}")
            
            print(f"[Work Order Complete] Successfully marked work order {work_order_id} as completed")
            
            return {
                "success": True,
                "message": "Work order permit marked as completed",
                "work_order_id": work_order_id
            }
        else:
            print(f"[Work Order Complete] Work order permit not found: {work_order_id}")
            raise HTTPException(status_code=404, detail=f"Work order permit not found with ID: {work_order_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete work order: {str(e)}")

@router.get("/next-id", response_model=dict)
async def get_next_work_order_id(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "tenant"]))
):
    """Get next available work order permit ID"""
    try:
        now = datetime.utcnow()
        year = now.year
        day_of_year = now.timetuple().tm_yday
        next_id = f"WP-{year}-{str(day_of_year).zfill(5)}"
        
        return {
            "next_id": next_id,
            "year": year,
            "sequence": day_of_year
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate next ID: {str(e)}")

@router.get("/", response_model=List[WorkOrderPermit])
async def get_all_permits(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all work order permits (Admin only)"""
    try:
        service = WorkOrderPermitService()
        permits = await service.get_all_permits()
        return permits
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get permits: {str(e)}")





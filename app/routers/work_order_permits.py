from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.services.work_order_permit_service import WorkOrderPermitService
from app.models.database_models import WorkOrderPermit, BulkApproveRequest, BulkRejectRequest
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

class CompleteWorkOrderRequest(BaseModel):
    completion_notes: Optional[str] = None

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
        "requested_by_name": current_user.get("display_name") or current_user.get("name") or current_user.get("email") or "",
        "title": title,
        "description": request.request_type_detail,
        "location": request.location,
        "category": "",
        "priority": "",
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

# Bulk approve endpoint - MUST come before /{permit_id}/... routes
@router.patch("/bulk/approve", response_model=dict)
async def bulk_approve_permits(
    request: BulkApproveRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Bulk approve multiple work order permits (Admin only)"""
    print(f"[Bulk Approve] Received request from {current_user.get('uid')}")
    print(f"[Bulk Approve] Permit IDs: {request.permit_ids}")
    print(f"[Bulk Approve] Conditions: {request.conditions}")
    
    try:
        if not request.permit_ids or len(request.permit_ids) == 0:
            print("[Bulk Approve] ERROR: No permits provided")
            raise HTTPException(status_code=400, detail="No permits provided for approval")
        
        service = WorkOrderPermitService()
        print(f"[Bulk Approve] Calling service for {len(request.permit_ids)} permits")
        
        result = await service.bulk_approve_permits(
            permit_ids=request.permit_ids,
            approved_by=current_user["uid"],
            conditions=request.conditions
        )
        
        print(f"[Bulk Approve] Result: {result}")
        return result
        
    except ValueError as e:
        print(f"[Bulk Approve] ValueError: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Bulk Approve] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to bulk approve permits: {str(e)}")

# Bulk reject endpoint - MUST come before /{permit_id}/... routes
@router.patch("/bulk/reject", response_model=dict)
async def bulk_reject_permits(
    request: BulkRejectRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Bulk reject multiple work order permits (Admin only)"""
    print(f"[Bulk Reject] Received request from {current_user.get('uid')}")
    print(f"[Bulk Reject] Permit IDs: {request.permit_ids}")
    print(f"[Bulk Reject] Reason: {request.reason}")
    
    try:
        if not request.permit_ids or len(request.permit_ids) == 0:
            print("[Bulk Reject] ERROR: No permits provided")
            raise HTTPException(status_code=400, detail="No permits provided for rejection")
        
        if not request.reason or len(request.reason.strip()) == 0:
            print("[Bulk Reject] ERROR: Rejection reason is required")
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        service = WorkOrderPermitService()
        print(f"[Bulk Reject] Calling service for {len(request.permit_ids)} permits")
        
        result = await service.bulk_reject_permits(
            permit_ids=request.permit_ids,
            rejected_by=current_user["uid"],
            reason=request.reason
        )
        
        print(f"[Bulk Reject] Result: {result}")
        return result
        
    except ValueError as e:
        print(f"[Bulk Reject] ValueError: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Bulk Reject] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to bulk reject permits: {str(e)}")

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

@router.patch("/{permit_id}/approved", response_model=WorkOrderPermit)
async def approve_permit_alias(
    permit_id: str,
    request: ApprovePermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Alias endpoint for clients that call '/approved'"""
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

@router.patch("/{permit_id}/rejected", response_model=WorkOrderPermit)
async def reject_permit_alias(
    permit_id: str,
    request: DenyPermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Alias endpoint for clients that call '/rejected' instead of '/deny'"""
    try:
        service = WorkOrderPermitService()
        # Use update_permit_status to set a specific status and attach notes
        notes = request.reason if request and getattr(request, 'reason', None) else None
        permit = await service.update_permit_status(
            permit_id=permit_id,
            status="returned_to_tenant",
            updated_by=current_user["uid"],
            notes=notes
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject permit: {str(e)}")

@router.patch("/{permit_id}/returned", response_model=WorkOrderPermit)
async def return_permit_to_tenant(
    permit_id: str,
    request: DenyPermitRequest,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Endpoint to mark a permit as returned to tenant for edits (client calls '/returned').
    This updates the permit status to 'returned_to_tenant' and records admin notes if provided.
    """
    try:
        service = WorkOrderPermitService()
        # Use update_permit_status to set a specific status and attach notes
        notes = request.reason if request and getattr(request, 'reason', None) else None
        permit = await service.update_permit_status(
            permit_id=permit_id,
            status="returned_to_tenant",
            updated_by=current_user["uid"],
            notes=notes
        )
        return permit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to return permit to tenant: {str(e)}")

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

# File attachment endpoints for work order permits
@router.post("/{permit_id}/attachments")
async def upload_work_order_attachment(
    permit_id: str,
    current_user: dict = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """
    Upload an attachment to a work order permit.
    - Tenants can attach files to their own permits
    - Admin can attach files to any permit
    """
    try:
        service = WorkOrderPermitService()
        file_metadata = await service.upload_attachment(
            permit_id=permit_id,
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

@router.get("/{permit_id}/attachments")
async def list_work_order_attachments(
    permit_id: str,
    current_user: dict = Depends(get_current_user)
):
    """List all attachments for a work order permit"""
    try:
        service = WorkOrderPermitService()
        attachments = await service.list_attachments(
            permit_id=permit_id,
            user_id=current_user.get("uid")
        )
        
        return {
            "permit_id": permit_id,
            "attachments": attachments
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list attachments: {str(e)}")

@router.get("/{permit_id}/attachments/{file_id}")
async def get_work_order_attachment_url(
    permit_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a signed URL for accessing a specific attachment"""
    try:
        service = WorkOrderPermitService()
        signed_url = await service.get_attachment_url(
            permit_id=permit_id,
            file_id=file_id,
            user_id=current_user.get("uid")
        )

        return {"url": signed_url}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attachment URL: {str(e)}")

@router.delete("/{permit_id}")
async def delete_work_order_permit(
    permit_id: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["tenant", "admin"]))
):
    """Delete a work order permit.
    - Tenants can delete their own permits only when status is 'pending'.
    - Admins can delete any permit.
    """
    try:
        from app.database.database_service import DatabaseService

        db = DatabaseService()

        success, permits, error = await db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to query work order permits: {error}")

        if not permits or len(permits) == 0:
            raise HTTPException(status_code=404, detail="Work order permit not found")

        permit = permits[0]
        doc_id = permit.get("_doc_id") or permit.get("id") or permit_id

        owner_uid = permit.get("requested_by") or permit.get("created_by") or permit.get("reported_by")
        is_admin = current_user.get("role") == "admin" or current_user.get("is_admin") is True

        if not is_admin:
            if not owner_uid or owner_uid != current_user.get("uid"):
                raise HTTPException(status_code=403, detail="Tenants can only delete their own permits")
            if permit.get("status") != ["pending", "completed"]:
                raise HTTPException(status_code=403, detail="Tenants may only delete permits while status is 'pending'")

        delete_success, delete_error = await db.delete_document("work_order_permits", doc_id)
        if not delete_success:
            raise HTTPException(status_code=500, detail=f"Failed to delete permit: {delete_error}")

        return {"success": True, "message": "Work order permit deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete work order permit: {str(e)}")

@router.delete("/{permit_id}/attachments/{file_id}")
async def delete_work_order_attachment(
    permit_id: str,
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a specific attachment from a work order permit"""
    try:
        service = WorkOrderPermitService()
        success = await service.delete_attachment(
            permit_id=permit_id,
            file_id=file_id,
            user_id=current_user.get("uid")
        )

        return {"message": "Attachment deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete attachment: {str(e)}")

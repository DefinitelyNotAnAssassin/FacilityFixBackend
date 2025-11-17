from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..auth.dependencies import get_current_user, require_role
from ..services.inventory_service import inventory_service
from ..services.notification_manager import notification_manager
from ..models.database_models import (
    Inventory, InventoryTransaction, InventoryRequest, InventoryReservation,
    LowStockAlert, InventoryUsageAnalytics
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory Management"],
    responses={404: {"description": "Not found"}}
)

# ═══════════════════════════════════════════════════════════════════════════
# INVENTORY ITEM MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/items", response_model=Dict[str, Any])
async def create_inventory_item(
    item_data: Inventory,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Create a new inventory item (Admin only)"""
    try:
        success, item_id, error = await inventory_service.create_inventory_item(
            item_data.dict(exclude_unset=True), 
            current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory item created successfully",
                "item_id": item_id
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except Exception as e:
        logger.error(f"Error creating inventory item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/items/{item_id}", response_model=Dict[str, Any])
async def get_inventory_item(
    item_id: str = Path(..., description="Inventory item ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get inventory item by ID"""
    try:
        success, item_data, error = await inventory_service.get_inventory_item(item_id)
        
        if success and item_data:
            return {
                "success": True,
                "data": item_data
            }
        else:
            raise HTTPException(status_code=404, detail=error or "Item not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/items/{item_id}", response_model=Dict[str, Any])
async def update_inventory_item(
    item_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Update inventory item details (Admin only)"""
    try:
        success, error = await inventory_service.update_inventory_item(
            item_id, 
            update_data, 
            current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory item updated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inventory item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/items/{item_id}", response_model=Dict[str, Any])
async def patch_inventory_item(
    item_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Patch inventory item (e.g., deduct stock)"""
    try:
        success, error = await inventory_service.patch_inventory_item(
            item_id=item_id,
            update_data=update_data,
            updated_by=current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory item updated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error patching inventory item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/items/{item_id}", response_model=Dict[str, Any])
async def deactivate_inventory_item(
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Deactivate inventory item (Admin only)"""
    try:
        success, error = await inventory_service.deactivate_inventory_item(
            item_id, 
            current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory item deactivated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating inventory item {item_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}/items", response_model=Dict[str, Any])
async def get_building_inventory(
    building_id: str,
    include_inactive: bool = Query(False, description="Include inactive items"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all inventory items for a building"""
    try:
        success, items, error = await inventory_service.get_inventory_by_building(
            building_id, 
            include_inactive
        )
        
        if success:
            return {
                "success": True,
                "data": items,
                "count": len(items)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting building inventory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}/departments/{department}/items", response_model=Dict[str, Any])
async def get_department_inventory(
    building_id: str,
    department: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get inventory items by department"""
    try:
        success, items, error = await inventory_service.get_inventory_by_department(
            building_id, 
            department
        )
        
        if success:
            return {
                "success": True,
                "data": items,
                "count": len(items)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting department inventory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}/search", response_model=Dict[str, Any])
async def search_inventory(
    building_id: str,
    q: str = Query(..., description="Search term for item name, code, or description"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Search inventory items"""
    try:
        success, items, error = await inventory_service.search_inventory(building_id, q)
        
        if success:
            return {
                "success": True,
                "data": items,
                "count": len(items),
                "search_term": q
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching inventory: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}/summary", response_model=Dict[str, Any])
async def get_inventory_summary(
    building_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get inventory summary statistics for a building (Admin only)"""
    try:
        success, summary, error = await inventory_service.get_inventory_summary(building_id)
        
        if success:
            return {
                "success": True,
                "data": summary
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# INVENTORY RESERVATION ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel

class InventoryReservationRequest(BaseModel):
    inventory_id: str
    quantity: int
    maintenance_task_id: str

@router.post("/reservations", response_model=Dict[str, Any])
async def create_inventory_reservation(
    reservation_data: InventoryReservationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))  # Only admin can reserve
):
    """
    Reserve inventory for a maintenance task (Admin only).
    Creates a reservation record separate from requests.
    """
    try:
        reservation_dict = {
            'inventory_id': reservation_data.inventory_id,
            'quantity': reservation_data.quantity,
            'maintenance_task_id': reservation_data.maintenance_task_id
        }
        
        success, reservation_id, error = await inventory_service.create_inventory_reservation(
            reservation_dict,
            current_user["uid"]
        )
        if success:
            return {
                "success": True,
                "message": "Inventory reserved successfully",
                "reservation_id": reservation_id
            }
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating inventory reservation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/reservations", response_model=Dict[str, Any])
async def get_inventory_reservations(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    maintenance_task_id: Optional[str] = Query(None, description="Filter by maintenance task ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get inventory reservations with filters"""
    try:
        user_role = current_user.get("role", "staff")
        
        # If filtering by maintenance task, check assignment for staff users
        if maintenance_task_id and user_role == "staff":
            from ..services.maintenance_task_service import maintenance_task_service
            from ..services.user_id_service import user_id_service
            
            user_id = current_user.get("uid")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found")
            
            # Get user profile
            user_profile = await user_id_service.get_user_profile(user_id)
            
            # Get the specific task
            task = await maintenance_task_service.get_task(maintenance_task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Maintenance task not found")
            
            # Check if user is assigned to this task
            is_assigned = False
            
            # Check whole task assignment - use staff_id
            if task.assigned_to == user_profile.staff_id:
                is_assigned = True
            
            # Check checklist item assignments
            if not is_assigned and task.checklist_completed:
                checklist = task.checklist_completed or []
                has_assigned_item = any(
                    item.get("assigned_to") == user_profile.staff_id
                    for item in checklist
                )
                if has_assigned_item:
                    is_assigned = True
            
            if not is_assigned:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You can only view reservations for tasks you are assigned to"
                )
        elif user_role != "admin":
            # Admin-only access for general reservation queries
            raise HTTPException(status_code=403, detail="Admin access required")
        
        filters = {}
        if building_id:
            filters['building_id'] = building_id
        if maintenance_task_id:
            filters['maintenance_task_id'] = maintenance_task_id
        
        success, reservations, error = await inventory_service.get_inventory_reservations(filters)
        
        if success:
            return {
                "success": True,
                "data": reservations,
                "count": len(reservations)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory reservations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/reservations/{reservation_id}/consumed", response_model=Dict[str, Any])
async def mark_reservation_consumed(
    reservation_id: str = Path(..., description="Reservation ID"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))  # Admin or staff can mark as consumed
):
    """Mark inventory reservation as consumed (items used for completed task)"""
    try:
        success, error = await inventory_service.mark_reservation_consumed(
            reservation_id,
            current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Reservation marked as consumed successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking reservation {reservation_id} as consumed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/reservations/{reservation_id}/released", response_model=Dict[str, Any])
async def release_reservation(
    reservation_id: str = Path(..., description="Reservation ID"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))  # Admin or staff can release
):
    """Release inventory reservation (cancel reservation)"""
    try:
        success, error = await inventory_service.release_reservation(
            reservation_id,
            current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Reservation released successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing reservation {reservation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/reservations/{reservation_id}/received", response_model=Dict[str, Any])
async def mark_reservation_received(
    reservation_id: str = Path(..., description="Reservation ID"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))  # Admin or staff can mark as received
):
    """Mark inventory reservation as received (staff has picked up the items)"""
    try:
        success, error = await inventory_service.mark_reservation_received(
            reservation_id,
            current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Reservation marked as received successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking reservation {reservation_id} as received: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

class ReplacementRequest(BaseModel):
    reason: str = "Item found defective during inspection"
    quantity_needed: Optional[int] = None  # If not specified, uses original quantity

@router.post("/reservations/{reservation_id}/request-replacement", response_model=Dict[str, Any])
async def request_replacement_for_defective_item(
    replacement_data: ReplacementRequest,
    reservation_id: str = Path(..., description="Reservation ID"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))  # Admin or staff can request replacement
):
    """Request replacement for a defective reserved item"""
    try:
        success, request_id, error = await inventory_service.request_replacement_for_defective_item(
            reservation_id,
            replacement_data.dict(),
            current_user["uid"]
        )
        
        if success:
            # Send notification to admins about the replacement request
            try:
                await notification_manager.notify_inventory_replacement_requested(
                    reservation_id=reservation_id,
                    request_id=request_id,
                    requested_by=current_user["uid"],
                    reason=replacement_data.reason,
                    quantity_needed=replacement_data.quantity_needed,
                )
                logger.info(f"Notification sent for replacement request {request_id} on reservation {reservation_id}")
            except Exception as exc:
                logger.error(f"Failed to send notification for replacement request {request_id}: {exc}")
                # Don't fail the request if notification fails

            return {
                "success": True,
                "message": "Replacement request created successfully",
                "request_id": request_id
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting replacement for reservation {reservation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# STOCK MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/items/{item_id}/consume", response_model=Dict[str, Any])
async def consume_stock(
    item_id: str,
    quantity: int = Query(..., gt=0, description="Quantity to consume"),
    reference_type: Optional[str] = Query(None, description="Reference type (job_service, work_permit, etc.)"),
    reference_id: Optional[str] = Query(None, description="Reference ID"),
    reason: Optional[str] = Query(None, description="Reason for consumption"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Consume stock (automatic deduction)"""
    try:
        success, error = await inventory_service.consume_stock(
            item_id=item_id,
            quantity=quantity,
            performed_by=current_user["uid"],
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason
        )
        
        if success:
            return {
                "success": True,
                "message": f"Successfully consumed {quantity} units from inventory"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error consuming stock: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/items/{item_id}/restock", response_model=Dict[str, Any])
async def restock_item(
    item_id: str,
    quantity: int = Query(..., gt=0, description="Quantity to add"),
    cost_per_unit: Optional[float] = Query(None, description="Cost per unit"),
    reason: Optional[str] = Query(None, description="Reason for restocking"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Add stock to inventory (Admin only)"""
    try:
        success, error = await inventory_service.restock_item(
            item_id=item_id,
            quantity=quantity,
            performed_by=current_user["uid"],
            cost_per_unit=cost_per_unit,
            reason=reason
        )
        
        if success:
            return {
                "success": True,
                "message": f"Successfully added {quantity} units to inventory"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restocking item: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/items/{item_id}/adjust", response_model=Dict[str, Any])
async def adjust_stock(
    item_id: str,
    new_quantity: int = Query(..., ge=0, description="New stock quantity"),
    reason: Optional[str] = Query(None, description="Reason for adjustment"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Adjust stock to specific quantity (Admin only)"""
    try:
        success, error = await inventory_service.adjust_stock(
            item_id=item_id,
            new_quantity=new_quantity,
            performed_by=current_user["uid"],
            reason=reason
        )
        
        if success:
            return {
                "success": True,
                "message": f"Successfully adjusted stock to {new_quantity} units"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adjusting stock: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# LOW STOCK ALERTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/alerts/low-stock", response_model=Dict[str, Any])
async def get_low_stock_alerts(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    status: str = Query("low stock", description="Alert status"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get low stock alerts (Admin only)"""
    try:
        success, alerts, error = await inventory_service.get_low_stock_alerts(
            building_id=building_id,
            status=status
        )
        
        if success:
            return {
                "success": True,
                "data": alerts,
                "count": len(alerts)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting low stock alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/alerts/{alert_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_low_stock_alert(
    alert_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Acknowledge a low stock alert (Admin only)"""
    try:
        success, error = await inventory_service.acknowledge_low_stock_alert(
            alert_id=alert_id,
            acknowledged_by=current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Low stock alert acknowledged"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging low stock alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# INVENTORY TRANSACTIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/transactions", response_model=Dict[str, Any])
async def get_inventory_transactions(
    inventory_id: Optional[str] = Query(None, description="Filter by inventory item ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get inventory transaction history (Admin only)"""
    try:
        success, transactions, error = await inventory_service.get_inventory_transactions(
            inventory_id=inventory_id,
            transaction_type=transaction_type
        )
        
        if success:
            return {
                "success": True,
                "data": transactions,
                "count": len(transactions)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# INVENTORY REQUESTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/requests", response_model=Dict[str, Any])
async def create_inventory_request(
    request_data: InventoryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["staff", "admin"]))
):
    """Create an inventory request (Staff and Admin only)"""
    try:
        from ..services.user_id_service import user_id_service

        # Set the requester
        request_dict = request_data.dict(exclude_unset=True)
        request_dict["requested_by"] = current_user["uid"]

        # Get user profile to populate department
        try:
            user_profile = await user_id_service.get_user_profile(current_user["uid"])
            if user_profile and user_profile.department:
                request_dict["department"] = user_profile.department
        except Exception as profile_error:
            logger.warning(f"Could not fetch user profile for department: {str(profile_error)}")
            # Continue without department if profile fetch fails

        success, request_id, error = await inventory_service.create_inventory_request(request_dict)

        if success:
            return {
                "success": True,
                "message": "Inventory request created successfully",
                "request_id": request_id
            }
        else:
            raise HTTPException(status_code=400, detail=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating inventory request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/requests", response_model=Dict[str, Any])
async def get_inventory_requests(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    requested_by: Optional[str] = Query(None, description="Filter by requester"),
    maintenance_task_id: Optional[str] = Query(None, description="Filter by maintenance task ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get inventory requests with filters"""
    try:
        # Staff can only see their own requests unless they're admin
        if current_user.get("role") == "staff" and not requested_by:
            requested_by = current_user["uid"]

        success, requests, error = await inventory_service.get_inventory_requests(
            building_id=building_id,
            status=status,
            requested_by=requested_by,
            maintenance_task_id=maintenance_task_id
        )

        if success:
            return {
                "success": True,
                "data": requests,
                "count": len(requests)
            }
        else:
            raise HTTPException(status_code=400, detail=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/requests/{request_id}", response_model=Dict[str, Any])
async def get_inventory_request_by_id(
    request_id: str = Path(..., description="Inventory request ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get inventory request by ID"""
    try:
        success, request_data, error = await inventory_service.get_inventory_request_by_id(request_id)

        if success and request_data:
            return {
                "success": True,
                "data": request_data
            }
        else:
            raise HTTPException(status_code=404, detail=error or "Request not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory request {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/requests/{request_id}/approve", response_model=Dict[str, Any])
async def approve_inventory_request(
    request_id: str,
    quantity_approved: Optional[int] = Query(None, description="Quantity approved (defaults to requested)"),
    admin_notes: Optional[str] = Query(None, description="Admin notes"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Approve an inventory request (Admin only)"""
    try:
        success, error = await inventory_service.approve_inventory_request(
            request_id=request_id,
            approved_by=current_user["uid"],
            quantity_approved=quantity_approved,
            admin_notes=admin_notes
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory request approved successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving inventory request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/requests/{request_id}/deny", response_model=Dict[str, Any])
async def deny_inventory_request(
    request_id: str,
    admin_notes: str = Query(..., description="Reason for denial"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Deny an inventory request (Admin only)"""
    try:
        success, error = await inventory_service.deny_inventory_request(
            request_id=request_id,
            denied_by=current_user["uid"],
            admin_notes=admin_notes
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory request denied"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error denying inventory request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/requests/{request_id}/fulfill", response_model=Dict[str, Any])
async def fulfill_inventory_request(
    request_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Fulfill an approved inventory request"""
    try:
        success, error = await inventory_service.fulfill_inventory_request(
            request_id=request_id,
            fulfilled_by=current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Inventory request fulfilled successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fulfilling inventory request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/requests/{request_id}", response_model=Dict[str, Any])
async def update_inventory_request(
    request_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update inventory request status and handle stock deduction"""
    try:
        # Extract status and deduct_stock flag
        new_status = update_data.get("status")
        deduct_stock = update_data.get("deduct_stock", False)
        
        # Role checks
        if new_status in ["approved", "rejected"] and current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Only admins can approve/reject requests")
        
        if new_status == "received" and deduct_stock:
            # Staff can receive approved or reserved requests
            if current_user.get("role") not in ["admin", "staff"]:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        success, error = await inventory_service.update_inventory_request(
            request_id=request_id,
            update_data=update_data,
            updated_by=current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": f"Inventory request updated to status: {new_status}"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inventory request {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# LOW STOCK ALERTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/alerts/low-stock", response_model=Dict[str, Any])
async def get_low_stock_alerts(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    status: str = Query("low stock", description="Alert status"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Get low stock alerts"""
    try:
        success, alerts, error = await inventory_service.get_low_stock_alerts(
            building_id=building_id,
            status=status
        )
        
        if success:
            return {
                "success": True,
                "data": alerts,
                "count": len(alerts)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting low stock alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/alerts/{alert_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_low_stock_alert(
    alert_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Acknowledge a low stock alert"""
    try:
        success, error = await inventory_service.acknowledge_low_stock_alert(
            alert_id=alert_id,
            acknowledged_by=current_user["uid"]
        )
        
        if success:
            return {
                "success": True,
                "message": "Low stock alert acknowledged"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging low stock alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# TRANSACTION HISTORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/transactions", response_model=Dict[str, Any])
async def get_inventory_transactions(
    inventory_id: Optional[str] = Query(None, description="Filter by inventory item ID"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Get inventory transaction history"""
    try:
        success, transactions, error = await inventory_service.get_inventory_transactions(
            inventory_id=inventory_id,
            transaction_type=transaction_type
        )
        
        if success:
            return {
                "success": True,
                "data": transactions,
                "count": len(transactions)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS AND REPORTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/buildings/{building_id}/summary", response_model=Dict[str, Any])
async def get_inventory_summary(
    building_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin", "staff"]))
):
    """Get inventory summary statistics for a building"""
    try:
        success, summary, error = await inventory_service.get_inventory_summary(building_id)
        
        if success:
            return {
                "success": True,
                "data": summary
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}/analytics", response_model=Dict[str, Any])
async def get_usage_analytics(
    building_id: str,
    period_type: str = Query("monthly", description="Period type (daily, weekly, monthly, quarterly, yearly)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get usage analytics for inventory items (Admin only)"""
    try:
        success, analytics, error = await inventory_service.generate_usage_analytics(
            building_id=building_id,
            period_type=period_type
        )
        
        if success:
            return {
                "success": True,
                "data": analytics,
                "count": len(analytics),
                "period_type": period_type
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting usage analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# MAINTENANCE TASK INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/maintenance-task/{task_id}/requests", response_model=Dict[str, Any])
async def get_requests_by_maintenance_task(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all inventory requests AND reservations linked to a specific maintenance task"""
    try:
        # Security check: Ensure user can access this task
        user_role = current_user.get("role", "staff")

        if user_role != "admin":
            # Staff can only view reservations for tasks they're assigned to
            from ..services.maintenance_task_service import maintenance_task_service
            from ..services.user_id_service import user_id_service

            user_id = current_user.get("uid")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found")

            # Get user profile to get full name
            user_profile = await user_id_service.get_user_profile(user_id)

            # Get the specific task
            task = await maintenance_task_service.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Maintenance task not found")

            # Check if user is assigned to this task
            is_assigned = False

            # Check whole task assignment
            if task.assigned_to == f"{user_profile.first_name} {user_profile.last_name}" or task.assigned_to == user_id:
                is_assigned = True

            # Check checklist item assignments
            if not is_assigned and task.checklist_completed:
                checklist = task.checklist_completed or []
                has_assigned_item = any(
                    item.get("assigned_to") == user_profile.staff_id
                    for item in checklist
                )
                if has_assigned_item:
                    is_assigned = True

            if not is_assigned:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: You can only view inventory for tasks you are assigned to"
                )

        # User has permission, proceed with getting items
        success, items, error = await inventory_service.get_requests_by_maintenance_task(task_id)

        if success:
            return {
                "success": True,
                "data": items,
                "count": len(items),
                "maintenance_task_id": task_id
            }
        else:
            raise HTTPException(status_code=400, detail=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory items for maintenance task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/my-maintenance-requests", response_model=Dict[str, Any])
async def get_my_maintenance_inventory_requests(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all inventory requests from maintenance tasks assigned to current user"""
    try:
        from ..services.maintenance_task_service import maintenance_task_service
        from ..services.user_id_service import user_id_service

        user_id = current_user.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")

        # Get user profile to get full name
        user_profile = await user_id_service.get_user_profile(user_id)

        # Get all maintenance tasks assigned to this user
        all_tasks = await maintenance_task_service.list_tasks({})
        assigned_tasks = []

        for task in all_tasks:
            # Check if whole task is assigned to user
            if task.assigned_to == f"{user_profile.first_name} {user_profile.last_name}" or task.assigned_to == user_id or task.assigned_staff_name == f"{user_profile.first_name} {user_profile.last_name}":
                assigned_tasks.append(task)
                continue

            # Check if any checklist item is assigned to user
            checklist = task.checklist_completed or []
            has_assigned_item = any(
                item.get("assigned_to") == user_profile.staff_id
                for item in checklist
            )

            if has_assigned_item:
                assigned_tasks.append(task)

        # Collect all inventory request IDs from assigned tasks
        all_request_ids = []
        for task in assigned_tasks:
            if task.inventory_request_ids:
                all_request_ids.extend(task.inventory_request_ids)

        # Fetch all inventory requests
        if not all_request_ids:
            return {
                "success": True,
                "data": [],
                "count": 0
            }

        # Get all requests matching these IDs
        success, all_requests, error = await inventory_service.get_inventory_requests()

        if not success:
            raise HTTPException(status_code=400, detail=error)

        # Filter to only include requests in our ID list
        filtered_requests = [
            req for req in all_requests
            if req.get('_doc_id') in all_request_ids or req.get('id') in all_request_ids
        ]

        return {
            "success": True,
            "data": filtered_requests,
            "count": len(filtered_requests)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting maintenance inventory requests for user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/health", response_model=Dict[str, Any])
async def inventory_health_check():
    """Health check for inventory service"""
    return {
        "status": "healthy",
        "service": "inventory_management",
        "timestamp": datetime.now().isoformat()
    }

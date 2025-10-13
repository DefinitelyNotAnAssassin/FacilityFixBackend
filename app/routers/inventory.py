from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..auth.dependencies import get_current_user, require_role
from ..services.inventory_service import inventory_service
from ..models.database_models import (
    Inventory, InventoryTransaction, InventoryRequest, 
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

@router.get("/items", response_model=Dict[str, Any])
async def get_all_inventory_items(
    include_inactive: bool = Query(False, description="Include inactive items"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get all inventory items (no building filter)"""
    try:
        success, items, error = await inventory_service.get_all_inventory_items(include_inactive)
        
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
        logger.error(f"Error getting all inventory items: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
        # Set the requester
        request_dict = request_data.dict(exclude_unset=True)
        request_dict["requested_by"] = current_user["uid"]
        
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

# ═══════════════════════════════════════════════════════════════════════════
# LOW STOCK ALERTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/alerts/low-stock", response_model=Dict[str, Any])
async def get_low_stock_alerts(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    status: str = Query("active", description="Alert status"),
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
    """Get all inventory requests linked to a specific maintenance task"""
    try:
        success, requests, error = await inventory_service.get_requests_by_maintenance_task(task_id)
        
        if success:
            return {
                "success": True,
                "data": requests,
                "count": len(requests),
                "maintenance_task_id": task_id
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory requests for maintenance task {task_id}: {str(e)}")
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

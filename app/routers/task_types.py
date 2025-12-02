from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Dict, Any, List, Optional
from ..auth.dependencies import get_current_user, require_role
from ..services.task_type_service import task_type_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/task-types",
    tags=["Task Types"],
    responses={404: {"description": "Not found"}}
)

@router.post("/", response_model=Dict[str, Any])
async def create_task_type(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Create a new Task Type (Admin only)"""
    try:
        success, doc_id, error = await task_type_service.create_task_type(payload, current_user['uid'])
        if success:
            ok, doc, err = await task_type_service.get_task_type(doc_id)
            return {"success": True, "message": "Task type created", "task_type_id": doc_id, "data": doc}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating task type: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=Dict[str, Any])
async def list_task_types(
    include_inactive: bool = Query(False, description="Include inactive/soft-deleted types"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        success, items, error = await task_type_service.list_task_types(include_inactive=include_inactive)
        if success:
            return {"success": True, "data": items, "count": len(items)}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error listing task types: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/maintenance-types", response_model=Dict[str, Any])
async def list_maintenance_types(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return a list of maintenance types (distinct values) and known defaults"""
    try:
        # Query all active task types and collect maintenance_type values
        success, items, err = await task_type_service.list_task_types(include_inactive=True)
        types = set()
        if success:
            for it in items:
                mt = it.get('maintenance_type')
                if mt:
                    types.add(mt)

        # Include a set of default common maintenance types
        DEFAULTS = ["Preventive", "Corrective", "Proactive", "Emergency", "Inspection", "Repair", "Routine"]
        types = list(sorted(types.union(DEFAULTS)))
        return {"success": True, "data": types}
    except Exception as e:
        logger.exception(f"Error listing maintenance types: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{task_type_id}", response_model=Dict[str, Any])
async def get_task_type(
    task_type_id: str = Path(..., description="Task Type document ID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        success, doc, error = await task_type_service.get_task_type(task_type_id)
        if success and doc:
            return {"success": True, "data": doc}
        else:
            raise HTTPException(status_code=404, detail=error or "Task Type not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching task type {task_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{task_type_id}", response_model=Dict[str, Any])
async def update_task_type(
    task_type_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    try:
        success, error = await task_type_service.update_task_type(task_type_id, payload, current_user['uid'])
        if success:
            ok, doc, err = await task_type_service.get_task_type(task_type_id)
            return {"success": True, "message": "Task Type updated", "data": doc}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating task type {task_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{task_type_id}", response_model=Dict[str, Any])
async def delete_task_type(
    task_type_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    try:
        success, error = await task_type_service.soft_delete_task_type(task_type_id, current_user['uid'])
        if success:
            return {"success": True, "message": "Task Type soft-deleted (inactive)"}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error soft-deleting task type {task_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# inventory item endpoints
@router.post("/{task_type_id}/inventory-items", response_model=Dict[str, Any])
async def add_inventory_item_to_task_type(
    task_type_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    try:
        success, error = await task_type_service.add_inventory_item(task_type_id, payload, current_user['uid'])
        if success:
            ok, doc, err = await task_type_service.get_task_type(task_type_id)
            return {"success": True, "message": "Inventory item added", "data": doc}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error adding inventory item to task type {task_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{task_type_id}/inventory-items/{item_id}", response_model=Dict[str, Any])
async def remove_inventory_item_from_task_type(
    task_type_id: str,
    item_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    try:
        success, error = await task_type_service.remove_inventory_item(task_type_id, item_id, current_user['uid'])
        if success:
            ok, doc, err = await task_type_service.get_task_type(task_type_id)
            return {"success": True, "message": "Inventory item removed", "data": doc}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error removing inventory item {item_id} from task type {task_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/maintenance-types", response_model=Dict[str, Any])
async def list_maintenance_types(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Return a list of maintenance types (distinct values) and known defaults"""
    try:
        # Query all active task types and collect maintenance_type values
        success, items, err = await task_type_service.list_task_types(include_inactive=True)
        types = set()
        if success:
            for it in items:
                mt = it.get('maintenance_type')
                if mt:
                    types.add(mt)

        # Include a set of default common maintenance types
        DEFAULTS = ["Preventive", "Corrective", "Proactive", "Emergency", "Inspection", "Repair", "Routine"]
        types = list(sorted(types.union(DEFAULTS)))
        return {"success": True, "data": types}
    except Exception as e:
        logger.exception(f"Error listing maintenance types: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.models.database_models import MaintenanceTask
from app.services.maintenance_task_service import maintenance_task_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])
class MaintenanceTaskCreate(BaseModel):
    building_id: str
    task_title: str
    task_description: str
    location: str
    scheduled_date: datetime
    assigned_to: Optional[str] = None
    category: Optional[str] = "preventive"
    priority: Optional[str] = "medium"
    task_type: Optional[str] = "scheduled"
    maintenance_type: Optional[str] = None  # internal, external, ipm, epm
    scheduled_time_slot: Optional[str] = None
    estimated_duration: Optional[int] = Field(default=None, ge=0)
    recurrence_type: Optional[str] = "none"
    parent_task_id: Optional[str] = None
    template_id: Optional[str] = None
    equipment_id: Optional[str] = None
    parts_used: Optional[List[Dict[str, Any]]] = []  # type: ignore[list-item]
    tools_used: Optional[List[str]] = []
    checklist_completed: Optional[List[Dict[str, Any]]] = []  # type: ignore[list-item]
    photos: Optional[List[str]] = []
    signature: Optional[str] = None
    quality_rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback_notes: Optional[str] = None
    status: Optional[str] = None
    
    # External maintenance contractor fields
    contractor_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[str] = None
    service_category: Optional[str] = None
    department: Optional[str] = None
    
    # Additional frontend compatibility fields
    task_code: Optional[str] = None
    formatted_id: Optional[str] = None
    assigned_staff_name: Optional[str] = None
    
    # Assessment and tracking fields
    assessment_received: Optional[str] = None
    logged_by: Optional[str] = None
    logged_date: Optional[str] = None
    assessment: Optional[str] = None
    recommendation: Optional[str] = None
    admin_notification: Optional[str] = None
    
    # Date fields that might come from frontend
    date_created: Optional[str] = None
    created_by: Optional[str] = None
    start_date: Optional[str] = None
    next_due_date: Optional[str] = None
    service_window_start: Optional[str] = None
    service_window_end: Optional[str] = None
    service_date_actual: Optional[str] = None


class MaintenanceTaskUpdate(BaseModel):
    task_title: Optional[str] = None
    task_description: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    scheduled_time_slot: Optional[str] = None
    estimated_duration: Optional[int] = Field(default=None, ge=0)
    task_type: Optional[str] = None
    maintenance_type: Optional[str] = None
    recurrence_type: Optional[str] = None
    parts_used: Optional[List[Dict[str, Any]]] = None  # type: ignore[list-item]
    tools_used: Optional[List[str]] = None
    checklist_completed: Optional[List[Dict[str, Any]]] = None  # type: ignore[list-item]
    photos: Optional[List[str]] = None
    signature: Optional[str] = None
    quality_rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback_notes: Optional[str] = None
    completion_notes: Optional[str] = None
    actual_duration: Optional[int] = Field(default=None, ge=0)
    
    # External maintenance contractor fields
    contractor_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[str] = None
    service_category: Optional[str] = None
    department: Optional[str] = None
    
    # Assessment and tracking fields
    assessment_received: Optional[str] = None
    logged_by: Optional[str] = None
    logged_date: Optional[str] = None
    assessment: Optional[str] = None
    recommendation: Optional[str] = None
    admin_notification: Optional[str] = None
    
    # Date fields
    service_date_actual: Optional[str] = None
    assessment_notes: Optional[str] = None
    recommendations: Optional[str] = None


def _serialize_task(task: MaintenanceTask) -> Dict[str, Any]:
    data = task.dict()
    
    # Serialize datetime fields
    for key in (
        "scheduled_date",
        "started_at",
        "completed_at",
        "next_occurrence",
        "created_at",
        "updated_at",
    ):
        value = data.get(key)
        if isinstance(value, datetime):
            data[key] = value.isoformat()

    # Ensure ID fields
    data["formatted_id"] = data.get("formatted_id") or data.get("id")
    
    # Ensure title fields
    data["task_title"] = data.get("task_title") or data.get("title") or "Maintenance Task"
    data["title"] = data.get("task_title")
    
    # Ensure staff assignment fields
    data["assigned_staff"] = data.get("assigned_to")
    data["assigned_staff_id"] = data.get("assigned_to")
    
    # Ensure location
    data["location"] = data.get("location") or ""
    
    # Ensure recurrence fields
    data["recurrence"] = data.get("recurrence_type") or "none"
    data["recurrence_type"] = data.get("recurrence_type") or "none"

    # Ensure downstream clients receive the expected maintenance type labels
    raw_type = str(
        data.get("maintenanceType")
        or data.get("maintenance_type")
        or data.get("task_type")
        or ""
    ).lower()
    if "external" in raw_type or raw_type == "epm":
        type_label = "External"
        type_slug = "external"
    elif "internal" in raw_type or raw_type == "ipm":
        type_label = "Internal"
        type_slug = "internal"
    else:
        type_label = "Internal"
        type_slug = "internal"

    data["maintenanceType"] = type_label
    data["maintenance_type"] = type_slug
    
    # Ensure essential fields have defaults
    data["priority"] = data.get("priority") or "medium"
    data["status"] = data.get("status") or "scheduled"
    data["category"] = data.get("category") or "preventive"
    data["building_id"] = data.get("building_id") or "default_building"
    
    # Ensure lists
    data["checklist_completed"] = data.get("checklist_completed") or []
    data["parts_used"] = data.get("parts_used") or []
    data["tools_used"] = data.get("tools_used") or []
    data["photos"] = data.get("photos") or []
    
    return data


@router.get("/")
async def get_all_maintenance_tasks(
    building_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Get all maintenance tasks."""
    try:
        filters: Dict[str, Any] = {}
        if building_id:
            filters["building_id"] = building_id
        if status:
            filters["status"] = status
        if assigned_to:
            filters["assigned_to"] = assigned_to
        if category:
            filters["category"] = category

        logger.info(
            "[DEBUG] Fetching maintenance tasks for user %s with filters %s",
            current_user.get("email"),
            filters,
        )

        tasks = await maintenance_task_service.list_tasks(filters)
        serialized = [_serialize_task(task) for task in tasks]
        logger.info("[DEBUG] Returning %d maintenance tasks", len(serialized))
        return serialized

    except ValueError as exc:
        logger.error("Error getting maintenance tasks: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Error getting maintenance tasks: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get maintenance tasks: {exc}")


@router.get("/{task_id}")
async def get_maintenance_task_by_id(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific maintenance task by ID."""
    try:
        task = await maintenance_task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        return _serialize_task(task)

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.error("Error getting maintenance task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to get maintenance task: {exc}")


@router.post("/")
async def create_maintenance_task(
    task_data: MaintenanceTaskCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new maintenance task."""
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        task = await maintenance_task_service.create_task(
            current_user.get("uid"),
            task_data.dict(exclude_unset=True),
        )

        return {
            "success": True,
            "message": "Maintenance task created successfully",
            "task": _serialize_task(task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error creating maintenance task: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error creating maintenance task: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to create maintenance task: {exc}")


@router.put("/{task_id}")
async def update_maintenance_task(
    task_id: str,
    updates: MaintenanceTaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing maintenance task."""
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        updated = await maintenance_task_service.update_task(
            task_id,
            updates.dict(exclude_unset=True),
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        return {
            "success": True,
            "message": "Maintenance task updated successfully",
            "task": _serialize_task(updated),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error updating maintenance task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error updating maintenance task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to update maintenance task: {exc}")


@router.delete("/{task_id}")
async def delete_maintenance_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a maintenance task."""
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        await maintenance_task_service.delete_task(task_id)
        return {
            "success": True,
            "message": "Maintenance task deleted successfully",
            "id": task_id,
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error deleting maintenance task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error deleting maintenance task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to delete maintenance task: {exc}")


class ChecklistItemUpdate(BaseModel):
    """Model for updating a single checklist item."""
    item_id: str
    completed: bool
    task: Optional[str] = None


class ChecklistUpdate(BaseModel):
    """Model for updating the entire checklist."""
    checklist_completed: List[Dict[str, Any]]


@router.patch("/{task_id}/checklist")
async def update_maintenance_checklist(
    task_id: str,
    checklist_data: ChecklistUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update the checklist for a maintenance task.
    
    The checklist should be an array of objects with the following structure:
    [
        {
            "id": "unique_item_id",
            "task": "Task description",
            "completed": true/false
        }
    ]
    """
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Validate checklist structure
        for item in checklist_data.checklist_completed:
            if "id" not in item or "task" not in item or "completed" not in item:
                raise HTTPException(
                    status_code=400,
                    detail="Each checklist item must have 'id', 'task', and 'completed' fields"
                )
            if not isinstance(item["completed"], bool):
                raise HTTPException(
                    status_code=400,
                    detail="'completed' field must be a boolean"
                )

        # Determine status based on checklist completion
        total_items = len(checklist_data.checklist_completed)
        completed_items = sum(1 for item in checklist_data.checklist_completed if item.get("completed", False))
        
        update_data = {"checklist_completed": checklist_data.checklist_completed}
        
        # Auto-update status based on checklist completion
        if total_items > 0:
            if completed_items == total_items:
                # All items completed
                update_data["status"] = "completed"
                update_data["completed_at"] = datetime.now()
                logger.info("All checklist items completed for task %s, setting status to 'completed'", task_id)
            elif completed_items > 0:
                # Some items completed - set to in_progress
                update_data["status"] = "in_progress"
                logger.info("Checklist progress for task %s: %d/%d items completed, setting status to 'in_progress'", 
                           task_id, completed_items, total_items)

        # Update the task with the new checklist and status
        updated_task = await maintenance_task_service.update_task(
            task_id,
            update_data
        )

        if not updated_task:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        return {
            "success": True,
            "message": "Checklist updated successfully",
            "task": _serialize_task(updated_task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error updating checklist for task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error updating checklist for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to update checklist: {exc}")


@router.patch("/{task_id}/checklist/{item_id}")
async def update_checklist_item(
    task_id: str,
    item_id: str,
    item_update: ChecklistItemUpdate,
    current_user: dict = Depends(get_current_user),
):
    """
    Update a single checklist item's completion status.
    
    This is useful for toggling individual checklist items without sending the entire list.
    """
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Get current task
        task = await maintenance_task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        # Get current checklist
        current_checklist = task.checklist_completed or []
        
        # Find and update the specific item
        item_found = False
        updated_checklist = []
        for item in current_checklist:
            if item.get("id") == item_id:
                item_found = True
                updated_item = {
                    "id": item_id,
                    "task": item_update.task if item_update.task is not None else item.get("task", ""),
                    "completed": item_update.completed
                }
                updated_checklist.append(updated_item)
            else:
                updated_checklist.append(item)

        if not item_found:
            raise HTTPException(
                status_code=404,
                detail=f"Checklist item with id '{item_id}' not found"
            )

        # Determine status based on checklist completion
        total_items = len(updated_checklist)
        completed_items = sum(1 for item in updated_checklist if item.get("completed", False))
        
        update_data = {"checklist_completed": updated_checklist}
        
        # Auto-update status based on checklist completion
        if total_items > 0:
            if completed_items == total_items:
                # All items completed
                update_data["status"] = "completed"
                update_data["completed_at"] = datetime.now()
                logger.info("All checklist items completed for task %s, setting status to 'completed'", task_id)
            elif completed_items > 0:
                # Some items completed - set to in_progress
                update_data["status"] = "in_progress"
                if not task.started_at:
                    update_data["started_at"] = datetime.now()
                logger.info("Checklist progress for task %s: %d/%d items completed, setting status to 'in_progress'", 
                           task_id, completed_items, total_items)

        # Update the task
        updated_task = await maintenance_task_service.update_task(
            task_id,
            update_data
        )

        return {
            "success": True,
            "message": "Checklist item updated successfully",
            "task": _serialize_task(updated_task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error updating checklist item for task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error updating checklist item for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to update checklist item: {exc}")
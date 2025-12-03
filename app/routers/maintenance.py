import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.models.database_models import MaintenanceTask
from app.services.maintenance_task_service import maintenance_task_service
from app.services.special_maintenance_service import special_maintenance_service
from app.services.user_id_service import UserIdService, user_id_service
from app.services.notification_manager import notification_manager
from app.models.notification_models import NotificationType, NotificationPriority, NotificationChannel
from app.database.collections import COLLECTIONS
from app.core.config import settings
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _convert_to_local_time(dt: datetime) -> datetime:
    """Convert UTC datetime to local timezone based on TZ_OFFSET setting"""
    if not dt:
        return dt
    
    # If the datetime is naive, assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to local timezone by adding the offset
    local_tz = timezone(timedelta(hours=settings.TZ_OFFSET))
    local_dt = dt.astimezone(local_tz)
    
    # Return as naive datetime (remove timezone info) so frontend treats it as local time
    return local_dt.replace(tzinfo=None)


def _compute_next_due_date(start_date: datetime, recurrence_type: str) -> Optional[datetime]:
    """
    Compute the next due date based on start date and recurrence type.

    Recurrence format examples:
    - "Every 1 month", "3 months"
    - "Every 2 weeks", "2 weeks"
    - "monthly", "quarterly", "yearly"
    - "weekly", "biweekly"
    - "none" or empty = no recurrence

    Returns:
        The next occurrence date, or None if no recurrence
    """
    if not recurrence_type or recurrence_type.lower() in ["none", "n/a", ""]:
        return None

    try:
        recurrence_lower = recurrence_type.lower().strip()

        # Check for named recurrence patterns first (monthly, quarterly, etc.)
        named_patterns = {
            "weekly": (1, "week"),
            "biweekly": (2, "week"),
            "bi-weekly": (2, "week"),
            "fortnightly": (2, "week"),
            "monthly": (1, "month"),
            "quarterly": (3, "month"),
            "semi-annually": (6, "month"),
            "semiannually": (6, "month"),
            "semi-annual": (6, "month"),
            "annually": (1, "year"),
            "yearly": (1, "year"),
            "annual": (1, "year"),
        }

        if recurrence_lower in named_patterns:
            amount, unit = named_patterns[recurrence_lower]
            logger.debug(f"Matched named pattern '{recurrence_lower}': {amount} {unit}")
        else:
            # Parse numeric recurrence string (e.g., "Every 1 month", "2 weeks", "3 months")
            # Make "every" optional to support both "Every 3 months" and "3 months" formats
            pattern = r"(?:every\s+)?(\d+)\s+(week|weeks|month|months|year|years)"
            match = re.search(pattern, recurrence_lower)

            if not match:
                logger.warning(f"Could not parse recurrence type: {recurrence_type}")
                return None

            amount = int(match.group(1))
            unit = match.group(2)

        # Normalize unit to singular
        if unit.endswith('s'):
            unit = unit[:-1]

        # Calculate next occurrence
        elif unit == "week":
            return start_date + timedelta(weeks=amount)
        elif unit == "month":
            # Add months by incrementing month field
            month = start_date.month + amount
            year = start_date.year
            while month > 12:
                month -= 12
                year += 1
            # Handle day overflow (e.g., Jan 31 + 1 month = Feb 28/29)
            try:
                return start_date.replace(year=year, month=month)
            except ValueError:
                # Day doesn't exist in target month, use last day of month
                if month == 2:
                    # February - check for leap year
                    day = 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
                elif month in [4, 6, 9, 11]:
                    day = 30
                else:
                    day = 31
                return start_date.replace(year=year, month=month, day=day)
        elif unit == "year":
            return start_date.replace(year=start_date.year + amount)
        else:
            logger.warning(f"Unknown recurrence unit: {unit}")
            return None

    except Exception as e:
        logger.error(f"Error computing next due date: {str(e)}")
        return None
class MaintenanceTaskCreate(BaseModel):
    building_id: str
    task_title: str
    task_description: str
    location: str
    scheduled_date: datetime
    assigned_to: Optional[str] = None
    category: Optional[str] = ""
    priority: Optional[str] = ""
    task_type: Optional[str] = "new"
    maintenance_type: Optional[str] = None  # internal, external, ipm, epm
    scheduled_time_slot: Optional[str] = None
    estimated_duration: Optional[int] = Field(default=None, ge=1)  # At least 1 minute
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
    
    # External maintenance contractor fields (canonical names)
    contact_name: Optional[str] = None
    email: Optional[str] = None
    contact_number: Optional[str] = None
    service_category: Optional[str] = None
    department: Optional[str] = None
    
    # Additional frontend compatibility fields
    task_code: Optional[str] = None
    formatted_id: Optional[str] = None
    assigned_staff_name: Optional[str] = None
    
    # Assessment and tracking fields
    assessment_received: Optional[str] = None
    assessment_date: Optional[datetime] = None
    logged_by: Optional[str] = None
    logged_date: Optional[str] = None
    assessment: Optional[str] = None
    recommendation: Optional[str] = None
    admin_notification: Optional[str] = None
    
    # Notes for admins to attach to a task
    admin_notes: Optional[str] = None
    
    # Date fields that might come from frontend
    date_created: Optional[str] = None
    created_by: Optional[str] = None
    start_date: Optional[str] = None
    next_due_date: Optional[str] = None
    service_window_start: Optional[str] = None
    service_window_end: Optional[str] = None
    service_date_actual: Optional[str] = None

    # Inventory request tracking
    inventory_request_ids: Optional[List[str]] = []


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
    estimated_duration: Optional[int] = Field(default=None, ge=1)  # At least 1 minute
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
    
    # External maintenance contractor fields (canonical names)
    contact_name: Optional[str] = None
    email: Optional[str] = None
    contact_number: Optional[str] = None
    service_category: Optional[str] = None
    department: Optional[str] = None
    
    # Assessment and tracking fields
    assessment_received: Optional[str] = None
    assessment_date: Optional[datetime] = None
    logged_by: Optional[str] = None
    logged_date: Optional[str] = None
    assessment: Optional[str] = None
    recommendation: Optional[str] = None
    admin_notification: Optional[str] = None
    # Admin-editable notes
    admin_notes: Optional[str] = None
    
    # Date fields
    service_date_actual: Optional[str] = None
    assessment_notes: Optional[str] = None
    recommendations: Optional[str] = None

    # Inventory request tracking
    inventory_request_ids: Optional[List[str]] = None


class MaintenanceTaskAssign(BaseModel):
    """Model for assigning staff to a maintenance task"""
    staff_id: str
    scheduled_date: Optional[datetime] = None
    notes: Optional[str] = None


class SubmitAssessmentRequest(BaseModel):
    """Model for staff to submit assessment for a maintenance task"""
    assessment: str
    assessment_notes: Optional[str] = None


async def _serialize_task(task: MaintenanceTask) -> Dict[str, Any]:
    data = task.dict()

    # Compute next_occurrence based on recurrence type and dates
    recurrence_type = data.get("recurrence_type")
    if recurrence_type and recurrence_type.lower() not in ["none", "n/a", ""]:
        # Determine base date for calculation
        # If task is completed, calculate from completed_at; otherwise use scheduled_date
        base_date = None
        if data.get("completed_at"):
            base_date = data.get("completed_at")
        elif data.get("scheduled_date"):
            base_date = data.get("scheduled_date")

        if base_date:
            # Compute next occurrence
            next_due = _compute_next_due_date(base_date, recurrence_type)
            if next_due:
                data["next_occurrence"] = next_due
                logger.debug(
                    f"Computed next_occurrence for task {data.get('id')}: {next_due} "
                    f"from base_date {base_date} with recurrence {recurrence_type}"
                )

    # Serialize datetime fields - convert to local time for frontend display
    for key in (
        "scheduled_date",
        "started_at",
        "completed_at",
        "next_occurrence",
        "assessment_date",
        "created_at",
        "updated_at",
    ):
        value = data.get(key)
        if isinstance(value, datetime):
            # Convert to local time for frontend display
            local_dt = _convert_to_local_time(value)
            data[key] = local_dt.isoformat()

    # Ensure ID fields
    data["formatted_id"] = data.get("formatted_id") or data.get("id")

    # Ensure title fields
    data["task_title"] = data.get("task_title") or data.get("title") or "Maintenance Task"
    data["title"] = data.get("task_title")

    # Set next_occurence (with typo for backwards compatibility) and next_due_date
    next_occurrence = data.get("next_occurrence")
    data["next_occurence"] = next_occurrence
    if next_occurrence:
        # If next_occurrence is a datetime object (before serialization), format it
        if isinstance(next_occurrence, datetime):
            local_date = _convert_to_local_time(next_occurrence)
            data["next_due_date"] = local_date.strftime("%Y-%m-%d")
        # If it's already a string (ISO format), parse and format it
        elif isinstance(next_occurrence, str):
            try:
                parsed_date = datetime.fromisoformat(next_occurrence.replace('Z', '+00:00'))
                local_date = _convert_to_local_time(parsed_date)
                data["next_due_date"] = local_date.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                data["next_due_date"] = None
    else:
        data["next_due_date"] = None
    
    # Ensure staff assignment fields
    data["assigned_staff"] = data.get("assigned_to")
    data["assigned_staff_id"] = data.get("assigned_to")
    
    data["created_by"] = await UserIdService.get_user_full_name(data.get("created_by")) if data.get("created_by") else "System"
    
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
    data["inventory_request_ids"] = data.get("inventory_request_ids") or []

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
        serialized = [await _serialize_task(task) for task in tasks]
        logger.info("[DEBUG] Returning %d maintenance tasks", len(serialized))
        return serialized

    except ValueError as exc:
        logger.error("Error getting maintenance tasks: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Error getting maintenance tasks: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get maintenance tasks: {exc}")


@router.get("/assigned-to-me")
async def get_my_assigned_tasks(
    building_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Get maintenance tasks assigned to the current user (whole task or checklist items)."""
    try:
        user_id = current_user.get("uid")
        current_user = await user_id_service.get_user_profile(user_id)
        print(current_user)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found")

        filters: Dict[str, Any] = {}
        if building_id:
            filters["building_id"] = building_id
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category

        # Get all tasks matching the filters
        all_tasks = await maintenance_task_service.list_tasks(filters)
        
        print("ALL TASKS:", all_tasks)

        # Filter to only include:
        # 1. Tasks where assigned_to == user_id
        # 2. Tasks with checklist items where any item.assigned_to == user_id
        assigned_tasks = []
        for task in all_tasks:
            # Check if whole task is assigned to user
            if task.assigned_to == f"{current_user.first_name} {current_user.last_name}" or task.assigned_to == user_id or task.assigned_staff_name == f"{current_user.first_name} {current_user.last_name}":
                assigned_tasks.append(task)
                continue
            
            # Check if any checklist item is assigned to user
            checklist = task.checklist_completed or []
            has_assigned_item = any(
                item.get("assigned_to") == current_user.staff_id
                for item in checklist
            )

            if has_assigned_item:
                assigned_tasks.append(task)

        serialized = [await _serialize_task(task) for task in assigned_tasks]
        logger.info("[DEBUG] Returning %d assigned tasks for user %s", len(serialized), user_id)
        return serialized

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error getting assigned tasks: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Error getting assigned tasks: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get assigned tasks: {exc}")


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

        return await _serialize_task(task)

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

        # Convert to dict
        task_dict = task_data.dict(exclude_unset=True)

        # Auto-compute next_occurrence (next_due_date) if recurrence and scheduled_date are provided
        scheduled_date = task_dict.get("scheduled_date")
        recurrence_type = task_dict.get("recurrence_type")

        if scheduled_date and recurrence_type:
            next_due = _compute_next_due_date(scheduled_date, recurrence_type)
            if next_due:
                task_dict["next_occurrence"] = next_due
                task_dict["next_due_date"] = next_due.strftime("%Y-%m-%d")
                logger.info(f"Auto-computed next_occurrence: {next_due} from recurrence: {recurrence_type}")

        task = await maintenance_task_service.create_task(
            current_user.get("uid"),
            task_dict,
        )

        serialized_task = await _serialize_task(task)

        # If the task contains inventory_request_ids, include full request documents
        req_ids = serialized_task.get("inventory_request_ids") or getattr(task, "inventory_request_ids", None) or []
        inventory_requests = []
        if req_ids:
            for rid in req_ids:
                try:
                    s, req_doc, e = await maintenance_task_service.db.get_document(COLLECTIONS["inventory_requests"], rid)
                    if s and req_doc:
                        inventory_requests.append(req_doc)
                except Exception:
                    logger.warning("Failed to fetch inventory request %s for serialization", rid)

        if inventory_requests:
            serialized_task["inventory_requests"] = inventory_requests

        # Send notification if task is created with assigned_to (staff assignment)
        if task_dict.get("assigned_to"):
            try:
                task_dict_for_notif = task.dict() if hasattr(task, 'dict') else task_dict
                
                maintenance_type = task_dict_for_notif.get("maintenance_type", "internal") if isinstance(task_dict_for_notif, dict) else getattr(task, "maintenance_type", "internal")
                print(f"\n[MAINTENANCE NOTIFY - POST] Maintenance type for task {task.id}: {maintenance_type}")
                logger.info(f"[POST ENDPOINT] Maintenance type for task {task.id}: {maintenance_type}")
                
                if maintenance_type == "internal":
                    if isinstance(task_dict_for_notif, dict):
                        task_title = task_dict_for_notif.get("task_title", "Maintenance Task")
                        location = task_dict_for_notif.get("location", "Unknown Location")
                        scheduled = task_dict_for_notif.get("scheduled_date")
                    else:
                        task_title = getattr(task, "task_title", "Maintenance Task")
                        location = getattr(task, "location", "Unknown Location")
                        scheduled = getattr(task, "scheduled_date", None)
                    
                    staff_id_identifier = task_dict.get("assigned_to")
                    print(f"[MAINTENANCE NOTIFY - POST] staff_id_identifier: {staff_id_identifier}")
                    
                    # Convert staff_id to Firebase UID
                    user_profile = await user_id_service.get_staff_profile_from_staff_id(staff_id_identifier)
                    if not user_profile:
                        print(f"[MAINTENANCE NOTIFY - POST] ERROR: Could not find user profile for staff_id {staff_id_identifier}")
                        logger.error(f"Could not find user profile for staff_id {staff_id_identifier}")
                    else:
                        firebase_uid = user_profile.id
                        print(f"[MAINTENANCE NOTIFY - POST] Converted staff_id {staff_id_identifier} to Firebase UID {firebase_uid}")
                        print(f"[MAINTENANCE NOTIFY - POST] Preparing to notify staff {firebase_uid}")
                        print(f"[MAINTENANCE NOTIFY - POST] Task title: {task_title}")
                        print(f"[MAINTENANCE NOTIFY - POST] Location: {location}")
                        print(f"[MAINTENANCE NOTIFY - POST] Scheduled: {scheduled} (type: {type(scheduled).__name__})")
                        
                        logger.info(f"[POST ENDPOINT] Preparing to notify staff {firebase_uid} about newly created maintenance task")
                        logger.info(f"  Task title: {task_title}")
                        logger.info(f"  Location: {location}")
                        logger.info(f"  Scheduled: {scheduled} (type: {type(scheduled).__name__})")
                        
                        from ..services.notification_manager import notification_manager
                        print(f"[MAINTENANCE NOTIFY - POST] Calling notification_manager.notify_maintenance_task_assigned...")
                        notification_result = await notification_manager.notify_maintenance_task_assigned(
                            task_id=task.id,
                            staff_id=firebase_uid,
                            task_title=task_title,
                            location=location,
                            scheduled_date=scheduled,
                            assigned_by=current_user.get("uid")
                        )
                        
                        print(f"[MAINTENANCE NOTIFY - POST] Notification result: {notification_result}")
                        if notification_result:
                            print(f"[MAINTENANCE NOTIFY - POST] ✓ Successfully sent maintenance task notification to Firebase UID {firebase_uid}")
                            logger.info(f"✓ Successfully sent maintenance task notification to Firebase UID {firebase_uid}")
                        else:
                            print(f"[MAINTENANCE NOTIFY - POST] ✗ Notification returned False for Firebase UID {firebase_uid}")
                            logger.warning(f"✗ Notification returned False for Firebase UID {firebase_uid}")
                else:
                    print(f"[MAINTENANCE NOTIFY - POST] Skipping notification - maintenance type is '{maintenance_type}', not 'internal'")
                    logger.info(f"Skipping notification - maintenance type is '{maintenance_type}', not 'internal'")
                    
            except Exception as notif_error:
                print(f"[MAINTENANCE NOTIFY - POST] ERROR: {str(notif_error)}")
                import traceback
                print(traceback.format_exc())
                logger.error(f"Error sending maintenance task notification: {str(notif_error)}", exc_info=True)

        return {
            "success": True,
            "message": "Maintenance task created successfully",
            "task": serialized_task,
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
    print(f"\n[PUT ENDPOINT CALLED] task_id={task_id}, updates={updates.dict(exclude_unset=True)}")
    update_dict_raw = updates.dict(exclude_unset=True)
    logger.info(f"[PUT ENDPOINT] Received update for task {task_id}")
    logger.info(f"[PUT ENDPOINT] Fields being updated: {list(update_dict_raw.keys())}")
    for key, value in update_dict_raw.items():
        logger.debug(f"[PUT ENDPOINT]   {key}: {value}")
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # Convert to dict
        update_dict = updates.dict(exclude_unset=True)

        # Auto-compute next_occurrence if recurrence_type or scheduled_date is being updated
        if "recurrence_type" in update_dict or "scheduled_date" in update_dict:
            # Get current task to access existing values
            current_task = await maintenance_task_service.get_task(task_id)
            if not current_task:
                raise HTTPException(status_code=404, detail="Maintenance task not found")

            # Use updated values if provided, otherwise use existing values
            scheduled_date = update_dict.get("scheduled_date") or current_task.scheduled_date
            recurrence_type = update_dict.get("recurrence_type") or current_task.recurrence_type

            if scheduled_date and recurrence_type:
                next_due = _compute_next_due_date(scheduled_date, recurrence_type)
                if next_due:
                    update_dict["next_occurrence"] = next_due
                    update_dict["next_due_date"] = next_due.strftime("%Y-%m-%d")
                    logger.info(f"Auto-computed next_occurrence: {next_due} for task {task_id} from recurrence: {recurrence_type}")
                else:
                    # No recurrence or could not parse, clear next_occurrence
                    update_dict["next_occurrence"] = None
                    update_dict["next_due_date"] = None
                    logger.info(f"Cleared next_occurrence for task {task_id} (no recurrence)")

        updated = await maintenance_task_service.update_task(
            task_id,
            update_dict,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        # Send notification if this is an internal maintenance task being assigned to staff
        if "assigned_to" in update_dict and update_dict["assigned_to"]:
            try:
                task_dict = updated.dict() if hasattr(updated, 'dict') else updated
                
                maintenance_type = task_dict.get("maintenance_type", "internal") if isinstance(task_dict, dict) else getattr(updated, "maintenance_type", "internal")
                print(f"\n[MAINTENANCE NOTIFY - PUT] Maintenance type for task {task_id}: {maintenance_type}")
                logger.info(f"[PUT ENDPOINT] Maintenance type for task {task_id}: {maintenance_type}")
                
                if maintenance_type == "internal":
                    if isinstance(task_dict, dict):
                        task_title = task_dict.get("task_title", "Maintenance Task")
                        location = task_dict.get("location", "Unknown Location")
                        scheduled = task_dict.get("scheduled_date")
                    else:
                        task_title = getattr(updated, "task_title", "Maintenance Task")
                        location = getattr(updated, "location", "Unknown Location")
                        scheduled = getattr(updated, "scheduled_date", None)
                    
                    staff_id_identifier = update_dict["assigned_to"]
                    print(f"[MAINTENANCE NOTIFY - PUT] staff_id_identifier: {staff_id_identifier}")
                    
                    # Convert staff_id to Firebase UID
                    user_profile = await user_id_service.get_staff_profile_from_staff_id(staff_id_identifier)
                    if not user_profile:
                        print(f"[MAINTENANCE NOTIFY - PUT] ERROR: Could not find user profile for staff_id {staff_id_identifier}")
                        logger.error(f"Could not find user profile for staff_id {staff_id_identifier}")
                    else:
                        firebase_uid = user_profile.id
                        print(f"[MAINTENANCE NOTIFY - PUT] Converted staff_id {staff_id_identifier} to Firebase UID {firebase_uid}")
                        print(f"[MAINTENANCE NOTIFY - PUT] Preparing to notify staff {firebase_uid}")
                        print(f"[MAINTENANCE NOTIFY - PUT] Task title: {task_title}")
                        print(f"[MAINTENANCE NOTIFY - PUT] Location: {location}")
                        print(f"[MAINTENANCE NOTIFY - PUT] Scheduled: {scheduled} (type: {type(scheduled).__name__})")
                        
                        logger.info(f"[PUT ENDPOINT] Preparing to notify staff {firebase_uid} about maintenance task")
                        logger.info(f"  Task title: {task_title}")
                        logger.info(f"  Location: {location}")
                        logger.info(f"  Scheduled: {scheduled} (type: {type(scheduled).__name__})")
                        
                        from ..services.notification_manager import notification_manager
                        print(f"[MAINTENANCE NOTIFY - PUT] Calling notification_manager.notify_maintenance_task_assigned...")
                        notification_result = await notification_manager.notify_maintenance_task_assigned(
                            task_id=task_id,
                            staff_id=firebase_uid,
                            task_title=task_title,
                            location=location,
                            scheduled_date=scheduled,
                            assigned_by=current_user.get("uid")
                        )
                        
                        print(f"[MAINTENANCE NOTIFY - PUT] Notification result: {notification_result}")
                        if notification_result:
                            print(f"[MAINTENANCE NOTIFY - PUT] ✓ Successfully sent maintenance task notification to Firebase UID {firebase_uid}")
                            logger.info(f"✓ Successfully sent maintenance task notification to Firebase UID {firebase_uid}")
                        else:
                            print(f"[MAINTENANCE NOTIFY - PUT] ✗ Notification returned False for Firebase UID {firebase_uid}")
                            logger.warning(f"✗ Notification returned False for Firebase UID {firebase_uid}")
                else:
                    print(f"[MAINTENANCE NOTIFY - PUT] Skipping notification - maintenance type is '{maintenance_type}', not 'internal'")
                    logger.info(f"Skipping notification - maintenance type is '{maintenance_type}', not 'internal'")
                    
            except Exception as notif_error:
                print(f"[MAINTENANCE NOTIFY - PUT] ERROR: {str(notif_error)}")
                import traceback
                print(traceback.format_exc())
                logger.error(f"Error sending maintenance task notification: {str(notif_error)}", exc_info=True)

        # Send notification to admins when assessment is submitted by staff
        # Check for either assessment_received field being set OR assessment content being provided
        has_assessment_received = "assessment_received" in update_dict and update_dict["assessment_received"]
        has_assessment_content = "assessment" in update_dict and update_dict["assessment"]
        
        logger.info(f"[PUT ENDPOINT] Assessment check - has_assessment_received={has_assessment_received}, has_assessment_content={has_assessment_content}")
        logger.info(f"[PUT ENDPOINT] assessment_received value: {update_dict.get('assessment_received', 'NOT_PRESENT')}")
        logger.info(f"[PUT ENDPOINT] assessment value: {update_dict.get('assessment', 'NOT_PRESENT')}")
        
        if has_assessment_received or has_assessment_content:
            try:
                logger.info(f"[PUT ENDPOINT] Assessment submitted for task {task_id}")
                task_title = getattr(updated, "task_title", "Maintenance Task")
                location = getattr(updated, "location", "Unknown Location")
                assessment = update_dict.get("assessment") or getattr(updated, "assessment", None)
                staff_name = current_user.get("name") or current_user.get("uid")
                
                logger.info(f"[PUT ENDPOINT] Assessment submitted for '{task_title}' at {location}")
                logger.info(f"[PUT ENDPOINT] Submitted by: {staff_name}")
                
                # Get all admins to notify
                admin_users = await notification_manager._get_users_by_role("admin")
                logger.info(f"[PUT ENDPOINT] Found {len(admin_users)} admin(s) to notify about assessment")
                
                for admin in admin_users:
                    try:
                        admin_id = admin.get("id") or admin.get("_doc_id")
                        if not admin_id:
                            continue
                        
                        logger.info(f"[PUT ENDPOINT] Creating assessment notification for admin {admin_id}")
                        success, notif_id, error = await notification_manager.create_notification(
                            notification_type=NotificationType.MAINTENANCE_COMPLETED,
                            recipient_id=admin_id,
                            title="Maintenance Assessment Submitted",
                            message=f"Assessment submitted for '{task_title}' at {location} by {staff_name}",
                            sender_id=current_user.get("uid"),
                            related_entity_type="maintenance_task",
                            related_entity_id=task_id,
                            channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                            action_url=f"/admin/maintenance/{task_id}",
                            action_label="Review Assessment",
                            priority=NotificationPriority.HIGH,
                            requires_action=True
                        )
                        if success:
                            logger.info(f"[PUT ENDPOINT] Assessment notification {notif_id} sent to admin {admin_id}")
                    except Exception as admin_error:
                        logger.warning(f"[PUT ENDPOINT] Failed to notify admin {admin.get('id')}: {str(admin_error)}")
            except Exception as assessment_error:
                logger.error(f"[PUT ENDPOINT] Error sending assessment notification for task {task_id}: {str(assessment_error)}", exc_info=True)

        return {
            "success": True,
            "message": "Maintenance task updated successfully",
            "task": await _serialize_task(updated),
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


@router.patch("/{task_id}/submit-assessment")
async def submit_assessment(
    task_id: str,
    request: SubmitAssessmentRequest,
    current_user: dict = Depends(get_current_user),
):
    """Submit assessment for a maintenance task (Staff or Admin)."""
    print(f"\n[SUBMIT ASSESSMENT DEBUG] current_user={current_user}")
    print(f"[SUBMIT ASSESSMENT DEBUG] current_user type={type(current_user)}")
    
    if not current_user:
        logger.error(f"[SUBMIT ASSESSMENT] 403 - No current_user")
        raise HTTPException(status_code=403, detail="Not authenticated")
    
    user_role = current_user.get("role") if isinstance(current_user, dict) else None
    user_uid = current_user.get("uid") if isinstance(current_user, dict) else None
    
    print(f"[SUBMIT ASSESSMENT DEBUG] user_role={user_role}, user_uid={user_uid}")
    logger.info(f"[SUBMIT ASSESSMENT] Received from user {user_uid} with role: {user_role}")
    logger.info(f"[SUBMIT ASSESSMENT] Assessment data: {request.dict()}")
    
    try:
        if user_role not in {"admin", "staff"}:
            logger.error(f"[SUBMIT ASSESSMENT] 403 - Role {user_role} not in allowed roles")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Get the task
        task = await maintenance_task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Maintenance task not found")
        
        # Verify staff is assigned to this task (admins can submit for any task)
        if user_role == "staff":
            # Get staff's profile to get their staff_id
            try:
                staff_profile = await user_id_service.get_user_profile(user_uid)
                staff_id = staff_profile.staff_id if staff_profile else None
            except:
                staff_id = None
            
            print(f"[SUBMIT ASSESSMENT DEBUG] task.assigned_to={task.assigned_to}")
            print(f"[SUBMIT ASSESSMENT DEBUG] current_user uid={user_uid}")
            print(f"[SUBMIT ASSESSMENT DEBUG] staff_id from profile={staff_id}")
            print(f"[SUBMIT ASSESSMENT DEBUG] Comparing: '{task.assigned_to}' vs '{staff_id}'")
            
            if task.assigned_to != staff_id and task.assigned_to != user_uid:
                logger.error(f"[SUBMIT ASSESSMENT] 403 - Staff user {user_uid} (staff_id={staff_id}) not assigned to task {task_id}")
                print(f"[SUBMIT ASSESSMENT DEBUG] Assignment check FAILED")
                raise HTTPException(status_code=403, detail="You can only submit assessment for tasks assigned to you")
        
        # Prepare update data
        update_dict = {
            "assessment_received": True,
            "assessment_date": datetime.utcnow(),
            "assessment": request.assessment,
            "assessment_notes": request.assessment_notes,
            "updated_at": datetime.utcnow(),
        }
        
        logger.info(f"[SUBMIT ASSESSMENT] Updating task with: {update_dict}")
        
        # Update the task
        updated = await maintenance_task_service.update_task(task_id, update_dict)
        
        # If update_task returns None, fetch the updated task
        if not updated:
            updated = await maintenance_task_service.get_task(task_id)
        
        logger.info(f"[SUBMIT ASSESSMENT] Task updated successfully")
        
        # Send notification to admins
        try:
            logger.info(f"[SUBMIT ASSESSMENT] Getting admins to notify")
            admin_users = await notification_manager._get_users_by_role("admin")
            logger.info(f"[SUBMIT ASSESSMENT] Found {len(admin_users)} admin(s)")
            
            # Use task object (not updated) since it has all the data
            task_title = task.task_title or "Maintenance Task"
            location = task.location or "Unknown Location"
            staff_name = current_user.get("name") or current_user.get("uid")
            assessment = update_dict.get("assessment", "")
            
            print(f"[SUBMIT ASSESSMENT DEBUG] Notification - task_title={task_title}, location={location}, staff_name={staff_name}")
            
            for admin in admin_users:
                try:
                    admin_id = admin.get("id") or admin.get("_doc_id")
                    if not admin_id:
                        logger.warning(f"[SUBMIT ASSESSMENT] Admin has no id field: {admin}")
                        continue
                    
                    logger.info(f"[SUBMIT ASSESSMENT] Sending notification to admin {admin_id}")
                    success, notif_id, error = await notification_manager.create_notification(
                        notification_type=NotificationType.MAINTENANCE_COMPLETED,
                        recipient_id=admin_id,
                        title="Maintenance Task Completed",
                        message=f"Maintenance task '{task_title}' at {location} has been completed by {staff_name}",
                        sender_id=current_user.get("uid"),
                        related_entity_type="maintenance_task",
                        related_entity_id=task_id,
                        channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH, NotificationChannel.EMAIL],
                        action_url=f"/admin/maintenance/{task_id}",
                        action_label="Review Assessment",
                        priority=NotificationPriority.HIGH,
                        requires_action=True
                    )
                    if success:
                        logger.info(f"[SUBMIT ASSESSMENT] Notification {notif_id} sent to admin {admin_id}")
                    else:
                        logger.warning(f"[SUBMIT ASSESSMENT] Failed to send notification to admin {admin_id}: {error}")
                except Exception as admin_error:
                    logger.error(f"[SUBMIT ASSESSMENT] Error notifying admin {admin.get('id')}: {str(admin_error)}", exc_info=True)
        except Exception as notif_error:
            logger.error(f"[SUBMIT ASSESSMENT] Error in notification process: {str(notif_error)}", exc_info=True)
        
        return {
            "success": True,
            "message": "Assessment submitted successfully",
            "task": await _serialize_task(updated) if updated else {"id": task_id, "message": "Task updated successfully"},
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[SUBMIT ASSESSMENT] Error submitting assessment for task {task_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit assessment: {str(exc)}")


class ChecklistItemUpdate(BaseModel):
    """Model for updating a single checklist item."""
    item_id: str
    completed: bool
    task: Optional[str] = None


class InventoryRequestReceived(BaseModel):
    condition: Optional[str] = "ok"
    notes: Optional[str] = None


class ChecklistUpdate(BaseModel):
    """Model for updating the entire checklist."""
    checklist_completed: List[Dict[str, Any]]


@router.post("/tasks/{task_id}/assign")
async def assign_staff_to_maintenance_task(
    task_id: str,
    assignment_data: MaintenanceTaskAssign,
    current_user: dict = Depends(get_current_user),
):
    """Assign staff to a maintenance task."""
    print(f"\n[ASSIGN ENDPOINT CALLED] task_id={task_id}, staff_id={assignment_data.staff_id}")
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        staff_id_identifier = assignment_data.staff_id
        if not staff_id_identifier:
            raise HTTPException(status_code=400, detail="staff_id is required")

        # Get scheduled date if provided
        scheduled_date = assignment_data.scheduled_date
        notes = assignment_data.notes

        # Build update payload
        updates = {
            "assigned_to": staff_id_identifier,
            "status": "assigned",
        }

        if scheduled_date:
            updates["scheduled_date"] = scheduled_date

        if notes:
            updates["notes"] = notes

        # Update the task
        updated_task = await maintenance_task_service.update_task(task_id, updates)

        if not updated_task:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        # Send notification to staff if this is an internal maintenance task
        try:
            # Convert MaintenanceTask object to dict for easier access
            task_dict = updated_task.dict() if hasattr(updated_task, 'dict') else updated_task
            
            maintenance_type = task_dict.get("maintenance_type", "internal") if isinstance(task_dict, dict) else getattr(updated_task, "maintenance_type", "internal")
            print(f"\n[MAINTENANCE NOTIFY] Maintenance type for task {task_id}: {maintenance_type}")
            logger.info(f"Maintenance type for task {task_id}: {maintenance_type}")
            
            if maintenance_type == "internal":
                if isinstance(task_dict, dict):
                    task_title = task_dict.get("task_title", "Maintenance Task")
                    location = task_dict.get("location", "Unknown Location")
                    scheduled = task_dict.get("scheduled_date")
                else:
                    task_title = getattr(updated_task, "task_title", "Maintenance Task")
                    location = getattr(updated_task, "location", "Unknown Location")
                    scheduled = getattr(updated_task, "scheduled_date", None)
                
                print(f"[MAINTENANCE NOTIFY] staff_id_identifier: {staff_id_identifier}")
                
                # Convert staff_id to Firebase UID
                user_profile = await user_id_service.get_staff_profile_from_staff_id(staff_id_identifier)
                if not user_profile:
                    print(f"[MAINTENANCE NOTIFY] ERROR: Could not find user profile for staff_id {staff_id_identifier}")
                    logger.error(f"Could not find user profile for staff_id {staff_id_identifier}")
                else:
                    firebase_uid = user_profile.id
                    print(f"[MAINTENANCE NOTIFY] Converted staff_id {staff_id_identifier} to Firebase UID {firebase_uid}")
                    print(f"[MAINTENANCE NOTIFY] Preparing to notify staff {firebase_uid}")
                    print(f"[MAINTENANCE NOTIFY] Task title: {task_title}")
                    print(f"[MAINTENANCE NOTIFY] Location: {location}")
                    print(f"[MAINTENANCE NOTIFY] Scheduled: {scheduled} (type: {type(scheduled).__name__})")
                    
                    logger.info(f"Preparing to notify staff {firebase_uid} about maintenance task")
                    logger.info(f"  Task title: {task_title}")
                    logger.info(f"  Location: {location}")
                    logger.info(f"  Scheduled: {scheduled} (type: {type(scheduled).__name__})")
                    
                    from ..services.notification_manager import notification_manager
                    print(f"[MAINTENANCE NOTIFY] Calling notification_manager.notify_maintenance_task_assigned...")
                    notification_result = await notification_manager.notify_maintenance_task_assigned(
                        task_id=task_id,
                        staff_id=firebase_uid,
                        task_title=task_title,
                        location=location,
                        scheduled_date=scheduled,
                        assigned_by=current_user.get("uid")
                    )
                    
                    print(f"[MAINTENANCE NOTIFY] Notification result: {notification_result}")
                    if notification_result:
                        print(f"[MAINTENANCE NOTIFY] ✓ Successfully sent maintenance task notification to Firebase UID {firebase_uid}")
                        logger.info(f"✓ Successfully sent maintenance task notification to Firebase UID {firebase_uid}")
                    else:
                        print(f"[MAINTENANCE NOTIFY] ✗ Notification returned False for Firebase UID {firebase_uid}")
                        logger.warning(f"✗ Notification returned False for Firebase UID {firebase_uid}")
            else:
                print(f"[MAINTENANCE NOTIFY] Skipping notification - maintenance type is '{maintenance_type}', not 'internal'")
                logger.info(f"Skipping notification - maintenance type is '{maintenance_type}', not 'internal'")
                
        except Exception as notif_error:
            print(f"[MAINTENANCE NOTIFY] ERROR: {str(notif_error)}")
            import traceback
            print(traceback.format_exc())
            logger.error(f"Error sending maintenance task notification: {str(notif_error)}", exc_info=True)
            # Don't fail the request if notification fails

        return {
            "success": True,
            "message": "Staff assigned successfully",
            "task": await _serialize_task(updated_task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error assigning staff to task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error assigning staff to task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to assign staff: {exc}")


@router.post("/inventory_requests/{request_id}/received")
async def mark_inventory_request_received(
    request_id: str,
    payload: InventoryRequestReceived,
    current_user: dict = Depends(get_current_user),
):
    """Mark an inventory request as received for a maintenance task.

    Only the staff assigned to the related maintenance task or an admin may perform this action.
    If the item is broken/damaged, the server will create a replacement request and attach it to the task.
    """
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        performer_id = current_user.get("uid")

        result = await maintenance_task_service.mark_inventory_request_received(
            request_id, performer_id, condition=payload.condition, notes=payload.notes
        )

        return {"success": True, "message": "Inventory request updated", "result": result}

    except ValueError as ve:
        logger.error("Error marking inventory request received %s: %s", request_id, ve)
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error marking inventory request received %s: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to mark inventory request received: {exc}")


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
        
        logger.info(f"Checklist update for task {task_id}: {completed_items}/{total_items} items completed")
        
        # Auto-update status based on checklist completion
        if total_items > 0:
            if completed_items == total_items:
                # All items completed
                update_data["status"] = "completed"
                update_data["completed_at"] = datetime.now()
                logger.info(f"All checklist items completed for task {task_id}, setting status to 'completed'")
            elif completed_items > 0:
                # Some items completed - set to in_progress
                update_data["status"] = "in_progress"
                logger.info(f"Checklist progress for task {task_id}: {completed_items}/{total_items} items completed, setting status to 'in_progress'")

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
            "task": await _serialize_task(updated_task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error updating checklist for task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error updating checklist for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to update checklist: {exc}")


@router.post("/{task_id}/checklist/{item_id}/assign")
async def assign_checklist_item(
    task_id: str,
    item_id: str,
    assignment_data: dict,
    current_user: dict = Depends(get_current_user),
):
    """Assign a staff member to a specific checklist item."""
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        staff_id = assignment_data.get("staff_id") or assignment_data.get("assigned_to")
        if not staff_id:
            raise HTTPException(status_code=400, detail="staff_id is required")

        # Get the current task
        task = await maintenance_task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Maintenance task not found")

        # Get checklist
        checklist = task.checklist_completed or []

        # Find and update the specific item
        item_found = False
        for item in checklist:
            if item.get("id") == item_id:
                item["assigned_to"] = staff_id
                item_found = True
                break

        if not item_found:
            raise HTTPException(status_code=404, detail=f"Checklist item {item_id} not found")

        # Update the task with modified checklist
        updated_task = await maintenance_task_service.update_task(
            task_id,
            {"checklist_completed": checklist}
        )

        return {
            "success": True,
            "message": "Checklist item assigned successfully",
            "task": await _serialize_task(updated_task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error assigning checklist item %s for task %s: %s", item_id, task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error assigning checklist item %s for task %s: %s", item_id, task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to assign checklist item: {exc}")


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
            "task": await _serialize_task(updated_task),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("Error updating checklist item for task %s: %s", task_id, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error updating checklist item for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to update checklist item: {exc}")


# Special Maintenance Tasks Endpoints

@router.post("/special/initialize")
async def initialize_special_tasks(
):
    """Initialize special maintenance tasks (Fire Safety, Earthquake, Typhoon/Flood)."""
    try:

        results = await special_maintenance_service.initialize_special_tasks(
        )

        return {
            "success": True,
            "message": "Special tasks initialization completed",
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.error("Error initializing special tasks: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to initialize special tasks: {exc}")


@router.get("/special")
async def get_special_tasks(
    current_user: dict = Depends(get_current_user),
):
    """Get all special maintenance tasks assigned to the current user (for staff) or all tasks (for admin)."""
    try:
        # If staff, filter by their user ID; if admin, show all tasks
        user_id = None
        if current_user.get("role") == "staff":
            user_id = current_user.get("uid") or current_user.get("user_id")
            logger.info(f"Fetching special tasks for staff user_id: {user_id}")
        else:
            logger.info("Fetching all special tasks for admin")

        tasks = await special_maintenance_service.get_special_tasks(user_id=user_id)
        serialized = [await _serialize_task(task) for task in tasks]

        logger.info(f"Returning {len(serialized)} special tasks for user role: {current_user.get('role')}")

        return {
            "success": True,
            "tasks": serialized,
        }

    except Exception as exc:  # pragma: no cover
        logger.error("Error getting special tasks: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get special tasks: {exc}")


@router.get("/special/summary")
async def get_special_tasks_summary(
    current_user: dict = Depends(get_current_user),
):
    """Get summary information for all special maintenance tasks."""
    try:
        summaries = {}

        for task_key in ["fire_safety", "earthquake", "typhoon_flood"]:
            summaries[task_key] = await special_maintenance_service.get_special_task_summary(task_key)

        return {
            "success": True,
            "summaries": summaries,
        }

    except Exception as exc:  # pragma: no cover
        logger.error("Error getting special tasks summary: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to get special tasks summary: {exc}")


@router.get("/special/{task_key}")
async def get_special_task(
    task_key: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific special maintenance task by key."""
    try:
        if task_key not in ["fire_safety", "earthquake", "typhoon_flood"]:
            raise HTTPException(status_code=400, detail="Invalid task key")

        task = await special_maintenance_service.get_special_task_by_key(task_key)

        if not task:
            raise HTTPException(status_code=404, detail="Special task not found")

        return {
            "success": True,
            "task": await _serialize_task(task),
        }

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.error("Error getting special task %s: %s", task_key, exc)
        raise HTTPException(status_code=500, detail=f"Failed to get special task: {exc}")


@router.post("/special/{task_key}/reset")
async def reset_special_task(
    task_key: str,
    current_user: dict = Depends(get_current_user),
):
    """Reset a special task's checklist and schedule next occurrence."""
    try:
        if current_user.get("role") not in {"admin", "staff"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        if task_key not in ["fire_safety", "earthquake", "typhoon_flood"]:
            raise HTTPException(status_code=400, detail="Invalid task key")

        task = await special_maintenance_service.reset_special_task_checklist(task_key)

        if not task:
            raise HTTPException(status_code=404, detail="Special task not found")

        return {
            "success": True,
            "message": f"Special task {task_key} reset successfully",
            "task": await _serialize_task(task),
        }

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.error("Error resetting special task %s: %s", task_key, exc)
        raise HTTPException(status_code=500, detail=f"Failed to reset special task: {exc}")
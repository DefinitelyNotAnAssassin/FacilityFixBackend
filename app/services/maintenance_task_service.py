import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.database.collections import COLLECTIONS
from app.database.database_service import DatabaseService, database_service
from app.models.database_models import MaintenanceTask
from app.services.user_id_service import UserIdService

logger = logging.getLogger(__name__)


class MaintenanceTaskService:
    """Service layer for CRUD operations on maintenance tasks."""

    def __init__(self) -> None:
        self.db = database_service or DatabaseService()
        self.user_service = UserIdService()

    async def list_tasks(self, filters: Optional[Dict[str, Any]] = None) -> List[MaintenanceTask]:
        """Return maintenance tasks filtered by the supplied attributes."""
        query_filters = []
        filters = filters or {}

        building_id = filters.get("building_id")
        if building_id:
            query_filters.append(("building_id", "==", building_id))

        status = filters.get("status")
        if status:
            query_filters.append(("status", "==", status))

        assigned_to = filters.get("assigned_to")
        if assigned_to:
            query_filters.append(("assigned_to", "==", assigned_to))

        category = filters.get("category")
        if category:
            query_filters.append(("category", "==", category))

        date_from = filters.get("date_from")
        if date_from:
            query_filters.append(("scheduled_date", ">=", date_from))

        date_to = filters.get("date_to")
        if date_to:
            query_filters.append(("scheduled_date", "<=", date_to))

        success, documents, error = await self.db.query_documents(
            COLLECTIONS["maintenance_tasks"],
            query_filters or None,
        )

        if not success:
            raise ValueError(error or "Failed to fetch maintenance tasks")

        tasks: List[MaintenanceTask] = []
        for raw in documents:
            try:
                normalized = self._normalize_document(raw)
                task = MaintenanceTask(**normalized)
                tasks.append(task)
            except ValueError as ve:
                # Expected validation errors (like system documents)
                logger.debug("Skipping document: %s", ve)
                continue
            except Exception as exc:
                logger.warning("Skipping maintenance task due to validation error: %s", exc)
                logger.debug("Failed document data: %s", raw)
                continue

        # Sort tasks by date with timezone handling
        def get_sort_date(task):
            sort_date = task.scheduled_date or task.created_at
            if sort_date is None:
                return datetime.min.replace(tzinfo=None)
            # Ensure timezone consistency for sorting
            if sort_date.tzinfo is not None:
                return sort_date.replace(tzinfo=None)
            return sort_date
            
        tasks.sort(key=get_sort_date, reverse=True)
        return tasks

    async def get_task(self, task_id: str) -> Optional[MaintenanceTask]:
        """Fetch a single maintenance task by ID."""
        success, document, error = await self.db.get_document(
            COLLECTIONS["maintenance_tasks"],
            task_id,
        )

        if not success or not document:
            if error:
                logger.debug("Failed to get maintenance task %s: %s", task_id, error)
            return None

        normalized = self._normalize_document(document)
        try:
            return MaintenanceTask(**normalized)
        except ValueError as ve:
            logger.debug("Skipping system document %s: %s", task_id, ve)
            return None
        except Exception as exc:
            logger.error("Failed to parse maintenance task %s: %s", task_id, exc)
            logger.debug("Failed document data: %s", document)
            return None

    async def create_task(self, created_by: str, payload: Dict[str, Any]) -> MaintenanceTask:
        """Create a maintenance task from payload and return the stored record."""
        task_id = payload.get("id") or self._generate_task_id()
        now = datetime.utcnow()

        # Extract and normalize maintenance type
        maintenance_type = str(
            payload.get("maintenance_type") 
            or payload.get("maintenanceType") 
            or payload.get("task_type") 
            or "internal"
        ).lower()
        
        # Set task_type based on maintenance_type
        if "external" in maintenance_type or maintenance_type == "epm":
            task_type = "external"
        elif "internal" in maintenance_type or maintenance_type == "ipm":
            task_type = "internal"
        else:
            task_type = payload.get("task_type") or "internal"

        data = {
            **payload,
            "id": task_id,
            "status": payload.get("status") or "scheduled",
            "task_type": task_type,
            "maintenance_type": maintenance_type,
            "recurrence_type": payload.get("recurrence_type") or "none",
            "assigned_to": payload.get("assigned_to") or "unassigned",
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            # Ensure required fields have defaults
            "priority": payload.get("priority") or "medium",
            "category": payload.get("category") or "preventive",
            "location": payload.get("location") or "",
            "building_id": payload.get("building_id") or "default_building",
        }

        normalized = self._normalize_document(data)
        task = MaintenanceTask(**normalized)

        success, _, error = await self.db.create_document(
            COLLECTIONS["maintenance_tasks"],
            self._task_to_dict(task),
            document_id=task.id,
            validate=False,
        )

        if not success:
            raise ValueError(error or "Failed to create maintenance task")

        return task

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> Optional[MaintenanceTask]:
        """Apply updates to an existing maintenance task and return the updated record."""
        update_payload = {**updates}
        if not update_payload:
            return await self.get_task(task_id)

        if "scheduled_date" in update_payload and isinstance(update_payload["scheduled_date"], str):
            try:
                update_payload["scheduled_date"] = datetime.fromisoformat(update_payload["scheduled_date"])
            except ValueError:
                pass

        update_payload["updated_at"] = datetime.utcnow()

        success, error = await self.db.update_document(
            COLLECTIONS["maintenance_tasks"],
            task_id,
            update_payload,
            validate=False,
        )

        if not success:
            raise ValueError(error or "Failed to update maintenance task")

        return await self.get_task(task_id)

    async def delete_task(self, task_id: str) -> bool:
        """Delete a maintenance task."""
        success, error = await self.db.delete_document(
            COLLECTIONS["maintenance_tasks"],
            task_id,
        )

        if not success:
            raise ValueError(error or "Failed to delete maintenance task")

        return True

    def _normalize_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {**document}
        
        # Handle document ID
        doc_id = normalized.get("id") or normalized.get("_doc_id")
        if doc_id:
            normalized["id"] = doc_id
        
        # Skip documents that appear to be counters or system documents
        if doc_id in ['epm_counter', 'ipm_counter']:
            raise ValueError(f"Skipping system document: {doc_id}")
        
        # Handle field name variations and missing required fields
        field_mappings = {
            'taskCode': 'task_code',
            'maintenanceType': 'maintenance_type',
            'equipmentId': 'equipment_id',
            'buildingId': 'building_id',
            'taskTitle': 'task_title',
            'taskDescription': 'task_description',
            'scheduledDate': 'scheduled_date',
            'assignedTo': 'assigned_to',
            'createdBy': 'created_by',
            'createdAt': 'created_at',
            'updatedAt': 'updated_at'
        }
        
        # Apply field mappings
        for old_key, new_key in field_mappings.items():
            if old_key in normalized and new_key not in normalized:
                normalized[new_key] = normalized.pop(old_key)
        
        # Ensure required fields have default values if missing
        required_defaults = {
            'building_id': 'default_building',
            'task_title': 'Maintenance Task',
            'task_description': 'Maintenance task description',
            'location': 'TBD',
            'category': 'preventive',
            'priority': 'medium',
            'status': 'scheduled',
            'task_type': 'scheduled',
            'recurrence_type': 'none',
            'assigned_to': 'unassigned'
        }
        
        for field, default_value in required_defaults.items():
            if field not in normalized or normalized[field] is None or normalized[field] == '':
                normalized[field] = default_value
        
        # Handle scheduled_date specifically
        if 'scheduled_date' not in normalized or normalized['scheduled_date'] is None:
            # Set default to today + 1 day
            normalized['scheduled_date'] = datetime.utcnow() + timedelta(days=1)
        elif isinstance(normalized['scheduled_date'], str):
            try:
                normalized['scheduled_date'] = datetime.fromisoformat(normalized['scheduled_date'])
            except ValueError:
                # If parsing fails, use default
                normalized['scheduled_date'] = datetime.utcnow() + timedelta(days=1)
        
        # Handle datetime fields
        datetime_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'next_occurrence']
        for field in datetime_fields:
            if field in normalized and isinstance(normalized[field], str):
                try:
                    normalized[field] = datetime.fromisoformat(normalized[field])
                except ValueError:
                    if field in ['created_at', 'updated_at']:
                        normalized[field] = datetime.utcnow()
                    else:
                        normalized[field] = None
        
        return normalized

    def _task_to_dict(self, task: MaintenanceTask) -> Dict[str, Any]:
        data = task.dict(exclude_none=True)
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
                data[key] = value
        return data

    def _generate_task_id(self) -> str:
        return f"MT-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


maintenance_task_service = MaintenanceTaskService()

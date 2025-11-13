import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.database.collections import COLLECTIONS
from app.database.database_service import DatabaseService, database_service
from app.models.database_models import MaintenanceTask
from app.services.user_id_service import UserIdService
from app.services.maintenance_id_service import maintenance_id_service
from app.services.inventory_service import inventory_service

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
        """Create a maintenance task from payload and return the stored record.

        Uses the sequential maintenance ID format (MT-YYYY-NNNNN) for task id
        when no explicit `id` or `formatted_id` is provided in the payload.
        """
        # We'll generate task id (sequential) later after we know maintenance_type.
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

        # Allow callers to provide either `id` or `formatted_id`. If neither is
        # provided, generate a sequential maintenance id via maintenance_id_service
        # using the detected maintenance_type so we can produce IPM/EPM prefixes.
        task_id = payload.get("id") or payload.get("formatted_id")
        if not task_id:
            task_id = await maintenance_id_service.generate_maintenance_id(maintenance_type)

        # If the payload includes inventory items (either `parts_used` with
        # inventory references or a list of `inventory_request_ids` which we
        # treat as inventory item ids), validate them and create reservation
        # inventory requests. The created request ids will be stored in the
        # maintenance task as `inventory_request_ids`.
        inventory_input = payload.get("parts_used") or payload.get("inventory_request_ids") or []
        created_request_ids: List[str] = []
        created_request_docs: List[Dict[str, Any]] = []

        # Helper to normalize parts entries
        parts_entries: List[Dict[str, Any]] = []
        if isinstance(inventory_input, list) and inventory_input:
            # parts_used may be list of dicts, inventory_request_ids may be list of ids
            if all(isinstance(i, dict) for i in inventory_input):
                parts_entries = inventory_input  # expected dicts with inventory_id/quantity
            else:
                # list of ids -> treat as existing inventory_request ids when possible
                for iid in inventory_input:
                    if not isinstance(iid, str):
                        continue
                    # Try to fetch existing inventory_request document
                    success, req_doc, err = await self.db.get_document(COLLECTIONS["inventory_requests"], iid)
                    if success and req_doc:
                        created_request_ids.append(iid)
                        created_request_docs.append(req_doc)
                    else:
                        # treat as inventory id to create a reservation
                        parts_entries.append({"inventory_id": iid, "quantity": 1, "reserve": True})

        for entry in parts_entries:
            # If entry already references an existing inventory_request, include it and skip creation
            existing_req_id = entry.get("inventory_request_id") or entry.get("request_id") or entry.get("id")
            if existing_req_id and isinstance(existing_req_id, str):
                success, req_doc, err = await self.db.get_document(COLLECTIONS["inventory_requests"], existing_req_id)
                if success and req_doc:
                    if existing_req_id not in created_request_ids:
                        created_request_ids.append(existing_req_id)
                        created_request_docs.append(req_doc)
                    continue

            # Only create a request if reserve flag is set (frontend sends reserve: true)
            reserve_flag = entry.get("reserve", True)
            if not reserve_flag:
                continue

            inv_id = entry.get("inventory_id") or entry.get("id")
            qty = int(entry.get("quantity") or entry.get("quantity_requested") or 1)
            if not inv_id:
                logger.warning("Skipping parts entry without inventory_id: %s", entry)
                continue

            # Validate inventory item exists
            item_success, item_data, item_error = await inventory_service.get_inventory_item(inv_id)
            if not item_success or not item_data:
                logger.warning("Inventory item not found while creating request: %s (%s)", inv_id, item_error)
                continue

            # Create an inventory request record linked to this maintenance task
            request_payload = {
                "inventory_id": item_data.get("id") or item_data.get("_doc_id") or inv_id,
                "requested_by": created_by,
                "quantity_requested": qty,
                "purpose": f"Reserved for maintenance task {task_id}",
                "maintenance_task_id": task_id,
                "reference_type": "maintenance_task",
                "reference_id": task_id,
                # Mark as reserved; tenant can request again if item broken
                "status": "reserved",
                "tenant_can_request_again": True,
            }

            # Try to reserve atomically using inventory service helper
            reserve_success, req_id_or_err, reserve_err = await inventory_service.reserve_item_for_task(inv_id, qty, task_id, created_by)
            if not reserve_success:
                logger.warning("Failed to reserve inventory %s: %s", inv_id, req_id_or_err or reserve_err)
                continue

            req_id = req_id_or_err
            created_request_ids.append(req_id)
            # Fetch created request doc to include details
            success, req_doc, err = await self.db.get_document(COLLECTIONS["inventory_requests"], req_id)
            if success and req_doc:
                created_request_docs.append(req_doc)

        # Attach created request ids and details to payload (if any)
        if created_request_ids:
            payload = {**payload, "inventory_request_ids": created_request_ids, "inventory_requests": created_request_docs}

        data = {
            **payload,
            "id": task_id,
            "formatted_id": payload.get("formatted_id") or task_id,
            "status": payload.get("status") or "scheduled",
            "task_type": task_type,
            "maintenance_type": maintenance_type,
            "recurrence_type": payload.get("recurrence_type") or "",
            "assigned_to": payload.get("assigned_to") or "unassigned",
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            # Ensure required fields have defaults
            "priority": payload.get("priority") or "",
            "category": payload.get("category") or "",
            "location": payload.get("location") or "",
            "building_id": payload.get("building_id") or "default_building",
            # Use admin_notes
            "admin_notes": payload.get("admin_notes") or "",
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

        # Persist the updates to the database and return the refreshed task
        success, error = await self.db.update_document(
            COLLECTIONS["maintenance_tasks"],
            task_id,
            update_payload,
            validate=False,
        )

        if not success:
            raise ValueError(error or "Failed to update maintenance task")

        return await self.get_task(task_id)

    async def mark_inventory_request_received(self, request_id: str, performed_by: str, condition: str = "ok", notes: Optional[str] = None) -> Dict[str, Any]:
        """Mark an inventory_request as received by tenant/staff.

        If the item is reported broken/damaged, create a follow-up replacement request and
        add it to the related maintenance task. Only the staff assigned to the task or an
        admin may mark the request received.
        Returns the updated request document (and replacement info when created).
        """
        # Fetch the inventory request
        success, req_doc, err = await self.db.get_document(COLLECTIONS["inventory_requests"], request_id)
        if not success or not req_doc:
            raise ValueError(f"Inventory request not found: {request_id}")

        task_id = req_doc.get("maintenance_task_id")

        # Fetch the maintenance task to validate performer permissions
        task = None
        if task_id:
            task = await self.get_task(task_id)

        # Verify performer is assigned staff for the task or an admin
        performer_profile = await self.user_service.get_user_profile(performed_by)
        performer_role = performer_profile.role if performer_profile else None
        if task:
            assigned = task.assigned_to
            if performed_by != assigned and performer_role != "admin":
                raise ValueError("Only the staff assigned to the task or admins may mark inventory as received")

        # Update the inventory_request status
        update_data = {
            "status": "received",
            "received_by": performed_by,
            "received_at": datetime.utcnow().isoformat(),
            "condition": condition,
            "notes": notes,
            "updated_at": datetime.utcnow(),
        }

        upd_success, upd_err = await self.db.update_document(
            COLLECTIONS["inventory_requests"], request_id, update_data, validate=False
        )

        if not upd_success:
            raise ValueError(f"Failed to update inventory request {request_id}: {upd_err}")

        # Fetch updated request
        success, updated_req, err = await self.db.get_document(COLLECTIONS["inventory_requests"], request_id)
        result: Dict[str, Any] = {"updated_request": updated_req}

        # If item received in good condition, consume stock and mark fulfilled
        if str(condition).lower() in {"ok", "received", "good"}:
            try:
                inventory_id = updated_req.get('inventory_id')
                qty = updated_req.get('quantity_approved') or updated_req.get('quantity_requested') or 1

                # Consume stock (this will create transaction logs and update stock)
                consume_success, consume_err = await inventory_service.consume_stock(
                    item_id=inventory_id,
                    quantity=int(qty),
                    performed_by=performed_by,
                    reference_type="inventory_request",
                    reference_id=request_id,
                    reason=f"Received by staff for maintenance task {task_id or updated_req.get('maintenance_task_id')}"
                )

                if consume_success:
                    # Update request to fulfilled
                    fulfilled_update = {
                        'status': 'fulfilled',
                        'fulfilled_by': performed_by,
                        'fulfilled_date': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    await self.db.update_document(COLLECTIONS['inventory_requests'], request_id, fulfilled_update, validate=False)

                    # Clear reservation flags on inventory item (best-effort)
                    try:
                        await inventory_service.update_inventory_item(
                            inventory_id,
                            {
                                'reserved': False,
                                'reserved_for_task': None,
                                'reserved_at': None,
                                'reserved_quantity': 0,
                                'updated_at': datetime.utcnow()
                            },
                            performed_by
                        )
                    except Exception:
                        logger.warning('Failed to clear reserved flags on inventory %s after receiving', inventory_id)

                    # Refresh updated request for response
                    s2, updated_req, _ = await self.db.get_document(COLLECTIONS['inventory_requests'], request_id)
                    result['updated_request'] = updated_req

            except Exception as e:
                logger.warning('Failed to consume stock on receive for request %s: %s', request_id, e)

        # If item broken/damaged, create a replacement request to re-open the flow
        if str(condition).lower() in {"broken", "damaged", "defective"}:
            replacement_payload = {
                "inventory_id": req_doc.get("inventory_id"),
                "requested_by": req_doc.get("requested_by"),
                "quantity_requested": req_doc.get("quantity_requested", 1),
                "purpose": f"Replacement requested for broken item from request {request_id}",
                "maintenance_task_id": req_doc.get("maintenance_task_id"),
                "reference_type": "inventory_request",
                "reference_id": request_id,
                "parent_request_id": request_id,
                "status": "requested",
                "tenant_can_request_again": True,
            }

            rep_success, rep_id, rep_err = await inventory_service.create_inventory_request(replacement_payload)
            if not rep_success:
                logger.warning("Failed to create replacement inventory request for %s: %s", request_id, rep_err)
            else:
                # Attach replacement info to result and also attach to the maintenance task
                result["replacement_request_id"] = rep_id

                # Add replacement id to task's inventory_request_ids and docs if task exists
                if task:
                    # fetch replacement doc
                    s2, rep_doc, e2 = await self.db.get_document(COLLECTIONS["inventory_requests"], rep_id)
                    # Update task record with the new request id
                    try:
                        # Append to task's inventory_request_ids stored in DB
                        new_ids = (task.inventory_request_ids or []) + [rep_id]
                        await self.db.update_document(
                            COLLECTIONS["maintenance_tasks"],
                            task.id,
                            {"inventory_request_ids": new_ids, "updated_at": datetime.utcnow()},
                            validate=False,
                        )
                    except Exception:
                        logger.warning("Failed to attach replacement request %s to task %s", rep_id, task.id)

                result["replacement_created"] = rep_success

                # Notify admins and assigned staff about the replacement request
                try:
                    from app.services.notification_manager import notification_manager
                    # Item info
                    item_name = ''
                    try:
                        s3, item_doc, _ = await inventory_service.get_inventory_item(req_doc.get('inventory_id'))
                        if s3 and item_doc:
                            item_name = item_doc.get('item_name')
                    except Exception:
                        item_name = ''

                    await notification_manager.notify_inventory_request_submitted(
                        rep_id,
                        replacement_payload.get('requested_by'),
                        item_name,
                        replacement_payload.get('quantity_requested', 1),
                        replacement_payload.get('purpose', '')
                    )

                    # Notify assigned staff if any
                    if task and getattr(task, 'assigned_to', None):
                        await notification_manager.notify_maintenance_task_assigned(
                            task_id=task.id,
                            staff_id=task.assigned_to,
                            task_title=getattr(task, 'task_title', '') or getattr(task, 'title', ''),
                            location=getattr(task, 'location', ''),
                            scheduled_date=getattr(task, 'scheduled_date', None),
                            assigned_by=performed_by
                        )
                except Exception:
                    logger.debug('Failed to send notifications for replacement request')

        return result

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
            'category': '',
            'priority': '',
            'status': 'scheduled',
            'task_type': 'scheduled',
            'recurrence_type': 'none',
            'assigned_to': 'unassigned'
        }
        
        for field, default_value in required_defaults.items():
            if field not in normalized or normalized[field] is None or normalized[field] == '':
                normalized[field] = default_value

        # Preserve admin_notes if present; default to empty string
        if 'admin_notes' not in normalized:
            normalized['admin_notes'] = ''
        
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

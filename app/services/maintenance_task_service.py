import logging
import uuid
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dateutil.relativedelta import relativedelta

from app.database.collections import COLLECTIONS
from app.database.database_service import DatabaseService, database_service
from app.models.database_models import MaintenanceTask
from app.services.user_id_service import UserIdService
from app.services.maintenance_id_service import maintenance_id_service
from app.services.inventory_service import inventory_service
from app.services.task_type_service import task_type_service

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

        # Handle task type inventory reservation first
        task_type_id = payload.get("task_type_id")
        task_type_inventory: List[Dict[str, Any]] = []
        
        if task_type_id:
            try:
                # Fetch task type and its inventory items
                success, task_type_data, error = await task_type_service.get_task_type(task_type_id)
                if success and task_type_data:
                    task_type_inventory = task_type_data.get("inventory_items") or []
                    logger.info(f"Found {len(task_type_inventory)} inventory items from task type {task_type_id}")
                    
                    # Set maintenance_type from task type if not explicitly provided
                    if not payload.get("maintenance_type"):
                        tt_maintenance_type = task_type_data.get("maintenance_type")
                        if tt_maintenance_type:
                            payload["maintenance_type"] = tt_maintenance_type
                            maintenance_type = tt_maintenance_type.lower()
                else:
                    logger.warning(f"Task type {task_type_id} not found: {error}")
            except Exception as e:
                logger.error(f"Error fetching task type {task_type_id}: {e}")
        
        # Merge task type inventory with manually selected inventory
        # Create inventory reservations (not requests) for task type and manual inventory
        manual_inventory = payload.get("parts_used") or []
        
        # Combine task type inventory with manual selections
        all_inventory = []
        all_inventory.extend(task_type_inventory)  # Task type items first
        
        # Add manual inventory (avoid duplicates by inventory_id)
        existing_ids = {item.get("inventory_id") or item.get("id") for item in task_type_inventory}
        for manual_item in (manual_inventory if isinstance(manual_inventory, list) else []):
            item_id = manual_item.get("inventory_id") or manual_item.get("id") if isinstance(manual_item, dict) else manual_item
            if item_id not in existing_ids:
                all_inventory.append(manual_item)
        
        created_reservation_ids: List[str] = []
        created_reservations: List[Dict[str, Any]] = []

        # Create inventory reservations for all inventory items
        for entry in all_inventory:
            if not isinstance(entry, dict):
                continue
                
            inv_id = entry.get("inventory_id") or entry.get("id")
            qty = int(entry.get("quantity") or 1)
            if not inv_id:
                logger.warning("Skipping inventory entry without inventory_id: %s", entry)
                continue

            # Validate inventory item exists
            item_success, item_data, item_error = await inventory_service.get_inventory_item(inv_id)
            if not item_success or not item_data:
                logger.warning("Inventory item not found: %s (%s)", inv_id, item_error)
                continue

            # Create inventory reservation (not request)
            reservation_payload = {
                "inventory_id": item_data.get("id") or item_data.get("_doc_id") or inv_id,
                "maintenance_task_id": task_id,
                "quantity": qty,
            }

            # Create reservation using inventory service
            reserve_success, reservation_id, reserve_err = await inventory_service.create_inventory_reservation(
                reservation_payload, created_by
            )
            if not reserve_success:
                logger.warning("Failed to create inventory reservation %s: %s", inv_id, reserve_err)
                continue
            else:
                logger.debug("Created inventory reservation %s for task %s (inventory %s) -> %s", reservation_id, task_id, inv_id, reserve_success)
            created_reservation_ids.append(reservation_id)
            print(f"[create_task] Created reservation {reservation_id} for task {task_id} and inventory {inv_id}")
            # Fetch created reservation doc to include details
            success, res_doc, err = await self.db.get_document(COLLECTIONS["inventory_reservations"], reservation_id)
            if success and res_doc:
                res_doc["_item_type"] = "reservation"  # Mark as reservation
                created_reservations.append(res_doc)

        # Attach created reservation ids and details to payload (if any)
        if created_reservation_ids:
            payload = {**payload, "inventory_reservation_ids": created_reservation_ids, "inventory_reservations": created_reservations}

        data = {
            **payload,
            "id": task_id,
            "formatted_id": payload.get("formatted_id") or task_id,
            "status": payload.get("status") or "scheduled",
            "task_type": task_type,
            "task_type_id": payload.get("task_type_id"),  # Store reference to TaskType
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

        # If this is an external task, ensure contact fields are set from common payload keys
        if task_type == "external":
            # prefer explicit contact fields, then contractor_ variants, then payload email
            contact_name = (
                payload.get("contact_name")
                or payload.get("contractor_name")
                or payload.get("contractorName")
                or payload.get("contactName")
            )
            contact_number = (
                payload.get("contact_number")
                or payload.get("contactNumber")
                or payload.get("contractor_contact")
                or payload.get("contractorContact")
            )
            contact_email = (
                payload.get("email")
                or payload.get("contact_email")
                or payload.get("contactEmail")
                or payload.get("contractor_email")
                or payload.get("contractorEmail")
                or payload.get("contactEmail")
            )

            if contact_name:
                data["contact_name"] = contact_name
            if contact_number:
                data["contact_number"] = contact_number
            if contact_email:
                data["email"] = contact_email

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

        # If the task status has become completed, consider generating a recurrence
        if update_payload.get("status") == "completed":
            try:
                prev_task = await self.get_task(task_id)
                if prev_task:
                    await self._maybe_generate_recurrence(prev_task, update_payload.get("completed_at") or None)
            except Exception as recurrence_error:
                logger.error("Error handling recurrence generation after completing task %s: %s", task_id, recurrence_error)

        return await self.get_task(task_id)

    async def _maybe_generate_recurrence(self, prev_task: MaintenanceTask, base_completed_at: Optional[datetime] = None) -> Optional[MaintenanceTask]:
        """If prev_task has a recurrence_type, compute next occurrence and create next task with auto-reservation.

        Returns the created task if any, otherwise None.
        """
        try:
            recurrence_type = getattr(prev_task, "recurrence_type", None)
            if not recurrence_type or recurrence_type.lower() in {"none", "", "n/a"}:
                return None

            base_date = base_completed_at or getattr(prev_task, "completed_at", None) or datetime.utcnow()

            def _compute_next_due_date(base_date: datetime, recurrence: str) -> Optional[datetime]:
                try:
                    r = str(recurrence).lower().strip()
                    # Named periods
                    if any(k in r for k in ("weekly", "every week")):
                        return base_date + relativedelta(weeks=+1)
                    if any(k in r for k in ("monthly", "every month")):
                        return base_date + relativedelta(months=+1)
                    if any(k in r for k in ("quarterly", "every quarter", "every 3 months")):
                        return base_date + relativedelta(months=+3)
                    if any(k in r for k in ("yearly", "annually")):
                        return base_date + relativedelta(years=+1)

                    # numeric pattern 'every X ...'
                    m = re.search(r"(\d+)\s*(day|week|month|year)s?", r)
                    if m:
                        amount = int(m.group(1))
                        unit = m.group(2)
                        if unit == "day":
                            return base_date + relativedelta(days=+amount)
                        if unit == "week":
                            return base_date + relativedelta(weeks=+amount)
                        if unit == "month":
                            return base_date + relativedelta(months=+amount)
                        if unit == "year":
                            return base_date + relativedelta(years=+amount)
                except Exception:
                    pass
                return None

            next_due = _compute_next_due_date(base_date, recurrence_type)
            if not next_due:
                return None

            # Build payload for next task
            new_task_payload = {
                "building_id": getattr(prev_task, "building_id", None) or prev_task.building_id,
                "task_title": getattr(prev_task, "task_title", None) or getattr(prev_task, "task_description", "Maintenance Task"),
                "task_description": getattr(prev_task, "task_description", None) or "",
                "location": getattr(prev_task, "location", None) or "",
                "scheduled_date": next_due.isoformat(),
                "recurrence_type": recurrence_type,
                "task_type_id": getattr(prev_task, "task_type_id", None) or None,
                "created_by": "system",
            }

            # Repopulate parts_used from previous task reservations
            try:
                inv_res_ids = getattr(prev_task, "inventory_reservation_ids", []) or []
                parts = []
                for rid in inv_res_ids:
                    s, rdoc, err = await self.db.get_document(COLLECTIONS["inventory_reservations"], rid)
                    if s and rdoc:
                        parts.append({
                            "inventory_id": rdoc.get("inventory_id"),
                            "quantity": rdoc.get("quantity", 1),
                        })
                if parts:
                    new_task_payload["parts_used"] = parts
            except Exception:
                pass

            new_task = await self.create_task("system", new_task_payload)

            # Notify assigned staff if any
            try:
                from app.services.notification_manager import notification_manager
                assigned_to = getattr(new_task, "assigned_to", None)
                if assigned_to:
                    await notification_manager.notify_maintenance_task_assigned(
                        task_id=new_task.id,
                        staff_id=assigned_to,
                        task_title=new_task.task_title,
                        location=new_task.location,
                        scheduled_date=new_task.scheduled_date,
                        assigned_by="system",
                    )
            except Exception:
                logger.debug("Failed to send recurrence notification; continuing")

            return new_task
        except Exception as e:
            logger.error("Error generating recurrence for task %s: %s", getattr(prev_task, 'id', 'unknown'), e)
            return None

    async def finalize_task(self, task_id: str, admin_uid: str, deduct_stock: bool = True) -> Optional[MaintenanceTask]:
        """Finalize (admin-only) a maintenance task: mark inventory received/consumed, mark task completed, and generate recurrence."""
        try:
            mark_success, mark_err = await inventory_service.mark_task_inventory_received(task_id, admin_uid, deduct_stock=deduct_stock)
            if not mark_success:
                logger.warning("Failed to mark task inventory received for finalization: %s", mark_err)

            # Update task to completed; this will trigger recurrence generation in update_task
            update_payload = {"status": "completed", "completed_at": datetime.utcnow()}
            await self.update_task(task_id, update_payload)

            return await self.get_task(task_id)
        except Exception as e:
            logger.error("Failed to finalize task %s: %s", task_id, e)
            raise

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
        datetime_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'next_occurrence', 'assessment_date']
        for field in datetime_fields:
            if field in normalized and isinstance(normalized[field], str):
                try:
                    normalized[field] = datetime.fromisoformat(normalized[field])
                except ValueError:
                    if field in ['created_at', 'updated_at']:
                        normalized[field] = datetime.utcnow()
                    else:
                        normalized[field] = None

        # Normalize common contractor/contact field variations so external tasks
        # consistently expose `contact_name`, `contact_number`, and `email`.
        contact_mappings = {
            'contractorName': 'contact_name',
            'contractor_name': 'contact_name',
            'contactName': 'contact_name',
            'contractorContact': 'contact_number',
            'contractor_contact': 'contact_number',
            'contactNumber': 'contact_number',
            'contact_number': 'contact_number',
            'contactEmail': 'email',
            'contact_email': 'email',
            'contractorEmail': 'email',
            'contractor_email': 'email',
        }
        for old_key, new_key in contact_mappings.items():
            if old_key in normalized and new_key not in normalized:
                normalized[new_key] = normalized.pop(old_key)
        
        return normalized

    def _task_to_dict(self, task: MaintenanceTask) -> Dict[str, Any]:
        data = task.dict(exclude_none=True)
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
                data[key] = value
        return data

    def _generate_task_id(self) -> str:
        return f"MT-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


maintenance_task_service = MaintenanceTaskService()

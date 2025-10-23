"""Service for managing special maintenance tasks (Fire Safety, Earthquake, Typhoon/Flood)."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.database.collections import COLLECTIONS
from app.database.database_service import database_service
from app.models.database_models import MaintenanceTask
from app.services.maintenance_task_service import maintenance_task_service

logger = logging.getLogger(__name__)

# Hardcoded IDs for special maintenance tasks
SPECIAL_TASK_IDS = {
    "fire_safety": "SPECIAL-FIRE-SAFETY-001",
    "earthquake": "SPECIAL-EARTHQUAKE-001",
    "typhoon_flood": "SPECIAL-TYPHOON-FLOOD-001",
}

# Special task templates with checklists
SPECIAL_TASK_TEMPLATES = {
    "fire_safety": {
        "id": SPECIAL_TASK_IDS["fire_safety"],
        "building_id": "default_building",
        "task_title": "Fire Safety Inspection",
        "task_description": "Comprehensive fire safety inspection and maintenance checklist",
        "location": "All Facility Areas",
        "category": "safety",
        "priority": "high",
        "status": "scheduled",
        "task_type": "internal",
        "maintenance_type": "internal",
        "recurrence_type": "monthly",
        "assigned_to": "safety_team",
        "checklist_completed": [
            {
                "id": "fs_1",
                "task": "Inspect fire extinguishers (pressure, accessibility, seals)",
                "completed": False
            },
            {
                "id": "fs_2",
                "task": "Test fire alarm systems and smoke detectors",
                "completed": False
            },
            {
                "id": "fs_3",
                "task": "Check emergency exit signs and lighting",
                "completed": False
            },
            {
                "id": "fs_4",
                "task": "Verify fire doors close properly and are unobstructed",
                "completed": False
            },
            {
                "id": "fs_5",
                "task": "Inspect fire sprinkler systems for leaks or damage",
                "completed": False
            },
            {
                "id": "fs_6",
                "task": "Ensure fire evacuation routes are clear and marked",
                "completed": False
            },
            {
                "id": "fs_7",
                "task": "Check fire hose cabinets and equipment",
                "completed": False
            },
            {
                "id": "fs_8",
                "task": "Review and update emergency contact lists",
                "completed": False
            }
        ]
    },
    "earthquake": {
        "id": SPECIAL_TASK_IDS["earthquake"],
        "building_id": "default_building",
        "task_title": "Earthquake Safety Inspection",
        "task_description": "Earthquake preparedness and structural safety inspection checklist",
        "location": "All Facility Areas",
        "category": "safety",
        "priority": "high",
        "status": "scheduled",
        "task_type": "internal",
        "maintenance_type": "internal",
        "recurrence_type": "quarterly",
        "assigned_to": "safety_team",
        "checklist_completed": [
            {
                "id": "eq_1",
                "task": "Secure heavy furniture and equipment to walls",
                "completed": False
            },
            {
                "id": "eq_2",
                "task": "Check structural supports and foundation",
                "completed": False
            },
            {
                "id": "eq_3",
                "task": "Inspect gas line shutoff valves and accessibility",
                "completed": False
            },
            {
                "id": "eq_4",
                "task": "Verify emergency supplies (water, first aid, flashlights)",
                "completed": False
            },
            {
                "id": "eq_5",
                "task": "Test earthquake detection and alert systems",
                "completed": False
            },
            {
                "id": "eq_6",
                "task": "Review earthquake evacuation procedures with staff",
                "completed": False
            },
            {
                "id": "eq_7",
                "task": "Check designated safe zones and assembly points",
                "completed": False
            },
            {
                "id": "eq_8",
                "task": "Inspect building for cracks or structural weaknesses",
                "completed": False
            }
        ]
    },
    "typhoon_flood": {
        "id": SPECIAL_TASK_IDS["typhoon_flood"],
        "building_id": "default_building",
        "task_title": "Typhoon/Flood Safety Inspection",
        "task_description": "Typhoon and flood preparedness inspection and safety checklist",
        "location": "All Facility Areas",
        "category": "safety",
        "priority": "high",
        "status": "scheduled",
        "task_type": "internal",
        "maintenance_type": "internal",
        "recurrence_type": "quarterly",
        "assigned_to": "safety_team",
        "checklist_completed": [
            {
                "id": "tf_1",
                "task": "Inspect and clear drainage systems and gutters",
                "completed": False
            },
            {
                "id": "tf_2",
                "task": "Check roof integrity and seal potential leak points",
                "completed": False
            },
            {
                "id": "tf_3",
                "task": "Secure outdoor equipment and materials",
                "completed": False
            },
            {
                "id": "tf_4",
                "task": "Test sump pumps and backup power systems",
                "completed": False
            },
            {
                "id": "tf_5",
                "task": "Verify flood barriers and sandbags availability",
                "completed": False
            },
            {
                "id": "tf_6",
                "task": "Inspect windows and doors for proper sealing",
                "completed": False
            },
            {
                "id": "tf_7",
                "task": "Check emergency communication systems",
                "completed": False
            },
            {
                "id": "tf_8",
                "task": "Review typhoon/flood evacuation procedures",
                "completed": False
            },
            {
                "id": "tf_9",
                "task": "Ensure emergency supplies are stocked and accessible",
                "completed": False
            }
        ]
    }
}


class SpecialMaintenanceService:
    """Service for managing special recurring maintenance tasks."""

    async def initialize_special_tasks(self, created_by: str = "system") -> Dict[str, Any]:
        """Initialize all special maintenance tasks if they don't exist."""
        results = {}

        for task_key, template in SPECIAL_TASK_TEMPLATES.items():
            try:
                # Check if task already exists
                existing_task = await maintenance_task_service.get_task(template["id"])

                if existing_task:
                    logger.info(f"Special task {task_key} already exists: {template['id']}")
                    results[task_key] = {
                        "status": "exists",
                        "task_id": template["id"],
                        "message": f"Task {task_key} already initialized"
                    }
                else:
                    # Create the special task
                    now = datetime.utcnow()
                    next_month = now + timedelta(days=30)

                    task_data = {
                        **template,
                        "created_by": created_by,
                        "created_at": now,
                        "updated_at": now,
                        "scheduled_date": next_month,
                    }

                    task = await maintenance_task_service.create_task(created_by, task_data)
                    logger.info(f"Created special task {task_key}: {task.id}")

                    results[task_key] = {
                        "status": "created",
                        "task_id": task.id,
                        "message": f"Task {task_key} created successfully"
                    }

            except Exception as e:
                logger.error(f"Error initializing special task {task_key}: {e}")
                results[task_key] = {
                    "status": "error",
                    "task_id": template["id"],
                    "message": str(e)
                }

        return results

    async def get_special_tasks(self) -> List[MaintenanceTask]:
        """Retrieve all special maintenance tasks."""
        tasks = []

        for task_id in SPECIAL_TASK_IDS.values():
            try:
                task = await maintenance_task_service.get_task(task_id)
                if task:
                    tasks.append(task)
            except Exception as e:
                logger.error(f"Error fetching special task {task_id}: {e}")

        return tasks

    async def get_special_task_by_key(self, task_key: str) -> Optional[MaintenanceTask]:
        """Get a specific special task by its key (fire_safety, earthquake, typhoon_flood)."""
        task_id = SPECIAL_TASK_IDS.get(task_key)
        if not task_id:
            return None

        return await maintenance_task_service.get_task(task_id)

    async def get_special_task_summary(self, task_key: str) -> Dict[str, Any]:
        """Get summary information for a special task."""
        task = await self.get_special_task_by_key(task_key)

        if not task:
            return {
                "exists": False,
                "task_key": task_key,
                "message": "Task not initialized"
            }

        # Calculate completion percentage
        checklist = task.checklist_completed or []
        total_items = len(checklist)
        completed_items = sum(1 for item in checklist if item.get("completed", False))
        completion_percentage = (completed_items / total_items * 100) if total_items > 0 else 0

        # Format next scheduled date
        next_date = task.scheduled_date
        if isinstance(next_date, datetime):
            next_date_str = next_date.strftime("%m/%d/%Y")
        else:
            next_date_str = "Not scheduled"

        return {
            "exists": True,
            "task_key": task_key,
            "task_id": task.id,
            "title": task.task_title,
            "status": task.status,
            "completion_percentage": round(completion_percentage, 1),
            "completed_items": completed_items,
            "total_items": total_items,
            "next_scheduled_date": next_date_str,
            "priority": task.priority,
            "recurrence": task.recurrence_type,
        }

    async def reset_special_task_checklist(self, task_key: str) -> Optional[MaintenanceTask]:
        """Reset a special task's checklist (mark all as incomplete) and schedule next occurrence."""
        task_id = SPECIAL_TASK_IDS.get(task_key)
        if not task_id:
            return None

        template = SPECIAL_TASK_TEMPLATES.get(task_key)
        if not template:
            return None

        # Calculate next scheduled date based on recurrence
        now = datetime.utcnow()
        recurrence = template.get("recurrence_type", "monthly")

        if recurrence == "monthly":
            next_date = now + timedelta(days=30)
        elif recurrence == "quarterly":
            next_date = now + timedelta(days=90)
        elif recurrence == "weekly":
            next_date = now + timedelta(days=7)
        else:
            next_date = now + timedelta(days=30)

        # Reset checklist to uncompleted state
        reset_checklist = [
            {**item, "completed": False}
            for item in template["checklist_completed"]
        ]

        updates = {
            "checklist_completed": reset_checklist,
            "status": "scheduled",
            "scheduled_date": next_date,
            "started_at": None,
            "completed_at": None,
        }

        return await maintenance_task_service.update_task(task_id, updates)


special_maintenance_service = SpecialMaintenanceService()

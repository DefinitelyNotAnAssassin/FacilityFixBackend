from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.database_models import TaskType
from .task_type_id_service import task_type_id_service
from .user_id_service import user_id_service
import logging

logger = logging.getLogger(__name__)

class TaskTypeService:
    def __init__(self):
        self.db = database_service
    
    async def _enrich_task_type_with_user_data(self, task_type: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich task type with user names for created_by and updated_by"""
        try:
            # Enrich created_by with user name
            if task_type.get('created_by'):
                created_by_name = await user_id_service.get_user_full_name(task_type['created_by'])
                task_type['created_by_name'] = created_by_name
            
            # Determine if this was actually edited (not just created)
            created_at = task_type.get('created_at')
            updated_at = task_type.get('updated_at')
            updated_by = task_type.get('updated_by')
            created_by = task_type.get('created_by')
            
            # Consider it "edited" if:
            # 1. There's an updated_by field AND it's different from created_by
            # 2. OR updated_at is significantly different from created_at (more than 1 second)
            was_edited = False
            
            if updated_by and updated_by != created_by:
                was_edited = True
            elif created_at and updated_at:
                # Handle both datetime objects and ISO strings
                try:
                    from datetime import datetime
                    if isinstance(created_at, str):
                        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created_dt = created_at
                    
                    if isinstance(updated_at, str):
                        updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    else:
                        updated_dt = updated_at
                    
                    # Consider edited if more than 1 second difference
                    if abs((updated_dt - created_dt).total_seconds()) > 1:
                        was_edited = True
                except Exception:
                    # Fallback to string comparison
                    was_edited = str(updated_at) != str(created_at)
            
            # Only include updated_by info if actually edited
            if was_edited and updated_by:
                updated_by_name = await user_id_service.get_user_full_name(updated_by)
                task_type['updated_by_name'] = updated_by_name
            else:
                # Remove updated_by fields if not actually edited
                task_type.pop('updated_by', None)
                task_type.pop('updated_by_name', None)
                task_type.pop('updated_at', None)  # Also remove updated_at if not edited
            
            return task_type
        except Exception as e:
            logger.warning(f"Failed to enrich task type with user data: {e}")
            return task_type

    async def create_task_type(self, data: Dict[str, Any], created_by: str) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            now = datetime.utcnow()
            data['created_by'] = created_by
            data['created_at'] = now
            data['updated_at'] = now
            # Don't set updated_by on creation - only on actual updates
            data['is_active'] = True
            # Generate a formatted ID and persist as document id
            formatted_id = await task_type_id_service.generate_task_type_id()
            data['formatted_id'] = formatted_id
            data['id'] = formatted_id
            success, doc_id, error = await self.db.create_document(
                COLLECTIONS['task_types'],
                data,
                document_id=formatted_id,
                validate=True
            )
            return success, doc_id, error
        except Exception as e:
            logger.error(f"Error creating task type: {e}")
            return False, None, str(e)

    async def get_task_type(self, task_type_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        try:
            success, task_type, error = await self.db.get_document(COLLECTIONS['task_types'], task_type_id)
            if success and task_type:
                task_type = await self._enrich_task_type_with_user_data(task_type)
            return success, task_type, error
        except Exception as e:
            logger.error(f"Error getting task type {task_type_id}: {e}")
            return False, None, str(e)

    async def list_task_types(self, building_id: Optional[str] = None, include_inactive: bool = False) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        try:
            filters = []
            if not include_inactive:
                filters.append(('is_active', '==', True))
            # Optional building_id filter (if task types are per building in future)
            if building_id:
                filters.append(('building_id', '==', building_id))
            
            success, task_types, error = await self.db.query_documents(COLLECTIONS['task_types'], filters)
            
            if success and task_types:
                # Enrich each task type with user data
                enriched_task_types = []
                for task_type in task_types:
                    enriched = await self._enrich_task_type_with_user_data(task_type)
                    enriched_task_types.append(enriched)
                return True, enriched_task_types, None
            
            return success, task_types, error
        except Exception as e:
            logger.error(f"Error listing task types: {e}")
            return False, [], str(e)

    async def update_task_type(self, task_type_id: str, update_data: Dict[str, Any], updated_by: str) -> Tuple[bool, Optional[str]]:
        try:
            update_data['updated_at'] = datetime.utcnow()
            update_data['updated_by'] = updated_by
            success, error = await self.db.update_document(COLLECTIONS['task_types'], task_type_id, update_data, validate=True)
            return success, error
        except Exception as e:
            logger.error(f"Error updating task type {task_type_id}: {e}")
            return False, str(e)

    async def soft_delete_task_type(self, task_type_id: str, deleted_by: str) -> Tuple[bool, Optional[str]]:
        try:
            success, error = await self.db.update_document(COLLECTIONS['task_types'], task_type_id, {
                'is_active': False,
                'updated_at': datetime.utcnow(),
                'updated_by': deleted_by
            }, validate=False)
            return success, error
        except Exception as e:
            logger.error(f"Error soft-deleting task type {task_type_id}: {e}")
            return False, str(e)

    async def add_inventory_item(self, task_type_id: str, item: Dict[str, Any], updated_by: str) -> Tuple[bool, Optional[str]]:
        try:
            # Fetch existing
            success, doc, err = await self.get_task_type(task_type_id)
            if not success or not doc:
                return False, err or 'Task type not found'
            items = doc.get('inventory_items') or []
            items.append(item)
            return await self.update_task_type(task_type_id, {'inventory_items': items}, updated_by)
        except Exception as e:
            logger.error(f"Error adding inventory item to task type {task_type_id}: {e}")
            return False, str(e)

    async def remove_inventory_item(self, task_type_id: str, item_id: str, updated_by: str) -> Tuple[bool, Optional[str]]:
        try:
            success, doc, err = await self.get_task_type(task_type_id)
            if not success or not doc:
                return False, err or 'Task type not found'
            items = doc.get('inventory_items') or []
            new_items = [i for i in items if i.get('item_id') != item_id and i.get('id') != item_id]
            return await self.update_task_type(task_type_id, {'inventory_items': new_items}, updated_by)
        except Exception as e:
            logger.error(f"Error removing inventory item from task type {task_type_id}: {e}")
            return False, str(e)

# create singleton

task_type_service = TaskTypeService()

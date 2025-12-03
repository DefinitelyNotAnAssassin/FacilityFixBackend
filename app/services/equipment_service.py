from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.database_models import Equipment
from .equipment_id_service import equipment_id_service
from .user_id_service import UserIdService
import logging

logger = logging.getLogger(__name__)

class EquipmentService:
    def __init__(self):
        self.db = database_service
        self.user_service = UserIdService()

    async def create_equipment(self, equipment_data: Dict[str, Any], created_by: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Create a new equipment record"""
        try:
            # Generate a formatted equipment ID and attach it to the record
            try:
                formatted = await equipment_id_service.generate_equipment_id()
                equipment_data['formatted_id'] = formatted
            except Exception as e:
                logger.warning(f"Failed to generate formatted equipment ID: {e}")
            else:
                # Also expose as equipment_id for frontend compatibility
                equipment_data['equipment_id'] = formatted

            # Normalize payload to expected backend fields (accept frontend keys)
            equipment_data = self._normalize_payload(equipment_data)

            equipment_data.update({
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'created_by': created_by,
                # Try to store a snapshot of the creator's display name
                'created_by_name': None,
                'is_active': True
            })

            # Attempt to fetch creator name and store a snapshot on the document before saving
            try:
                creator_profile = await self.user_service.get_user_profile(created_by)
                if creator_profile:
                    equipment_data['created_by_name'] = f"{creator_profile.first_name} {creator_profile.last_name}"
            except Exception:
                # If we fail to resolve the name, leave the snapshot as None
                pass

            # Use the formatted ID as the document ID to make lookup deterministic
            success, doc_id, error = await self.db.create_document(
                COLLECTIONS['equipment'],
                equipment_data,
                document_id=equipment_data.get('formatted_id'),
                validate=True
            )

            if success:
                # Return the formatted id as the created document id (for frontend convenience)
                return True, doc_id or equipment_data.get('formatted_id'), None
            else:
                return False, None, error

        except Exception as e:
            logger.error(f"Error creating equipment: {e}")
            return False, None, str(e)

    async def get_equipment(self, equipment_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Get equipment by ID or asset_tag"""
        try:
            # try asset_tag search first
            success, items, error = await self.db.query_documents(
                COLLECTIONS['equipment'],
                [('asset_tag', '==', equipment_id)]
            )

            if success and items:
                # Normalize response and enrich with user data
                normalized = self._normalize_response(items[0])
                await self._enrich_with_user_data(normalized)
                return True, normalized, None

            # fallback to document ID
            success, doc, err = await self.db.get_document(COLLECTIONS['equipment'], equipment_id)
            if success and doc:
                normalized = self._normalize_response(doc)
                await self._enrich_with_user_data(normalized)
                return True, normalized, None
            return success, doc, err

        except Exception as e:
            logger.error(f"Error getting equipment {equipment_id}: {e}")
            return False, None, str(e)

    async def update_equipment(self, equipment_id: str, update_data: Dict[str, Any], updated_by: str) -> Tuple[bool, Optional[str]]:
        """Update equipment fields"""
        try:
            success, current, error = await self.get_equipment(equipment_id)
            if not success:
                return False, f"Equipment not found: {error}"

            update_data = self._normalize_payload(update_data)
            update_data['updated_at'] = datetime.now()
            update_data['updated_by'] = updated_by
            # Try to store a snapshot of the updater's display name
            update_data['updated_by_name'] = None

            # Attempt to fetch updater name and store a snapshot on the document
            try:
                updater_profile = await self.user_service.get_user_profile(updated_by)
                if updater_profile:
                    update_data['updated_by_name'] = f"{updater_profile.first_name} {updater_profile.last_name}"
            except Exception:
                # If we fail to resolve the name, leave the snapshot as None
                pass

            doc_id = current.get('_doc_id') or current.get('id') or equipment_id
            success, error = await self.db.update_document(
                COLLECTIONS['equipment'],
                doc_id,
                update_data
            )

            if success:
                return True, None
            else:
                return False, f"Failed to update equipment: {error}"

        except Exception as e:
            logger.error(f"Error updating equipment {equipment_id}: {e}")
            return False, str(e)

    async def soft_delete_equipment(self, equipment_id: str, deleted_by: str) -> Tuple[bool, Optional[str]]:
        """Soft-delete equipment by marking it inactive (do not remove from DB)"""
        try:
            success, current, error = await self.get_equipment(equipment_id)
            if not success:
                return False, f"Equipment not found: {error}"

            doc_id = current.get('_doc_id') or current.get('id') or equipment_id
            update_data = {
                'is_active': False,
                'updated_at': datetime.now(),
                'updated_by': deleted_by,
                # Try to store a snapshot of the deleter's display name
                'updated_by_name': None
            }

            # Attempt to fetch deleter name and store a snapshot on the document
            try:
                deleter_profile = await self.user_service.get_user_profile(deleted_by)
                if deleter_profile:
                    update_data['updated_by_name'] = f"{deleter_profile.first_name} {deleter_profile.last_name}"
            except Exception:
                # If we fail to resolve the name, leave the snapshot as None
                pass

            success, error = await self.db.update_document(
                COLLECTIONS['equipment'],
                doc_id,
                update_data
            )

            if success:
                return True, None
            else:
                return False, f"Failed to soft-delete equipment: {error}"

        except Exception as e:
            logger.error(f"Error soft-deleting equipment {equipment_id}: {e}")
            return False, str(e)

    async def list_by_building(self, building_id: str, include_inactive: bool = False) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        try:
            filters = [('building_id', '==', building_id)]
            if not include_inactive:
                filters.append(('is_active', '==', True))

            success, docs, err = await self.db.query_documents(COLLECTIONS['equipment'], filters)
            if success:
                normalized_docs = [self._normalize_response(d) for d in docs]
                # Enrich all documents with user data
                for doc in normalized_docs:
                    await self._enrich_with_user_data(doc)
                return True, normalized_docs, None
            return success, docs, err

        except Exception as e:
            logger.error(f"Error listing equipment for building {building_id}: {e}")
            return False, [], str(e)

    async def search_equipment(self, building_id: str, q: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        try:
            success, items, error = await self.list_by_building(building_id, include_inactive=False)
            if not success:
                return False, [], error

            ql = q.lower()
            filtered = [
                item for item in items
                if ql in (item.get('equipment_name') or '').lower() or
                   ql in (item.get('asset_tag') or '').lower() or
                   ql in (item.get('model_number') or '').lower() or
                   ql in (item.get('serial_number') or '').lower() or
                   ql in (item.get('manufacturer') or '').lower()
            ]

            return True, filtered, None

        except Exception as e:
            logger.error(f"Error searching equipment: {e}")
            return False, [], str(e)

    def _normalize_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize incoming payload keys from frontend (camelCase or alternate names) to backend snake_case."""
        if not isinstance(data, dict):
            # if data is a Pydantic model or similar, convert to dict
            try:
                data = dict(data)
            except Exception:
                return data

        out = {}
        for k, v in data.items():
            if k in ('name', 'equipmentName'):
                out['equipment_name'] = v
            elif k in ('equipment_id', 'equipmentId', 'formattedId'):
                # map client-provided equipment_id to formatted_id
                out['formatted_id'] = v
            elif k in ('assetTag', 'asset_tag'):
                out['asset_tag'] = v
            elif k in ('modelNumber', 'model_number'):
                out['model_number'] = v
            elif k in ('serialNumber', 'serial_number'):
                out['serial_number'] = v
            elif k in ('equipmentType', 'equipment_type'):
                out['equipment_type'] = v
            elif k in ('createdBy', 'created_by'):
                out['created_by'] = v
            elif k in ('createdAt', 'created_at'):
                out['created_at'] = v
            elif k in ('updatedAt', 'updated_at'):
                out['updated_at'] = v
            elif k in ('acquisitionDate', 'acquisition_date'):
                out['acquisition_date'] = v
            elif k in ('installationDate', 'installation_date'):
                out['installation_date'] = v
            elif k in ('lastMaintenanceDate', 'last_maintenance_date'):
                out['last_maintenance_date'] = v
            elif k in ('location', 'area'):
                out['location'] = v
            else:
                # pass through other keys as-is (building_id, category, status, manufacturer, etc.)
                out[k] = v
        return out

    def _normalize_response(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich and normalize DB document for frontend convenience (add camelCase and alternate keys)."""
        if not isinstance(doc, dict):
            try:
                doc = dict(doc)
            except Exception:
                return doc

        out = dict(doc)

        # document id key mapping
        if '_doc_id' in doc:
            out['id'] = doc.get('_doc_id')
        if 'id' not in out and '_doc_id' not in doc and 'id' in doc:
            out['id'] = doc.get('id')

        # formatted_id as equipment_id for frontend
        formatted = doc.get('formatted_id') or doc.get('equipment_id')
        if formatted:
            out['equipment_id'] = formatted
            out['equipmentId'] = formatted

        # name and equipmentName
        name = doc.get('equipment_name') or doc.get('name')
        if name:
            out['name'] = name
            out['equipmentName'] = name

        # camelCase fields
        if 'asset_tag' in doc:
            out['assetTag'] = doc.get('asset_tag')
        if 'model_number' in doc:
            out['modelNumber'] = doc.get('model_number')
        if 'serial_number' in doc:
            out['serialNumber'] = doc.get('serial_number')
        if 'equipment_type' in doc:
            out['equipmentType'] = doc.get('equipment_type')
        if 'acquisition_date' in doc:
            out['acquisitionDate'] = doc.get('acquisition_date')
        if 'installation_date' in doc:
            out['installationDate'] = doc.get('installation_date')
        if 'created_by' in doc:
            out['createdBy'] = doc.get('created_by')
        if 'created_at' in doc:
            out['createdAt'] = doc.get('created_at')
        if 'updated_at' in doc:
            out['updatedAt'] = doc.get('updated_at')
        if 'updated_by' in doc:
            out['updatedBy'] = doc.get('updated_by')

        return out

    async def _enrich_with_user_data(self, doc: Dict[str, Any]) -> None:
        """Enrich document with user data (replace UIDs with names for display)"""
        try:
            # Replace created_by UID with full name
            created_by_uid = doc.get('created_by')
            if created_by_uid:
                try:
                    user_profile = await self.user_service.get_user_profile(created_by_uid)
                    if user_profile:
                        doc['created_by'] = f"{user_profile.first_name} {user_profile.last_name}"
                    else:
                        # Fall back to any stored snapshot value on the document
                        if doc.get('created_by_name'):
                            doc['created_by'] = doc.get('created_by_name')
                        else:
                            doc['created_by'] = "Unknown User"
                except Exception:
                    if doc.get('created_by_name'):
                        doc['created_by'] = doc.get('created_by_name')
                    else:
                        doc['created_by'] = "Unknown User"

            # Replace updated_by UID with full name if present
            updated_by_uid = doc.get('updated_by')
            if updated_by_uid:
                try:
                    user_profile = await self.user_service.get_user_profile(updated_by_uid)
                    if user_profile:
                        doc['updated_by'] = f"{user_profile.first_name} {user_profile.last_name}"
                    else:
                        if doc.get('updated_by_name'):
                            doc['updated_by'] = doc.get('updated_by_name')
                        else:
                            doc['updated_by'] = "Unknown User"
                except Exception:
                    if doc.get('updated_by_name'):
                        doc['updated_by'] = doc.get('updated_by_name')
                    else:
                        doc['updated_by'] = "Unknown User"
        except Exception as e:
            logger.warning(f"Failed to enrich user data: {e}")
            # Don't fail the whole operation if user enrichment fails


# Singleton instance
equipment_service = EquipmentService()


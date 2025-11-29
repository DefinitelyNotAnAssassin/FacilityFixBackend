from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..auth.dependencies import get_current_user, require_role
from ..services.equipment_service import equipment_service
from ..models.database_models import Equipment
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/equipment",
    tags=["Equipment Registry"],
    responses={404: {"description": "Not found"}}
)

@router.post("/", response_model=Dict[str, Any])
async def create_equipment(
    equipment_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Create a new equipment record (Admin only)"""
    try:
        success, equipment_id, error = await equipment_service.create_equipment(
            equipment_data,  # raw dict -> service will normalize
            current_user["uid"]
        )

        if success:
            # Fetch created equipment document for the response
            got_success, got_doc, got_err = await equipment_service.get_equipment(equipment_id)
            response_data = got_doc if (got_success and got_doc) else {"id": equipment_id}
            return {"success": True, "message": "Equipment created", "equipment_id": equipment_id, "data": response_data}
        else:
            raise HTTPException(status_code=400, detail=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating equipment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{equipment_id}", response_model=Dict[str, Any])
async def get_equipment(
    equipment_id: str = Path(..., description="Equipment ID or asset tag"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get equipment by document ID or asset tag"""
    try:
        success, data, error = await equipment_service.get_equipment(equipment_id)
        if success and data:
            return {"success": True, "data": data}
        else:
            raise HTTPException(status_code=404, detail=error or "Equipment not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching equipment {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{equipment_id}", response_model=Dict[str, Any])
async def update_equipment(
    equipment_id: str,
    update_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Update equipment (Admin only)"""
    try:
        success, error = await equipment_service.update_equipment(
            equipment_id, update_data, current_user["uid"]
        )

        if success:
            # Return updated equipment document
            got_success, got_doc, got_err = await equipment_service.get_equipment(equipment_id)
            response_data = got_doc if (got_success and got_doc) else None
            return {"success": True, "message": "Equipment updated", "data": response_data}
        else:
            raise HTTPException(status_code=400, detail=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating equipment {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{equipment_id}", response_model=Dict[str, Any])
async def delete_equipment(
    equipment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Soft-delete equipment (mark inactive) - does not remove from DB"""
    try:
        success, error = await equipment_service.soft_delete_equipment(
            equipment_id, current_user["uid"]
        )

        if success:
            return {"success": True, "message": "Equipment soft-deleted (inactive)"}
        else:
            raise HTTPException(status_code=400, detail=error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting equipment {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}", response_model=Dict[str, Any])
async def list_equipment_by_building(
    building_id: str,
    include_inactive: bool = Query(False, description="Include inactive equipment"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        success, items, error = await equipment_service.list_by_building(building_id, include_inactive)
        if success:
            return {"success": True, "data": items, "count": len(items)}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing equipment for building {building_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/buildings/{building_id}/search", response_model=Dict[str, Any])
async def search_equipment(
    building_id: str,
    q: str = Query(..., description="Search term"),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    try:
        success, results, error = await equipment_service.search_equipment(building_id, q)
        if success:
            return {"success": True, "data": results, "count": len(results), "search_term": q}
        else:
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching equipment in building {building_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

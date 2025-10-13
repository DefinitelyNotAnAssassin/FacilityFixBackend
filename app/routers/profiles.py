from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, Dict, Any
from ..services.profile_service import profile_service
from ..models.user import UserUpdate, UserProfileComplete
from ..auth.dependencies import require_admin, require_staff_or_admin, get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/profiles", tags=["profile-management"])

class ProfilePreferences(BaseModel):
    notifications_enabled: bool = True
    email_notifications: bool = True
    sms_notifications: bool = False
    language: str = "en"
    timezone: str = "UTC"
    theme: str = "light"

class ProfileHistoryResponse(BaseModel):
    user_id: str
    updated_by: str
    updated_at: str
    changes: Dict[str, Any]
    previous_values: Dict[str, Any]

@router.get("/{user_id}/complete")
async def get_complete_profile(
    user_id: str,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get complete user profile with Firebase data and completion score"""
    try:
        success, profile_data, error = await profile_service.get_complete_profile(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {error}"
            )
        
        return profile_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving complete profile: {str(e)}"
        )

@router.get("/me/complete")
async def get_my_complete_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's complete profile"""
    try:
        user_id = current_user.get("uid")
        success, profile_data, error = await profile_service.get_complete_profile(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {error}"
            )
        
        return profile_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving profile: {str(e)}"
        )

@router.put("/{user_id}/update")
async def update_profile_with_history(
    user_id: str,
    profile_update: UserUpdate,
    current_user: dict = Depends(require_admin)
):
    """Update user profile with validation and history tracking"""
    try:
        # Prepare update data
        update_data = {}
        if profile_update.first_name is not None:
            update_data['first_name'] = profile_update.first_name
        if profile_update.last_name is not None:
            update_data['last_name'] = profile_update.last_name
        if profile_update.phone_number is not None:
            update_data['phone_number'] = profile_update.phone_number
        if profile_update.department is not None:
            update_data['department'] = profile_update.department
        if profile_update.building_id is not None:
            update_data['building_id'] = profile_update.building_id
        if profile_update.unit_id is not None:
            update_data['unit_id'] = profile_update.unit_id
        
        success, error = await profile_service.update_profile_with_history(
            user_id, 
            update_data, 
            current_user.get("uid")
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error
            )
        
        return {"message": "Profile updated successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating profile: {str(e)}"
        )

@router.get("/{user_id}/history")
async def get_profile_history(
    user_id: str,
    limit: int = Query(10, description="Number of history entries to return"),
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get profile change history"""
    try:
        success, history, error = await profile_service.get_profile_history(user_id, limit)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving profile history: {error}"
            )
        
        return {
            "user_id": user_id,
            "history": history,
            "total_entries": len(history)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving profile history: {str(e)}"
        )

@router.get("/search")
async def search_users(
    q: str = Query(..., description="Search term"),
    role: Optional[str] = Query(None, description="Filter by role"),
    building_id: Optional[str] = Query(None, description="Filter by building"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(require_staff_or_admin)
):
    """Search users by name, email, or department"""
    try:
        filters = {}
        if role:
            filters['role'] = role
        if building_id:
            filters['building_id'] = building_id
        if status:
            filters['status'] = status
        
        success, users, error = await profile_service.search_users(q, filters)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Search failed: {error}"
            )
        
        return {
            "search_term": q,
            "filters": filters,
            "results": users,
            "total_results": len(users)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search error: {str(e)}"
        )

@router.get("/building/{building_id}")
async def get_building_users(
    building_id: str,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get all users in a specific building"""
    try:
        success, users, error = await profile_service.get_users_by_building(building_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving building users: {error}"
            )
        
        return {
            "building_id": building_id,
            "users": users,
            "total_users": len(users)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving building users: {str(e)}"
        )

@router.get("/{user_id}/export")
async def export_user_data(
    user_id: str,
    current_user: dict = Depends(require_admin)
):
    """Export complete user data for GDPR compliance"""
    try:
        success, export_data, error = await profile_service.export_user_data(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User data not found: {error}"
            )
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting user data: {str(e)}"
        )

@router.get("/{user_id}/completion")
async def get_profile_completion(
    user_id: str,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get profile completion status"""
    try:
        success, profile_data, error = await profile_service.get_complete_profile(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {error}"
            )
        
        return {
            "user_id": user_id,
            "completion": profile_data.get('completion_score', {}),
            "profile_complete": profile_data.get('completion_score', {}).get('is_complete', False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking profile completion: {str(e)}"
        )

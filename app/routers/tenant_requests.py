from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.auth.dependencies import get_current_user, require_role
from app.database.database_service import DatabaseService
from app.services.user_id_service import user_id_service
import logging

router = APIRouter(prefix="/tenant-requests", tags=["tenant-requests"])
logger = logging.getLogger(__name__)

@router.get("/")
async def get_all_tenant_requests(
    user_id: str = "",
    current_user: dict = Depends(get_current_user)
):
    """
    Get all tenant requests from all three collections:
    - concern_slips (Concern Slip)
    - job_services (Job Service)
    - work_order_permits (Work Order Permit)
    
    Filtering logic:
    - Tenant role: Only their own requests (reported_by/requested_by matches their user_id)
    - Staff role: Only requests assigned to them (assigned_to matches their user_id)
    - Admin role: All requests (no filtering)
    """
    try:
        db = DatabaseService()
        all_requests = []
        
        # Get current user's role and ID
        user_role = current_user.get("role")
        current_user_id = current_user.get("uid")
        
        logger.info(f"[TENANT_REQUESTS] User {current_user_id} with role {user_role} requesting tenant requests")
        
        # Fetch from concern_slips collection
        try:
            concern_slips = await db.get_all_documents("concern_slips")
            for slip in concern_slips:
                # Ensure request_type is set
                if 'request_type' not in slip or not slip['request_type']:
                    slip['request_type'] = 'Concern Slip'
                all_requests.append(slip)
            logger.info(f"[TENANT_REQUESTS] Fetched {len(concern_slips)} concern slips")
        except Exception as e:
            logger.error(f"[TENANT_REQUESTS] Error fetching concern slips: {e}")
        
        # Fetch from job_services collection
        try:
            job_services = await db.get_all_documents("job_services")
            for js in job_services:
                # Ensure request_type is set
                if 'request_type' not in js or not js['request_type']:
                    js['request_type'] = 'Job Service'
                all_requests.append(js)
            logger.info(f"[TENANT_REQUESTS] Fetched {len(job_services)} job services")
        except Exception as e:
            logger.error(f"[TENANT_REQUESTS] Error fetching job services: {e}")
        
        # Fetch from work_order_permits collection
        try:
            work_orders = await db.get_all_documents("work_order_permits")
            for wo in work_orders:
                # Ensure request_type is set
                if 'request_type' not in wo or not wo['request_type']:
                    wo['request_type'] = 'Work Order Permit'
                all_requests.append(wo)
            logger.info(f"[TENANT_REQUESTS] Fetched {len(work_orders)} work order permits")
        except Exception as e:
            logger.error(f"[TENANT_REQUESTS] Error fetching work orders: {e}")
        
        # Apply role-based filtering
        if user_role == "tenant":
            # Tenants can only see their own requests
            all_requests = [
                req for req in all_requests 
                if req.get('reported_by') == current_user_id or 
                   req.get('requested_by') == current_user_id or
                   req.get('created_by') == current_user_id
            ]
            logger.info(f"[TENANT_REQUESTS] Filtered to {len(all_requests)} requests for tenant {current_user_id}")
        elif user_role == "staff":
            # Staff can only see requests assigned to them
            # First, get the staff's staff_id from their user profile
            user_profile = await user_id_service.get_user_profile(current_user_id)
            if user_profile and user_profile.staff_id:
                staff_id = user_profile.staff_id
                all_requests = [
                    req for req in all_requests 
                    if req.get('assigned_to') == staff_id
                ]
                logger.info(f"[TENANT_REQUESTS] Filtered to {len(all_requests)} requests assigned to staff_id {staff_id} (user {current_user_id})")
            else:
                # If no staff_id found, return empty list
                logger.warning(f"[TENANT_REQUESTS] No staff_id found for user {current_user_id}, returning empty list")
                all_requests = []
        elif user_role == "admin":
            # Admins can see all requests
            logger.info(f"[TENANT_REQUESTS] Admin user - showing all {len(all_requests)} requests")
        else:
            # Unknown role - return empty list for security
            logger.warning(f"[TENANT_REQUESTS] Unknown role {user_role} - returning empty list")
            all_requests = []
        
        # Legacy filter by user_id if provided (for backward compatibility)
        # This will further filter already role-filtered results
        if user_id:
            all_requests = [
                req for req in all_requests 
                if req.get('reported_by') == user_id or 
                   req.get('requested_by') == user_id or
                   req.get('created_by') == user_id
            ]
            logger.info(f"[TENANT_REQUESTS] Further filtered to {len(all_requests)} requests for user_id parameter {user_id}")
        
        # Sort by submission date (latest first) - handle mixed date types
        def get_sort_key(x):
            from datetime import datetime, timezone
            date_val = x.get('submitted_at') or x.get('created_at')
            
            if not date_val:
                return datetime.min
            
            # If it's already a datetime object
            if hasattr(date_val, 'year'):
                # Remove timezone info to make it naive
                if hasattr(date_val, 'tzinfo') and date_val.tzinfo is not None:
                    return date_val.replace(tzinfo=None)
                return date_val
            
            # If it's a string, try to parse it
            if isinstance(date_val, str):
                try:
                    parsed = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                    # Remove timezone info to make it naive
                    return parsed.replace(tzinfo=None)
                except:
                    return datetime.min
            
            return datetime.min
        
        all_requests.sort(key=get_sort_key, reverse=True)
        
        logger.info(f"[TENANT_REQUESTS] Returning {len(all_requests)} total requests")
        return all_requests
        
    except Exception as e:
        logger.error(f"[TENANT_REQUESTS] Error getting tenant requests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get tenant requests: {str(e)}")

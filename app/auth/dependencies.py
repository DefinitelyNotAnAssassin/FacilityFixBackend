from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .firebase_auth import firebase_auth
from typing import Optional
import logging

security = HTTPBearer()
logger = logging.getLogger(__name__)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify Firebase authentication token and return user data.
    Raises 401 if token is invalid.
    """
    try:
        token = credentials.credentials
        user_data = await firebase_auth.verify_token(token)
        
        if not user_data:
            logger.warning("[Auth] Token verification failed - invalid token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"[Auth] ✅ Authenticated user: {user_data.get('email')} with role: {user_data.get('role')}")
        
        return user_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auth] ❌ Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_role(required_roles: list):
    def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role")
        logger.info(f"[Auth] Checking role: user has '{user_role}', required: {required_roles}")
        
        if user_role not in required_roles:
            logger.warning(f"[Auth] Role check failed: user role '{user_role}' not in required roles {required_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_roles}, current role: {user_role}"
            )
        return current_user
    return role_checker

# Role-specific dependencies
async def require_admin(current_user: dict = Depends(get_current_user)):
    user_role = current_user.get("role")
    logger.info(f"[Auth] Admin check: user role is '{user_role}'")
    
    if user_role != "admin":
        logger.warning(f"[Auth] Admin access denied: user role '{user_role}' is not admin")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required. Current role: {user_role}"
        )
    return current_user

async def require_staff_or_admin(current_user: dict = Depends(get_current_user)):
    role = current_user.get("role")
    logger.info(f"[Auth] Staff/Admin check: user role is '{role}'")
    
    if role not in ["admin", "staff"]:
        logger.warning(f"[Auth] Staff/Admin access denied: user role '{role}' is not in ['admin', 'staff']")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Staff or Admin access required. Current role: {role}"
        )
    return current_user

async def require_self_or_admin(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Allow users to access/modify their own data or allow admins to access any user's data.
    
    Args:
        user_id: The user ID being accessed/modified
        current_user: The authenticated current user
    
    Raises:
        HTTPException: If the user is neither the self user nor an admin
    """
    user_role = current_user.get("role")
    current_user_id = current_user.get("uid")
    
    logger.info(f"[Auth] Self/Admin check: current user '{current_user_id}' accessing user '{user_id}', role: '{user_role}'")
    
    # Allow if user is accessing their own data or if user is admin
    if current_user_id == user_id or user_role == "admin":
        return current_user
    
    logger.warning(f"[Auth] Self/Admin access denied: user '{current_user_id}' is not accessing self or admin")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You can only access your own data. Current user: {current_user_id}, requested user: {user_id}"
    )

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .firebase_auth import firebase_auth
from typing import Optional

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = await firebase_auth.verify_token(token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"[DEBUG] Authenticated user: {user_data.get('email')} with role: {user_data.get('role')}")
    
    return user_data

def require_role(required_roles: list):
    def role_checker(current_user: dict = Depends(get_current_user)):
        user_role = current_user.get("role")
        print(f"[DEBUG] Checking role: user has '{user_role}', required: {required_roles}")
        
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_roles}, current role: {user_role}"
            )
        return current_user
    return role_checker

# Role-specific dependencies
async def require_admin(current_user: dict = Depends(get_current_user)):
    user_role = current_user.get("role")
    print(f"[DEBUG] Admin check: user role is '{user_role}'")
    
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin access required. Current role: {user_role}"
        )
    return current_user

async def require_staff_or_admin(current_user: dict = Depends(get_current_user)):
    role = current_user.get("role")
    print(f"[DEBUG] Staff/Admin check: user role is '{role}'")
    print
    if role not in ["admin", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Staff or Admin access required. Current role: {role}"
        )
    return current_user


"""
Authentication & account routes for FacilityFix (snake_case-only).

Rules
- Login: email + password only (via Firebase REST). Returns id_token + profile.
- Register:
    Admin:  first_name, last_name, birth_date, email, password, phone_number
    Staff:  first_name, last_name, birth_date, email, password, phone_number, staff_department
    Tenant: first_name, last_name, birth_date, email, password, phone_number, building_unit
- All persisted fields and API responses are snake_case.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr

# Domain enums (keep as in your project)
from ..models.user import UserRole, UserStatus  # Enum-like
# Auth/admin deps
from ..auth.firebase_auth import firebase_auth
from ..auth.dependencies import get_current_user
# DB
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
# Services & settings
from ..services.user_id_service import user_id_service
from ..core.config import settings

logger = logging.getLogger("facilityfix.routers.auth")
router = APIRouter(prefix="/auth", tags=["authentication"])


# ──────────────────────────────────────────────────────────────────────────────
# Request DTOs (snake_case-only)
# ──────────────────────────────────────────────────────────────────────────────

class EmailPasswordLogin(BaseModel):
    email: EmailStr
    password: str


class AdminRegister(BaseModel):
    first_name: str
    last_name: str
    birth_date: str
    email: EmailStr
    password: str
    phone_number: Optional[str] = None


class StaffRegister(AdminRegister):
    staff_department: str


class TenantRegister(AdminRegister):
    building_unit: str   # normalized to 'A-00005'


# ──────────────────────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────────────────────

def _model_dump(obj: Any) -> Dict[str, Any]:
    try:
        return obj.model_dump(exclude_none=True)  # Pydantic v2
    except AttributeError:
        try:
            return obj.dict(exclude_none=True)    # Pydantic v1
        except Exception:
            return dict(getattr(obj, "__dict__", {}))

def _redact_sensitive(d: Dict[str, Any]) -> Dict[str, Any]:
    redacted = dict(d or {})
    if "password" in redacted and redacted["password"] is not None:
        redacted["password"] = "***"
    return redacted

async def _get_profile_by_uid(uid: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    return await database_service.get_document(COLLECTIONS["users"], uid)

def _normalize_building_unit(raw: str) -> str:
    """
    Accepts A-5, A5, a-00005, etc. Returns 'A-00005' (letter + 5 digits).
    """
    s = (raw or "").strip().replace(" ", "").upper()
    m = re.match(r"^([A-Z])[-]?(\d{1,5})$", s)
    if not m:
        raise HTTPException(status_code=400, detail="Invalid building_unit format (expected 'A-00005')")
    return f"{m.group(1)}-{m.group(2).zfill(5)}"

async def _sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    """
    Server-side password verification using Firebase REST API.
    Returns {idToken, refreshToken, expiresIn, localId, ...}
    """
    if not settings.FIREBASE_WEB_API_KEY:
        raise HTTPException(status_code=500, detail="Missing FIREBASE_WEB_API_KEY")
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={settings.FIREBASE_WEB_API_KEY}"
    )
    payload = {"email": email, "password": password, "returnSecureToken": True}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return resp.json()


# ──────────────────────────────────────────────────────────────────────────────
# Login (email + password only)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=dict)
async def login_email_password(body: EmailPasswordLogin) -> Dict[str, Any]:
    """
    Unified login with email + password only (server-validated via Firebase REST).
    Returns id_token + profile so the frontend can render immediately.
    """
    try:
        logger.info("Login attempt: %s", _redact_sensitive(_model_dump(body)))

        token_data = await _sign_in_with_password(body.email, body.password)
        uid = token_data.get("localId")
        if not uid:
            raise HTTPException(status_code=400, detail="Login failed: missing uid")

        prof_ok, profile, _ = await _get_profile_by_uid(uid)
        profile = profile or {}

        # Optional: block suspended/inactive users
        status_val = str(profile.get("status", UserStatus.ACTIVE.value)).lower()
        if status_val in ("suspended", "inactive"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account is {status_val}. Please contact administrator."
            )

        # Response in snake_case
        return {
            "message": "login successful",
            "id_token": token_data.get("idToken"),
            "token_type": "Bearer",
            "refresh_token": token_data.get("refreshToken"),
            "expires_in": token_data.get("expiresIn", "3600"),
            "uid": uid,
            "email": body.email,
            "role": profile.get("role"),
            "status": status_val,
            "profile": profile,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Email/password login failed")
        raise HTTPException(status_code=400, detail="Login validation failed")


# ──────────────────────────────────────────────────────────────────────────────
# Registration (snake_case-only)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/register/admin", response_model=dict)
async def register_admin(body: AdminRegister) -> Dict[str, Any]:
    return await _register_user(body, UserRole.ADMIN)

@router.post("/register/staff", response_model=dict)
async def register_staff(body: StaffRegister) -> Dict[str, Any]:
    return await _register_user(body, UserRole.STAFF)

@router.post("/register/tenant", response_model=dict)
async def register_tenant(body: TenantRegister) -> Dict[str, Any]:
    return await _register_user(body, UserRole.TENANT)

async def _register_user(body: BaseModel, role: UserRole) -> Dict[str, Any]:
    # Safe log
    try:
        logger.info("Registration request role=%s payload=%s", role.value, _redact_sensitive(_model_dump(body)))
    except Exception:
        logger.debug("Could not log registration payload.", exc_info=True)

    try:
        # Generate short user_id (your service decides the format)
        user_id = await user_id_service.generate_user_id(role)

        # Create user in Firebase Auth
        firebase_user = await firebase_auth.create_user(
            email=body.email,
            password=body.password,
            display_name=f"{body.first_name} {body.last_name}",
        )

        now = datetime.now(timezone.utc)

        # Base profile (snake_case)
        profile: Dict[str, Any] = {
            "id": firebase_user["uid"],
            "user_id": user_id,
            "email": body.email,
            "first_name": body.first_name,
            "last_name": body.last_name,
            "birth_date": body.birth_date,
            "phone_number": getattr(body, "phone_number", None),
            "role": role.value,
            "status": UserStatus.ACTIVE.value,
            "created_at": now,
            "updated_at": now,
        }

        # Role-specific fields
        if role == UserRole.STAFF:
            staff_dept = getattr(body, "staff_department")
            profile.update({
                "staff_id": user_id,
                "staff_department": staff_dept,   
                
            })

        if role == UserRole.TENANT:
            normalized = _normalize_building_unit(getattr(body, "building_unit"))
            building_id, unit_id = normalized.split("-")
            profile.update({
                "building_unit": normalized,
                "building_id": building_id,
                "unit_id": unit_id,
            })

        # Custom claims (snake_case)
        claims = {
            "role": role.value,
            "user_id": user_id,
            "building_id": profile.get("building_id"),
            "unit_id": profile.get("unit_id"),
            "staff_department": profile.get("staff_department"),  
        }
        await firebase_auth.set_custom_claims(firebase_user["uid"], claims)

        # Save profile
        ok, _, err = await database_service.create_document(
            COLLECTIONS["users"], profile, document_id=firebase_user["uid"], validate=True
        )
        if not ok:
            try:
                await firebase_auth.delete_user(firebase_user["uid"])
            except Exception:
                logger.warning("Rollback Firebase user failed.", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to create user profile: {err}")

        logger.info("Registered %s uid=%s user_id=%s email=%s", role.value, firebase_user["uid"], user_id, body.email)
        return {
            "message": f"{role.value.title()} registered successfully",
            "uid": firebase_user["uid"],
            "user_id": user_id,
            "email": firebase_user["email"],
            "role": role.value,
            "profile_created": True,
            "profile": profile,  # send complete profile back
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Registration failed role=%s", role.value)
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────────
# Identity / Self-service (snake_case responses)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Return current user identity and profile info (snake_case)."""
    try:
        uid = current_user.get("uid")
        prof_ok, profile, _ = await _get_profile_by_uid(uid)

        info: Dict[str, Any] = {
            "uid": uid,
            "user_id": current_user.get("staff_id"),
            "email": current_user.get("email"),
            "role": current_user.get("role"),
            "building_id": current_user.get("building_id"),
            "unit_id": current_user.get("unit_id"),
            "testing this out": "hello",
            "staff_department": current_user.get("staff_department"),  # ✅ expose only staff_department
        }

        if prof_ok and profile:
            info.update({
                "first_name": profile.get("first_name"),
                "last_name": profile.get("last_name"),
                "birth_date": profile.get("birth_date"),
                "phone_number": profile.get("phone_number"),
                "status": profile.get("status"),
                "staff_id": profile.get("staff_id"),
                "staff_department": profile.get("staff_department"),
                "building_unit": profile.get("building_unit"),
                "created_at": profile.get("created_at"),
                "updated_at": profile.get("updated_at"),
            })

        return info

    except Exception:
        logger.exception("/auth/me failed")
        return {
            "uid": current_user.get("uid"),
            "user_id": current_user.get("user_id"),
            "email": current_user.get("email"),
            "role": current_user.get("role"),
            "error": "Could not load complete profile",
        }


@router.patch("/change-password", response_model=dict)
async def change_own_password(
    new_password: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Allow users to change their own password."""
    try:
        if not new_password:
            raise HTTPException(status_code=400, detail="New password is required")
        await firebase_auth.update_user(current_user.get("uid"), password=new_password)
        return {"message": "password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to change password for uid=%s", current_user.get("uid"))
        raise HTTPException(status_code=400, detail=f"Failed to change password: {str(e)}")


@router.post("/logout", response_model=dict)
async def logout_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Logout current user by revoking refresh tokens."""
    try:
        await firebase_auth.revoke_refresh_tokens(current_user.get("uid"))
        return {"message": "logged out successfully"}
    except Exception as e:
        logger.exception("Logout failed for uid=%s", current_user.get("uid"))
        raise HTTPException(status_code=400, detail=f"Logout failed: {str(e)}")


@router.post("/logout-all-devices", response_model=dict)
async def logout_all_devices(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Logout user from all devices by revoking all tokens & bumping claims."""
    try:
        await firebase_auth.revoke_refresh_tokens(current_user.get("uid"))
        claims = {**(current_user or {}), "tokens_valid_after": datetime.now(timezone.utc).timestamp()}
        await firebase_auth.set_custom_claims(current_user.get("uid"), claims)
        return {"message": "logged out from all devices successfully"}
    except Exception as e:
        logger.exception("Logout-all-devices failed for uid=%s", current_user.get("uid"))
        raise HTTPException(status_code=400, detail=f"Logout from all devices failed: {str(e)}")

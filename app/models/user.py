from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime
import re

# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    TENANT = "tenant"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class StaffDepartment(str, Enum):
    MAINTENANCE = "maintenance"
    CARPENTRY   = "carpentry"
    PLUMBING    = "plumbing"
    ELECTRICAL  = "electrical"
    MASONRY     = "masonry"


# ──────────────────────────────────────────────────────────────────────────────
# Legacy login payloads (kept for back-compat with old screens)
# ──────────────────────────────────────────────────────────────────────────────

class AdminLogin(BaseModel):
    userEmail: EmailStr
    userId: str = Field(..., description="Admin user ID (e.g., A-0001)")
    userPassword: str


class StaffLogin(BaseModel):
    userEmail: EmailStr
    userId: str = Field(..., description="Staff user ID (e.g., S-0001)")
    userDepartment: str = Field(..., description="Staff department")
    userPassword: str


class TenantLogin(BaseModel):
    userEmail: EmailStr
    userId: str = Field(..., description="Tenant user ID (e.g., T-0001)")
    buildingUnitNo: str = Field(..., description="Building unit (e.g., A-01)")
    userPassword: str


# ──────────────────────────────────────────────────────────────────────────────
# Registration payloads — camelCase for app, fold legacy to these keys
# ──────────────────────────────────────────────────────────────────────────────

class AdminCreate(BaseModel):
    firstName: str = Field(..., min_length=1)
    lastName:  str = Field(..., min_length=1)
    email: EmailStr
    password: str   = Field(..., min_length=6)
    phoneNumber: str  # REQUIRED
    birthDate: str = Field(..., description="Birth date as YYYY-MM-DD")  # REQUIRED

    @root_validator(pre=True)
    def _fold_legacy(cls, v: Dict) -> Dict:
        v.setdefault("firstName", v.get("first_name"))
        v.setdefault("lastName", v.get("last_name"))
        v.setdefault("email", v.get("userEmail") or v.get("email"))
        v.setdefault("password", v.get("userPassword") or v.get("password"))
        v.setdefault("phoneNumber", v.get("contactNumber") or v.get("phone_number"))
        v.setdefault("birthDate", v.get("birth_date") or v.get("birthDate"))
        return v


class StaffCreate(BaseModel):
    firstName: str = Field(..., min_length=1)
    lastName:  str = Field(..., min_length=1)
    email: EmailStr
    password: str   = Field(..., min_length=6)
    staffDepartment: Optional[StaffDepartment] = None  # Legacy single department
    staffDepartments: Optional[List[str]] = []  # New: Multiple departments
    phoneNumber: str  # REQUIRED
    birthDate: str = Field(..., description="Birth date as YYYY-MM-DD")  # REQUIRED

    @root_validator(pre=True)
    def _fold_department_keys(cls, v: Dict) -> Dict:
        v.setdefault("firstName", v.get("first_name"))
        v.setdefault("lastName", v.get("last_name"))
        v.setdefault("email", v.get("userEmail") or v.get("email"))
        v.setdefault("password", v.get("userPassword") or v.get("password"))
        v.setdefault("phoneNumber", v.get("contactNumber") or v.get("phone_number"))
        v.setdefault("birthDate", v.get("birth_date") or v.get("birthDate"))

        # Handle both single and multiple departments
        dept = v.get("staffDepartment") or v.get("department") or v.get("staff_department") or v.get("classification")
        depts = v.get("staffDepartments") or v.get("departments") or v.get("staff_departments")
        
        # If single department provided, convert to array for staffDepartments
        if dept and not depts:
            v["staffDepartments"] = [dept]
            v["staffDepartment"] = dept
        elif depts:
            v["staffDepartments"] = depts if isinstance(depts, list) else [depts]
            # Set single department as first in list for backward compatibility
            if not dept and depts:
                v["staffDepartment"] = depts[0] if isinstance(depts, list) else depts
        
        return v


class TenantCreate(BaseModel):
    firstName: str = Field(..., min_length=1)
    lastName:  str = Field(..., min_length=1)
    email: EmailStr
    password: str   = Field(..., min_length=6)
    phoneNumber: str  # REQUIRED
    birthDate: str = Field(..., description="Birth date as YYYY-MM-DD")  # REQUIRED
    buildingUnit: str = Field(..., description="Normalized as 'A-00005'")

    @root_validator(pre=True)
    def _map_bu_variants(cls, v: Dict) -> Dict:
        v.setdefault("firstName", v.get("first_name"))
        v.setdefault("lastName", v.get("last_name"))
        v.setdefault("email", v.get("userEmail") or v.get("email"))
        v.setdefault("password", v.get("userPassword") or v.get("password"))
        v.setdefault("phoneNumber", v.get("contactNumber") or v.get("phone_number"))
        v.setdefault("birthDate", v.get("birth_date") or v.get("birthDate"))

        bu = v.get("buildingUnit") or v.get("building_unit") or v.get("buildingUnitId") or v.get("buildingUnitNo")
        if bu is not None:
            v["buildingUnit"] = bu
        return v

    @validator("buildingUnit", pre=True)
    def _normalize_building_unit(cls, raw: str) -> str:
        if not isinstance(raw, str):
            raise ValueError("buildingUnit must be a string")
        s = raw.strip().upper()
        m = re.match(r"^([A-Z])\-?(\d{1,5})$", s)
        if not m:
            raise ValueError("buildingUnit must be like 'A-5' or 'A-00005'")
        letter = m.group(1)
        unit   = m.group(2).zfill(5)
        return f"{letter}-{unit}"


# ──────────────────────────────────────────────────────────────────────────────
# Generic auth/login
# ──────────────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    identifier: str = Field(..., description="Email or User ID (e.g., T-0001)")
    password: str


# ──────────────────────────────────────────────────────────────────────────────
# Core user models (camelCase for app)
# ──────────────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    firstName: str
    lastName: str
    phoneNumber: str
    role: UserRole
    buildingId: Optional[str] = None
    unitId: Optional[str] = None
    staffDepartment: Optional[str] = None  # Legacy single department
    staffDepartments: Optional[List[str]] = []  # New: Multiple departments
    departments: Optional[List[str]] = []  # General purpose departments
    staffId: Optional[str] = None
    buildingUnit: Optional[str] = None
    birthDate: str


class UserResponse(BaseModel):
    uid: str
    userId: str
    email: str
    firstName: str
    lastName: str
    role: UserRole
    phoneNumber: str
    buildingId: Optional[str] = None
    unitId: Optional[str] = None
    staffDepartment: Optional[str] = None  # Legacy single department
    staffDepartments: Optional[List[str]] = []  # New: Multiple departments
    departments: Optional[List[str]] = []  # General purpose departments
    staffId: Optional[str] = None
    buildingUnit: Optional[str] = None
    status: Optional[UserStatus] = UserStatus.ACTIVE
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    birthDate: str


class UserUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phoneNumber: Optional[str] = None
    buildingId: Optional[str] = None
    unitId: Optional[str] = None
    staffDepartment: Optional[str] = None  # Legacy single department
    staffDepartments: Optional[List[str]] = None  # New: Multiple departments
    departments: Optional[List[str]] = None  # General purpose departments
    buildingUnit: Optional[str] = None
    birthDate: Optional[str] = None

    @validator("buildingUnit")
    def _validate_building_unit_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            vs = v.strip().upper()
            if not vs:
                raise ValueError("buildingUnit, if provided, must be non-empty")
            return vs
        return v


class UserStatusUpdate(BaseModel):
    status: UserStatus


class PasswordChange(BaseModel):
    newPassword: str = Field(..., min_length=6, description="New password (minimum 6 characters)")


class UserSearchFilters(BaseModel):
    role: Optional[UserRole] = None
    buildingId: Optional[str] = None
    status: Optional[UserStatus] = None
    staffDepartment: Optional[str] = None
    searchTerm: Optional[str] = Field(None, description="Search in name, email, or department")


class UserListResponse(BaseModel):
    users: List[UserResponse]
    totalCount: int
    page: int
    pageSize: int
    totalPages: int


class BulkUserOperation(BaseModel):
    userIds: List[str]
    operation: str  # "activate", "deactivate", "delete"


class UserStatistics(BaseModel):
    totalUsers: int
    byRole: dict
    byStatus: dict
    byBuilding: dict
    recentRegistrations: int  # in the last 30 days


class UserProfileComplete(BaseModel):
    """Complete user profile with Firebase and Firestore data"""
    uid: str
    userId: str
    email: str
    emailVerified: bool
    firstName: str
    lastName: str
    phoneNumber: str
    role: UserRole
    status: UserStatus
    buildingId: Optional[str] = None
    unitId: Optional[str] = None
    staffDepartment: Optional[str] = None  # Legacy single department
    staffDepartments: Optional[List[str]] = []  # New: Multiple departments
    departments: Optional[List[str]] = []  # General purpose departments
    staffId: Optional[str] = None
    buildingUnit: Optional[str] = None
    birthDate: str
    lastSignIn: Optional[datetime] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    firebaseMetadata: Optional[dict] = None

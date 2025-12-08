#routers/users
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from ..models.user import UserResponse, UserRole
from ..models.database_models import UserProfile
from ..auth.dependencies import require_admin, require_staff_or_admin, get_current_user
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..auth.firebase_auth import firebase_auth
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone

router = APIRouter(prefix="/users", tags=["user-management"])

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    birth_date: Optional[str] = None  # Birth date in YYYY-MM-DD format
    department: Optional[str] = None  # Legacy single department
    departments: Optional[List[str]] = None  # New: Multiple departments
    staff_department: Optional[str] = None  # Legacy single staff department
    staff_departments: Optional[List[str]] = None  # New: Multiple staff departments
    building_id: Optional[str] = None
    unit_id: Optional[str] = None

class UserStatusUpdate(BaseModel):
    status: str  # active, suspended, inactive

class PasswordChange(BaseModel):
    new_password: str

class UserSearchFilters(BaseModel):
    role: Optional[UserRole] = None
    building_id: Optional[str] = None
    status: Optional[str] = None
    department: Optional[str] = None

@router.get("/staff", response_model=List[dict])
async def get_staff_members(
    department: Optional[str] = Query(None, description="Filter by department"),
    available_only: bool = Query(False, description="Only return available staff"),
    schedule: Optional[str] = Query(None, description="Optional date to filter availability (YYYY-MM-DD)"),
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get all staff members with optional filtering"""
    try:
        # Build filters to get staff members
        filters = [('role', '==', 'staff')]
        
        if department:
            filters.append(('staff_department', '==', department))
        
        if available_only:
            filters.append(('status', '==', 'active'))
        
        # Query staff from Firestore
        success, staff_members, error = await database_service.query_documents(
            COLLECTIONS['users'], 
            filters=filters
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve staff members: {error}"
            )
        
        # Format staff data for frontend
        formatted_staff = []
        for staff in staff_members:
            # Get departments, prioritize new multi-select fields
            staff_depts = staff.get("staff_departments") or staff.get("departments")
            if not staff_depts:
                # Fallback to legacy single department
                single_dept = staff.get("staff_department") or staff.get("department")
                staff_depts = [single_dept] if single_dept else []
            
            # When schedule parameter is provided, further check daily availability and day-off requests
            if schedule:
                try:
                    # Parse requested date
                    from datetime import datetime, timedelta
                    requested_date = datetime.strptime(schedule, '%Y-%m-%d').date()
                    week_start = requested_date - timedelta(days=requested_date.weekday())
                    week_start_str = week_start.strftime('%Y-%m-%d')

                    # Determine staff unique id to query availability and day off (user's firebase uid or staff_id)
                    staff_uid = staff.get('id') or staff.get('_doc_id') or staff.get('user_id') or staff.get('staff_id')

                    # Query weekly availability for the week
                    avail_filters = [('staff_id', '==', staff_uid), ('week_start_date', '==', week_start_str)]
                    a_success, a_docs, a_error = await database_service.query_documents(COLLECTIONS['staff_availability'], filters=avail_filters, limit=1)
                    if a_success and a_docs:
                        avail_doc = a_docs[0]
                        day_name = requested_date.strftime('%A').lower()
                        if not avail_doc.get(day_name, True):
                            # Staff is unavailable for the requested date
                            continue

                    # Query day off requests for that date/status
                    dor_filters = [('staff_id', '==', staff_uid), ('request_date', '==', schedule)]
                    dor_success, dor_docs, dor_error = await database_service.query_documents(COLLECTIONS['day_off_requests'], filters=dor_filters)
                    if dor_success and dor_docs and len(dor_docs) > 0:
                        # If any day off requests exist for that date and not in 'rejected' status, exclude staff
                        blocked = False
                        for d in dor_docs:
                            if d.get('status') in ['pending', 'approved']:
                                blocked = True
                                break
                        if blocked:
                            continue
                except Exception:
                    # If any error during checks, fallback to include staff
                    pass

            formatted_staff.append({
                "id": staff.get("id") or staff.get("_doc_id"),  # Firebase UID
                "uid": staff.get("id") or staff.get("_doc_id"),  # Firebase UID (explicit field for clarity)
                "user_id": staff.get("user_id"),
                "first_name": staff.get("first_name", ""),
                "last_name": staff.get("last_name", ""),
                "email": staff.get("email", ""),
                "staff_id": staff.get("staff_id", ""),
                "staff_department": staff.get("staff_department") or staff.get("department"),  # Legacy
                "staff_departments": staff_depts,  # New multi-select
                "departments": staff_depts,  # General purpose
                "phone_number": staff.get("phone_number", ""),
                "status": staff.get("status", "active"),
                "building_id": staff.get("building_id"),
            })
        
        return formatted_staff
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving staff members: {str(e)}"
        )

@router.get("/", response_model=List[dict])
async def get_users(
    role: Optional[str] = Query(None, description="Filter by user role"),
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    status: Optional[str] = Query(None, description="Filter by user status"),
    department: Optional[str] = Query(None, description="Filter by department"),
    limit: Optional[int] = Query(50, description="Maximum number of users to return"),
):
    """Get all users with optional filtering"""
    try:
        # Build filters
        filters = []
        if role:
            filters.append(('role', '==', role))
        if building_id:
            filters.append(('building_id', '==', building_id))
        if status:
            filters.append(('status', '==', status))
        if department:
            filters.append(('department', '==', department))
        
        # Query users from Firestore
        success, users, error = await database_service.query_collection(
            COLLECTIONS['users'], 
            filters=filters if filters else None,
            limit=limit
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve users: {error}"
            )
        
        return users
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)  # Allow any authenticated user
):
    """
    Get a specific user whose user_id == {user_id} (e.g., T-0001).
    Tenants can only access their own data. Staff and admin can access any user.
    """
    try:
        current_user_id = current_user.get('uid')
        current_user_role = current_user.get('role', '').lower()
        
        # Get the user data first
        success, user_data, error = await database_service.get_document(
            COLLECTIONS["users"], user_id
        )

        # If not found by doc-id, query by the "user_id" field
        if not success or not user_data:
            q_success, docs, q_error = await database_service.query_documents(
                COLLECTIONS["users"],
                filters=[("user_id", "==", user_id)],
                limit=1,
            )
            if not q_success or not docs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User not found: Document '{user_id}' or field user_id == '{user_id}' not found in 'users'"
                )
            user_data = docs[0]
        
        target_firebase_uid = user_data.get('id')  # Firebase UID stored in 'id' field
        
        if current_user_role == 'tenant':
            # Tenant can only access their own data
            if current_user_id != target_firebase_uid and current_user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenants can only access their own user data"
                )
        elif current_user_role not in ['staff', 'admin']:
            # Unknown role - deny access
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Staff and admin can access any user data (no additional check needed)

        # Attach Firebase Auth info (by email first, fallback to Firebase UID in 'id')
        try:
            fb_user = None
            email = user_data.get("email")
            if email:
                fb_user = await firebase_auth.get_user_by_email(email)
            elif user_data.get("id"):
                fb_user = await firebase_auth.get_user(user_data["id"])

            if fb_user:
                user_data["firebase_uid"] = fb_user.uid
                user_data["email_verified"] = fb_user.email_verified
                user_data["last_sign_in"] = getattr(fb_user.user_metadata, "last_sign_in_time", None)
        except Exception:
            pass  # Firebase data is optional

        return user_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user: {str(e)}"
        )

@router.put("/{user_id}")
async def update_user(
    user_id: str,
    user_update: UserUpdate,
):
    """Update the user whose `user_id` == {user_id} (e.g., T-0001)."""
    try:
        print(f"[update_user] Received request to update user: {user_id}")
        print(f"[update_user] Update payload: {user_update.dict(exclude_unset=True)}")
        
        # Build update payload from provided fields only
        update_data = {}
        if user_update.first_name is not None:
            update_data["first_name"] = user_update.first_name
        if user_update.last_name is not None:
            update_data["last_name"] = user_update.last_name
        if user_update.phone_number is not None:
            update_data["phone_number"] = user_update.phone_number
        if user_update.birth_date is not None:
            update_data["birth_date"] = user_update.birth_date
            # Also update birthdate field for backward compatibility
            update_data["birthdate"] = user_update.birth_date

        # Handle departments - support both legacy single and new multiple
        if user_update.departments is not None:
            update_data["departments"] = user_update.departments
            # Also update legacy department field with first value for backward compatibility
            if user_update.departments:
                update_data["department"] = user_update.departments[0]
            else:
                update_data["department"] = None
        elif user_update.department is not None:
            # If only legacy department provided, update both fields
            update_data["department"] = user_update.department
            update_data["departments"] = [user_update.department] if user_update.department else []
        
        # Handle staff departments - support both legacy single and new multiple
        if user_update.staff_departments is not None:
            update_data["staff_departments"] = user_update.staff_departments
            # Also update legacy staff_department field with first value for backward compatibility
            if user_update.staff_departments:
                update_data["staff_department"] = user_update.staff_departments[0]
            else:
                update_data["staff_department"] = None
        elif user_update.staff_department is not None:
            # If only legacy staff_department provided, update both fields
            update_data["staff_department"] = user_update.staff_department
            update_data["staff_departments"] = [user_update.staff_department] if user_update.staff_department else []
        
        if user_update.building_id is not None:
            update_data["building_id"] = user_update.building_id
        if user_update.unit_id is not None:
            update_data["unit_id"] = user_update.unit_id

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided to update."
            )

        update_data["updated_at"] = datetime.now(timezone.utc)
        
        print(f"[update_user] Final update_data: {update_data}")

        # ── Resolve the actual Firestore document id ───────────────────────────
        target_doc_id = None

        # 1) If a document is literally named T-0001, allow updating it
        by_id_ok, by_id_doc, _ = await database_service.get_document(
            COLLECTIONS["users"], user_id
        )
        if by_id_ok and by_id_doc:
            target_doc_id = user_id
        else:
            # 2) Otherwise query by the 'user_id' field
            q_ok, docs, q_err = await database_service.query_documents(
                COLLECTIONS["users"],
                filters=[("user_id", "==", user_id)],
                limit=2,
            )
            if not q_ok:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Query failed: {q_err}"
                )
            if not docs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User not found for user_id '{user_id}'."
                )
            if len(docs) > 1:
                # Safety: enforce uniqueness of user_id before writing
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Multiple users found with user_id '{user_id}'. Please resolve duplicates."
                )

            target_doc_id = docs[0].get("_doc_id") or docs[0].get("id")
            if not target_doc_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Resolved user document has no Firestore id."
                )

        # ── Perform the update using the resolved doc id ───────────────────────
        print(f"[update_user] Updating Firestore document: {target_doc_id}")
        success, error = await database_service.update_document(
            COLLECTIONS["users"], target_doc_id, update_data
        )
        if not success:
            print(f"[update_user] Update failed: {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update user: {error}"
            )

        print(f"[update_user] Update successful for user: {user_id}")
        return {
            "message": "User updated successfully",
            "user_id": user_id,
            "doc_id": target_doc_id,
            "updated_fields": list(update_data.keys()),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )


@router.patch("/{user_id}/status")
async def update_user_status(
    user_id: str,
    status_update: UserStatusUpdate,
    current_user: dict = Depends(require_admin),
):
    """Update user status (active, suspended, inactive) for the user whose user_id == {user_id}."""
    try:
        valid_statuses = {"active", "suspended", "inactive"}
        if status_update.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {sorted(valid_statuses)}"
            )

        # Resolve the actual Firestore document id
        target_doc_id = None
        user_doc = None

        by_id_ok, by_id_doc, _ = await database_service.get_document(
            COLLECTIONS["users"], user_id
        )
        if by_id_ok and by_id_doc:
            target_doc_id = user_id
            user_doc = by_id_doc
        else:
            q_ok, docs, q_err = await database_service.query_documents(
                COLLECTIONS["users"], filters=[("user_id", "==", user_id)], limit=2
            )
            if not q_ok:
                raise HTTPException(status_code=500, detail=f"Query failed: {q_err}")
            if not docs:
                raise HTTPException(status_code=404, detail=f"User not found for user_id '{user_id}'.")
            if len(docs) > 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"Multiple users found with user_id '{user_id}'. Please resolve duplicates."
                )
            user_doc = docs[0]
            target_doc_id = user_doc.get("_doc_id") or user_doc.get("id")

        update_data = {
            "status": status_update.status,
            "updated_at": datetime.now(timezone.utc),
        }

        success, err = await database_service.update_document(
            COLLECTIONS["users"], target_doc_id, update_data
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update user status: {err}"
            )

        return {
            "message": f"User status updated to {status_update.status}",
            "user_id": user_id,
            "doc_id": target_doc_id,
            "previous_status": user_doc.get("status") if isinstance(user_doc, dict) else None,
            "new_status": status_update.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user status: {str(e)}"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    permanent: bool = Query(False, description="Permanently delete user (default: deactivate)"),
    current_user: dict = Depends(require_admin),
):
    """Deactivate or permanently delete the user whose user_id == {user_id} (e.g., T-0001)."""
    try:
        # ── Resolve Firestore doc id by doc-id first, then by user_id field ──
        target_doc_id = None
        user_doc = None

        by_id_ok, by_id_doc, _ = await database_service.get_document(
            COLLECTIONS["users"], user_id
        )
        if by_id_ok and by_id_doc:
            target_doc_id = user_id
            user_doc = by_id_doc
        else:
            q_ok, docs, q_err = await database_service.query_documents(
                COLLECTIONS["users"], filters=[("user_id", "==", user_id)], limit=2
            )
            if not q_ok:
                raise HTTPException(status_code=500, detail=f"Query failed: {q_err}")
            if not docs:
                raise HTTPException(status_code=404, detail=f"User not found for user_id '{user_id}'.")
            if len(docs) > 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"Multiple users found with user_id '{user_id}'. Please resolve duplicates first."
                )
            user_doc = docs[0]
            target_doc_id = user_doc.get("_doc_id") or user_doc.get("id")

        # ── Permanent delete ───────────────────────────────────────────────────
        if permanent:
            success, err = await database_service.delete_document(
                COLLECTIONS["users"], target_doc_id
            )
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to delete user: {err}"
                )

            # Best-effort: also delete from Firebase Auth (by UID or email)
            try:
                firebase_uid = user_doc.get("id")  # your schema stores Firebase UID in 'id'
                if not firebase_uid and user_doc.get("email"):
                    fb_user = await firebase_auth.get_user_by_email(user_doc["email"])
                    if fb_user:
                        firebase_uid = fb_user.uid
                if firebase_uid:
                    await firebase_auth.delete_user(firebase_uid)
            except Exception:
                # Firebase deletion is optional
                pass

            return {"message": "User permanently deleted", "user_id": user_id, "doc_id": target_doc_id}

        # ── Soft delete (deactivate) ───────────────────────────────────────────
        update_data = {
            "status": "inactive",
            "updated_at": datetime.now(timezone.utc),
        }
        success, err = await database_service.update_document(
            COLLECTIONS["users"], target_doc_id, update_data
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to deactivate user: {err}"
            )

        return {"message": "User deactivated", "user_id": user_id, "doc_id": target_doc_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}"
        )

@router.patch("/{user_id}/password")
async def change_user_password(
    user_id: str,
    password_change: PasswordChange,
    current_user: dict = Depends(require_admin)
):
    """Change user password (Admin only)"""
    try:
        # Update password in Firebase Auth
        firebase_auth.update_user(user_id, password=password_change.new_password)
        
        return {"message": "Password updated successfully", "user_id": user_id}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update password: {str(e)}"
        )

@router.post("/bulk/status")
async def bulk_update_user_status(
    user_ids: List[str],
    new_status: str,
    current_user: dict = Depends(require_admin)
):
    """Bulk update user status"""
    try:
        valid_statuses = ['active', 'suspended', 'inactive']
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        
        results = []
        update_data = {
            'status': new_status,
            'updated_at': datetime.utcnow()
        }
        
        for user_id in user_ids:
            try:
                success, error = await database_service.update_document(
                    COLLECTIONS['users'],
                    user_id,
                    update_data
                )
                
                results.append({
                    "user_id": user_id,
                    "success": success,
                    "error": error if not success else None
                })
            except Exception as e:
                results.append({
                    "user_id": user_id,
                    "success": False,
                    "error": str(e)
                })
        
        successful_updates = sum(1 for r in results if r["success"])
        
        return {
            "message": f"Bulk update completed. {successful_updates}/{len(user_ids)} users updated.",
            "new_status": new_status,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk update: {str(e)}"
        )

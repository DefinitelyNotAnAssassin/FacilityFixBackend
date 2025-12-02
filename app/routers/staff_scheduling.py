from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, date, timedelta
from ..models.staff_scheduling_models import (
    WeeklyAvailabilityRequest, StatusUpdateRequest, DayOffRequestSubmission,
    StaffScheduleOverview, StaffAssignmentRequest, AvailabilityStatus, DayOffStatus,
    BulkApproveDayOffRequest, BulkRejectDayOffRequest
)
from ..auth.dependencies import require_staff_or_admin, require_admin, get_current_user
from ..services.staff_scheduling_service import staff_scheduling_service
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..services.notification_manager import notification_manager

router = APIRouter(prefix="/staff-scheduling", tags=["staff-scheduling"])

# ──────────────────────────────────────────────────────────────────────────────
# Staff Availability Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/availability/submit")
async def submit_weekly_availability(
    availability_request: WeeklyAvailabilityRequest,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Submit weekly availability schedule"""
    try:
        staff_id = current_user.get('uid')
        
        success, doc_id, error = await staff_scheduling_service.submit_weekly_availability(
            staff_id, availability_request.dict()
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to submit availability: {error}"
            )
        
        return {
            "message": "Weekly availability submitted successfully",
            "availability_id": doc_id,
            "week_start": availability_request.week_start_date
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting availability: {str(e)}"
        )

@router.get("/availability/{staff_id}")
async def get_staff_availability(
    staff_id: str,
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD)"),
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get staff availability for a specific week"""
    try:
        # Staff members access their own data via uid from token, admins can access any staff_id
        current_user_id = current_user.get('uid')
        current_user_role = current_user.get('role', '').lower()

        # Use the staff_id parameter if admin, otherwise use current user's uid
        actual_staff_id = staff_id if current_user_role == 'admin' else current_user_id
        
        # If no week specified, get current week
        if not week_start:
            today = date.today()
            week_start_date = today - timedelta(days=today.weekday())
            week_start = week_start_date.strftime('%Y-%m-%d')
        
        filters = [
            ('staff_id', '==', actual_staff_id),
            ('week_start_date', '==', week_start)
        ]
        
        success, docs, error = await database_service.query_documents(
            COLLECTIONS['staff_availability'], 
            filters=filters,
            limit=1
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve availability: {error}"
            )
        
        if not docs:
            # Return default availability if none found
            return {
                "staff_id": actual_staff_id,
                "week_start_date": week_start,
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False,
                "status": "not_submitted"
            }
        
        return docs[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving availability: {str(e)}"
        )

# ──────────────────────────────────────────────────────────────────────────────
# Real-time Status Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/status/update")
async def update_real_time_status(
    status_request: StatusUpdateRequest,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Update real-time status of staff member"""
    try:
        staff_id = current_user.get('uid')
        
        success, doc_id, error = await staff_scheduling_service.update_real_time_status(
            staff_id, 
            status_request.status,
            status_request.location,
            status_request.notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update status: {error}"
            )
        
        return {
            "message": "Status updated successfully",
            "status": status_request.status.value,
            "location": status_request.location,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating status: {str(e)}"
        )

@router.get("/status/{staff_id}")
async def get_staff_real_time_status(
    staff_id: str,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get real-time status of a staff member"""
    try:
        current_user_id = current_user.get('uid')
        current_user_role = current_user.get('role', '').lower()
        
        # Use the staff_id parameter if admin, otherwise use current user's uid
        actual_staff_id = staff_id if current_user_role == 'admin' else current_user_id
        
        filters = [('staff_id', '==', actual_staff_id)]
        success, docs, error = await database_service.query_documents(
            COLLECTIONS['staff_real_time_status'],
            filters=filters,
            limit=1
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve status: {error}"
            )
        
        if not docs:
            # Return default status if none found
            return {
                "staff_id": actual_staff_id,
                "current_status": "available",
                "workload_level": "low",
                "active_task_count": 0,
                "is_scheduled_on_duty": True,
                "is_currently_available": True,
                "auto_assign_eligible": True,
                "last_activity_at": None
            }
        
        return docs[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving status: {str(e)}"
        )

# ──────────────────────────────────────────────────────────────────────────────
# Day Off Request Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/day-off/request")
async def submit_day_off_request(
    request: DayOffRequestSubmission,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Submit a day-off request"""
    try:
        staff_id = current_user.get('uid')
        
        success, doc_id, error = await staff_scheduling_service.submit_day_off_request(
            staff_id, request.dict()
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to submit day-off request: {error}"
            )
        
        return {
            "message": "Day-off request submitted successfully",
            "request_id": doc_id,
            "request_date": request.request_date,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting day-off request: {str(e)}"
        )

@router.get("/day-off/requests")
async def get_day_off_requests(
    staff_id: Optional[str] = Query(None, description="Filter by staff ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get day-off requests"""
    try:
        current_user_id = current_user.get('uid')
        current_user_role = current_user.get('role', '').lower()
        
        # Build filters
        filters = []
        
        # Staff can only see their own requests
        if current_user_role == 'staff':
            filters.append(('staff_id', '==', current_user_id))
        elif staff_id:  # Admin can filter by specific staff
            filters.append(('staff_id', '==', staff_id))
        
        if status_filter:
            filters.append(('status', '==', status_filter))
        
        success, docs, error = await database_service.query_documents(
            COLLECTIONS['day_off_requests'],
            filters=filters if filters else None
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve day-off requests: {error}"
            )

        enriched_docs = []
        for doc in (docs or []):
            staff_uid = doc.get('staff_id')
            if staff_uid:
                # Fetch staff member's details from users collection
                success_user, user_docs, _ = await database_service.query_documents(
                    COLLECTIONS['users'],
                    filters=[('uid', '==', staff_uid)]
                )
                
                if success_user and user_docs:
                    user = user_docs[0]
                    # Add staff_name and department to the day-off request
                    doc['staff_name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    doc['department'] = user.get('department', 'N/A')
            
            enriched_docs.append(doc)
        
        return {
            "requests": enriched_docs,
            "total_count": len(enriched_docs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving day-off requests: {str(e)}"
        )

@router.patch("/day-off/requests/{request_id}/approve")
async def approve_day_off_request(
    request_id: str,
    admin_notes: Optional[str] = None,
    current_user: dict = Depends(require_admin)
):
    """Approve a day-off request (Admin only)"""
    try:
        admin_id = current_user.get('uid')
        
        update_data = {
            'status': DayOffStatus.APPROVED.value,
            'approved_by': admin_id,
            'approved_at': datetime.utcnow(),
            'admin_notes': admin_notes,
            'updated_at': datetime.utcnow()
        }
        
        success, error = await database_service.update_document(
            COLLECTIONS['day_off_requests'],
            request_id,
            update_data
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to approve request: {error}"
            )
        
        return {
            "message": "Day-off request approved successfully",
            "request_id": request_id,
            "approved_by": admin_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving day-off request: {str(e)}"
        )

@router.patch("/day-off/requests/{request_id}/reject")
async def reject_day_off_request(
    request_id: str,
    rejection_reason: str,
    current_user: dict = Depends(require_admin)
):
    """Reject a day-off request (Admin only)"""
    try:
        admin_id = current_user.get('uid')
        
        update_data = {
            'status': DayOffStatus.REJECTED.value,
            'approved_by': admin_id,
            'approved_at': datetime.utcnow(),
            'rejection_reason': rejection_reason,
            'updated_at': datetime.utcnow()
        }
        
        success, error = await database_service.update_document(
            COLLECTIONS['day_off_requests'],
            request_id,
            update_data
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to reject request: {error}"
            )
        
        return {
            "message": "Day-off request rejected",
            "request_id": request_id,
            "rejection_reason": rejection_reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting day-off request: {str(e)}"
        )

# Bulk Approve/Reject Endpoints
@router.patch("/day-off/bulk/approve")
async def bulk_approve_day_off_requests(
    request: BulkApproveDayOffRequest,
    current_user: dict = Depends(require_admin)
):
    """Bulk approve multiple day-off requests (Admin only)"""
    try:
        if not request.request_ids or len(request.request_ids) == 0:
            raise HTTPException(status_code=400, detail="No requests provided for approval")
        
        admin_id = current_user.get('uid')
        approved_count = 0
        failed_count = 0
        errors = []
        
        for request_id in request.request_ids:
            try:
                success_query, query_docs, query_error = await database_service.query_documents(
                    COLLECTIONS['day_off_requests'],
                    filters=[('formatted_id', '==', request_id)]
                )
                
                if not success_query or not query_docs:
                    failed_count += 1
                    errors.append(f"Request {request_id}: Document {request_id} not found in day_off_requests")
                    continue
                
                # Get the actual Firestore document ID
                doc = query_docs[0]
                actual_doc_id = doc.get('_doc_id')
                
                if not actual_doc_id:
                    failed_count += 1
                    errors.append(f"Request {request_id}: Could not determine document ID")
                    continue

                update_data = {
                    'status': DayOffStatus.APPROVED.value,
                    'approved_by': admin_id,
                    'approved_at': datetime.utcnow(),
                    'admin_notes': request.admin_notes,
                    'updated_at': datetime.utcnow()
                }
                
                success, error = await database_service.update_document(
                    COLLECTIONS['day_off_requests'],
                    actual_doc_id,
                    update_data
                )
                
                if not success:
                    failed_count += 1
                    errors.append(f"Request {request_id}: {error}")
                    continue
                
                # Notify staff member about approval
                staff_id = doc.get('staff_id')
                if staff_id:
                    try:
                        await notification_manager.notify_day_off_approved(
                            request_id=request_id,
                            staff_id=staff_id,
                            approved_by=admin_id
                        )
                    except:
                        pass  # Notification failure shouldn't block approval
                
                approved_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"Request {request_id}: {str(e)}")
        
        return {
            "approved_count": approved_count,
            "failed_count": failed_count,
            "errors": errors,
            "message": f"Bulk approval completed: {approved_count} approved, {failed_count} failed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during bulk approval: {str(e)}"
        )

@router.patch("/day-off/bulk/reject")
async def bulk_reject_day_off_requests(
    request: BulkRejectDayOffRequest,
    current_user: dict = Depends(require_admin)
):
    """Bulk reject multiple day-off requests (Admin only)"""
    try:
        if not request.request_ids or len(request.request_ids) == 0:
            raise HTTPException(status_code=400, detail="No requests provided for rejection")
        
        if not request.rejection_reason or len(request.rejection_reason.strip()) == 0:
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        admin_id = current_user.get('uid')
        rejected_count = 0
        failed_count = 0
        errors = []
        
        for request_id in request.request_ids:
            try:
                success_query, query_docs, query_error = await database_service.query_documents(
                    COLLECTIONS['day_off_requests'],
                    filters=[('formatted_id', '==', request_id)]
                )
                
                if not success_query or not query_docs:
                    failed_count += 1
                    errors.append(f"Request {request_id}: Document {request_id} not found in day_off_requests")
                    continue
                
                # Get the actual Firestore document ID
                doc = query_docs[0]
                actual_doc_id = doc.get('_doc_id')
                
                if not actual_doc_id:
                    failed_count += 1
                    errors.append(f"Request {request_id}: Could not determine document ID")
                    continue

                update_data = {
                    'status': DayOffStatus.REJECTED.value,
                    'approved_by': admin_id,
                    'approved_at': datetime.utcnow(),
                    'rejection_reason': request.rejection_reason,
                    'updated_at': datetime.utcnow()
                }
                
                success, error = await database_service.update_document(
                    COLLECTIONS['day_off_requests'],
                    actual_doc_id,
                    update_data
                )
                
                if not success:
                    failed_count += 1
                    errors.append(f"Request {request_id}: {error}")
                    continue
                
                # Notify staff member about rejection
                staff_id = doc.get('staff_id')
                if staff_id:
                    try:
                        await notification_manager.notify_day_off_rejected(
                            request_id=request_id,
                            staff_id=staff_id,
                            rejected_by=admin_id,
                            reason=request.rejection_reason
                        )
                    except:
                        pass  # Notification failure shouldn't block rejection
                
                rejected_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append(f"Request {request_id}: {str(e)}")
        
        return {
            "rejected_count": rejected_count,
            "failed_count": failed_count,
            "errors": errors,
            "message": f"Bulk rejection completed: {rejected_count} rejected, {failed_count} failed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during bulk rejection: {str(e)}"
        )
    
# ──────────────────────────────────────────────────────────────────────────────
# Smart Assignment Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/eligible-staff")
async def get_eligible_staff(
    departments: List[str] = Query(..., description="Required departments"),
    location: Optional[str] = Query(None, description="Task location"),
    priority: str = Query("medium", description="Task priority"),
    current_user: dict = Depends(require_staff_or_admin)
):
    """Get list of eligible staff for task assignment"""
    try:
        eligible_staff = await staff_scheduling_service.get_eligible_staff_for_assignment(
            departments, location, priority
        )
        
        return {
            "eligible_staff": [staff.dict() for staff in eligible_staff],
            "total_count": len(eligible_staff),
            "departments": departments,
            "priority": priority
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting eligible staff: {str(e)}"
        )

@router.post("/assign-staff")
async def smart_assign_staff(
    assignment_request: StaffAssignmentRequest,
    current_user: dict = Depends(require_staff_or_admin)
):
    """Smart assignment of staff to tasks"""
    try:
        assignment_result = await staff_scheduling_service.smart_assign_staff(
            assignment_request.task_id,
            assignment_request.task_type,
            assignment_request.required_departments,
            assignment_request.priority,
            assignment_request.preferred_staff_id,
            assignment_request.location
        )
        
        return assignment_result.dict()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in staff assignment: {str(e)}"
        )

# ──────────────────────────────────────────────────────────────────────────────
# Admin Dashboard Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/overview")
async def get_staff_schedule_overview(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    current_user: dict = Depends(require_admin)
):
    """Get staff scheduling overview for admin dashboard"""
    try:
        overview = await staff_scheduling_service.get_staff_schedule_overview(building_id)
        
        if "error" in overview:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=overview["error"]
            )
        
        return overview
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting staff overview: {str(e)}"
        )

@router.get("/staff-list")
async def get_staff_list_with_status(
    department: Optional[str] = Query(None, description="Filter by department"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(require_admin)
):
    """Get detailed staff list with availability and status"""
    try:
        # Get all staff
        staff_filters = [('role', '==', 'staff'), ('status', '==', 'active')]
        if department:
            staff_filters.append(('staff_department', '==', department))
        
        success, all_staff, error = await database_service.query_documents(
            COLLECTIONS['users'], filters=staff_filters
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get staff: {error}"
            )
        
        # Get current week availability
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_str = week_start.strftime('%Y-%m-%d')
        
        success, availability_docs, error = await database_service.query_documents(
            COLLECTIONS['staff_availability'],
            filters=[('week_start_date', '==', week_start_str)]
        )
        
        # Get real-time status
        success, status_docs, error = await database_service.query_documents(
            COLLECTIONS['staff_real_time_status']
        )
        
        # Combine data
        staff_list = []
        for staff in all_staff:
            staff_id = staff.get('id') or staff.get('_doc_id')
            
            # Find availability
            availability = next(
                (a for a in availability_docs if a.get('staff_id') == staff_id),
                None
            )
            
            # Find real-time status
            real_time_status = next(
                (s for s in status_docs if s.get('staff_id') == staff_id),
                {}
            )
            
            # Calculate this week's availability
            today_name = today.strftime('%A').lower()
            is_available_today = True
            days_available_this_week = 5  # Default
            
            if availability:
                is_available_today = availability.get(today_name, True)
                days_available_this_week = sum([
                    availability.get('monday', True),
                    availability.get('tuesday', True),
                    availability.get('wednesday', True),
                    availability.get('thursday', True),
                    availability.get('friday', True),
                    availability.get('saturday', False),
                    availability.get('sunday', False)
                ])
            
            staff_info = {
                "staff_id": staff_id,
                "user_id": staff.get('user_id'),
                "first_name": staff.get('first_name'),
                "last_name": staff.get('last_name'),
                "email": staff.get('email'),
                "departments": staff.get('staff_departments', []) or [staff.get('staff_department')] if staff.get('staff_department') else [],
                "phone_number": staff.get('phone_number'),
                
                # Availability info
                "is_available_today": is_available_today,
                "days_available_this_week": f"{days_available_this_week}/7",
                "availability_status": availability.get('status', 'not_submitted') if availability else 'not_submitted',
                
                # Real-time status
                "current_status": real_time_status.get('current_status', 'available'),
                "workload_level": real_time_status.get('workload_level', 'low'),
                "active_task_count": real_time_status.get('active_task_count', 0),
                "current_location": real_time_status.get('current_location'),
                "last_activity": real_time_status.get('last_activity_at'),
                "auto_assign_eligible": real_time_status.get('auto_assign_eligible', True),
                
                # Computed fields
                "overall_status": "Available" if is_available_today and real_time_status.get('current_status') == 'available' else "Unavailable"
            }
            
            # Apply status filter
            if status_filter:
                if status_filter.lower() == 'available' and staff_info['overall_status'] != 'Available':
                    continue
                elif status_filter.lower() == 'unavailable' and staff_info['overall_status'] != 'Unavailable':
                    continue
            
            staff_list.append(staff_info)
        
        return {
            "staff": staff_list,
            "total_count": len(staff_list),
            "filters": {
                "department": department,
                "status": status_filter
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting staff list: {str(e)}"
        )
from typing import List, Optional, Dict, Tuple
from datetime import datetime, date, timedelta
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.staff_scheduling_models import (
    StaffAvailability, StaffRealTimeStatus, DayOffRequest,
    AvailabilityStatus, DayOffStatus, WorkloadLevel,
    EligibleStaffResponse, StaffAssignmentResponse
)
import logging

logger = logging.getLogger(__name__)

class StaffSchedulingService:
    """Service for managing staff scheduling and availability"""
    
    async def submit_weekly_availability(
        self, 
        staff_id: str, 
        availability_data: dict
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Submit or update weekly availability for a staff member"""
        try:
            # Parse week start date
            week_start_str = availability_data.get('week_start_date')
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
            week_end = week_start + timedelta(days=6)
            
            # Check if availability already exists for this week
            existing_filters = [
                ('staff_id', '==', staff_id),
                ('week_start_date', '==', week_start_str)
            ]
            
            success, existing_docs, error = await database_service.query_documents(
                COLLECTIONS['staff_availability'], 
                filters=existing_filters,
                limit=1
            )
            
            availability_doc = {
                'staff_id': staff_id,
                'week_start_date': week_start_str,
                'week_end_date': week_end.strftime('%Y-%m-%d'),
                'monday': availability_data.get('monday', True),
                'tuesday': availability_data.get('tuesday', True),
                'wednesday': availability_data.get('wednesday', True),
                'thursday': availability_data.get('thursday', True),
                'friday': availability_data.get('friday', True),
                'saturday': availability_data.get('saturday', False),
                'sunday': availability_data.get('sunday', False),
                'monday_hours': availability_data.get('monday_hours'),
                'tuesday_hours': availability_data.get('tuesday_hours'),
                'wednesday_hours': availability_data.get('wednesday_hours'),
                'thursday_hours': availability_data.get('thursday_hours'),
                'friday_hours': availability_data.get('friday_hours'),
                'saturday_hours': availability_data.get('saturday_hours'),
                'sunday_hours': availability_data.get('sunday_hours'),
                'status': 'submitted',
                'submitted_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            if existing_docs:
                # Update existing availability
                doc_id = existing_docs[0].get('_doc_id') or existing_docs[0].get('id')
                success, error = await database_service.update_document(
                    COLLECTIONS['staff_availability'], 
                    doc_id, 
                    availability_doc
                )
                return success, doc_id, error
            else:
                # Create new availability record
                availability_doc['created_at'] = datetime.utcnow()
                success, doc_id, error = await database_service.create_document(
                    COLLECTIONS['staff_availability'], 
                    availability_doc
                )
                return success, doc_id, error
                
        except Exception as e:
            logger.error(f"Error submitting weekly availability: {str(e)}")
            return False, None, str(e)
    
    async def update_real_time_status(
        self, 
        staff_id: str, 
        status: AvailabilityStatus,
        location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Update real-time status of a staff member"""
        try:
            # Get or create real-time status record
            existing_filters = [('staff_id', '==', staff_id)]
            success, existing_docs, error = await database_service.query_documents(
                COLLECTIONS['staff_real_time_status'],
                filters=existing_filters,
                limit=1
            )
            
            # Calculate workload level based on active tasks
            active_task_count = await self._get_active_task_count(staff_id)
            workload_level = self._calculate_workload_level(active_task_count)
            
            # Determine if staff is scheduled on duty today
            is_scheduled_on_duty = await self._is_scheduled_on_duty_today(staff_id)
            
            # Calculate auto-assignment eligibility
            is_currently_available = status == AvailabilityStatus.AVAILABLE
            auto_assign_eligible = (
                is_scheduled_on_duty and 
                is_currently_available and 
                workload_level != WorkloadLevel.OVERLOADED
            )
            
            status_doc = {
                'staff_id': staff_id,
                'current_status': status.value,
                'workload_level': workload_level.value,
                'active_task_count': active_task_count,
                'current_location': location,
                'status_updated_at': datetime.utcnow(),
                'last_activity_at': datetime.utcnow(),
                'is_scheduled_on_duty': is_scheduled_on_duty,
                'is_currently_available': is_currently_available,
                'auto_assign_eligible': auto_assign_eligible,
                'updated_at': datetime.utcnow()
            }
            
            # Handle break timing
            if status == AvailabilityStatus.ON_BREAK:
                status_doc['break_start_time'] = datetime.utcnow()
            elif status == AvailabilityStatus.AVAILABLE and existing_docs:
                # Clear break time when returning from break
                status_doc['break_start_time'] = None
            
            if existing_docs:
                # Update existing status
                doc_id = existing_docs[0].get('_doc_id') or existing_docs[0].get('id')
                success, error = await database_service.update_document(
                    COLLECTIONS['staff_real_time_status'],
                    doc_id,
                    status_doc
                )
                return success, doc_id, error
            else:
                # Create new status record
                status_doc['created_at'] = datetime.utcnow()
                success, doc_id, error = await database_service.create_document(
                    COLLECTIONS['staff_real_time_status'],
                    status_doc
                )
                return success, doc_id, error
                
        except Exception as e:
            logger.error(f"Error updating real-time status: {str(e)}")
            return False, None, str(e)
    
    async def submit_day_off_request(
        self, 
        staff_id: str, 
        request_data: dict
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Submit a day-off request"""
        try:
            # Generate formatted ID
            formatted_id = await self._generate_day_off_request_id()
            
            request_doc = {
                'formatted_id': formatted_id,
                'staff_id': staff_id,
                'request_date': request_data['request_date'],
                'reason': request_data['reason'],
                'description': request_data.get('description'),
                'request_type': request_data.get('request_type', 'day_off'),
                'status': DayOffStatus.PENDING.value,
                'requested_at': datetime.utcnow(),
                'affects_critical_tasks': await self._check_critical_tasks_impact(
                    staff_id, request_data['request_date']
                ),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            success, doc_id, error = await database_service.create_document(
                COLLECTIONS['day_off_requests'],
                request_doc
            )
            
            return success, doc_id, error
            
        except Exception as e:
            logger.error(f"Error submitting day-off request: {str(e)}")
            return False, None, str(e)
    
    async def get_eligible_staff_for_assignment(
        self, 
        required_departments: List[str],
        task_location: Optional[str] = None,
        priority: str = "medium"
    ) -> List[EligibleStaffResponse]:
        """Get list of eligible staff for task assignment"""
        try:
            # Get all staff members in required departments
            staff_filters = [
                ('role', '==', 'staff'),
                ('status', '==', 'active')
            ]
            
            success, all_staff, error = await database_service.query_documents(
                COLLECTIONS['users'],
                filters=staff_filters
            )
            
            if not success:
                logger.error(f"Error querying staff: {error}")
                return []
            
            eligible_staff = []
            
            for staff in all_staff:
                staff_id = staff.get('id') or staff.get('_doc_id')
                
                # Check if staff has required departments
                staff_departments = (
                    staff.get('staff_departments', []) or 
                    staff.get('departments', []) or 
                    [staff.get('staff_department')] if staff.get('staff_department') else []
                )
                
                has_required_dept = any(dept in staff_departments for dept in required_departments)
                if not has_required_dept:
                    continue
                
                # Get real-time status
                real_time_status = await self._get_staff_real_time_status(staff_id)
                
                # Check if eligible for auto-assignment
                if not real_time_status.get('auto_assign_eligible', False):
                    continue
                
                # For critical priority, only include staff with low/medium workload
                if priority == "critical":
                    workload = real_time_status.get('workload_level', 'low')
                    if workload in ['high', 'overloaded']:
                        continue
                
                eligible_staff.append(EligibleStaffResponse(
                    staff_id=staff_id,
                    user_id=staff.get('user_id', ''),
                    first_name=staff.get('first_name', ''),
                    last_name=staff.get('last_name', ''),
                    departments=staff_departments,
                    current_status=AvailabilityStatus(real_time_status.get('current_status', 'available')),
                    workload_level=WorkloadLevel(real_time_status.get('workload_level', 'low')),
                    active_task_count=real_time_status.get('active_task_count', 0),
                    is_scheduled_on_duty=real_time_status.get('is_scheduled_on_duty', False),
                    is_currently_available=real_time_status.get('is_currently_available', True),
                    auto_assign_eligible=real_time_status.get('auto_assign_eligible', True),
                    current_location=real_time_status.get('current_location'),
                    last_activity_at=real_time_status.get('last_activity_at')
                ))
            
            # Sort by workload level and last activity
            eligible_staff.sort(key=lambda x: (
                x.workload_level.value,
                x.active_task_count,
                -(x.last_activity_at.timestamp() if x.last_activity_at else 0)
            ))
            
            return eligible_staff
            
        except Exception as e:
            logger.error(f"Error getting eligible staff: {str(e)}")
            return []
    
    async def smart_assign_staff(
        self,
        task_id: str,
        task_type: str,
        required_departments: List[str],
        priority: str = "medium",
        preferred_staff_id: Optional[str] = None,
        location: Optional[str] = None
    ) -> StaffAssignmentResponse:
        """Smart assignment of staff to tasks"""
        try:
            # Get eligible staff
            eligible_staff = await self.get_eligible_staff_for_assignment(
                required_departments, location, priority
            )
            
            if not eligible_staff:
                return StaffAssignmentResponse(
                    assigned_staff_id=None,
                    assignment_reason="No eligible staff available",
                    eligible_staff_count=0,
                    alternative_staff=[],
                    assignment_successful=False
                )
            
            # Try preferred staff first
            assigned_staff = None
            assignment_reason = ""
            
            if preferred_staff_id:
                preferred_staff = next(
                    (s for s in eligible_staff if s.staff_id == preferred_staff_id), 
                    None
                )
                if preferred_staff:
                    assigned_staff = preferred_staff
                    assignment_reason = "Assigned to preferred staff member"
            
            # If no preferred staff or preferred not available, use smart assignment
            if not assigned_staff:
                # Priority-based assignment logic
                if priority == "critical":
                    # For critical tasks, assign to staff with lowest workload
                    assigned_staff = min(eligible_staff, key=lambda x: x.active_task_count)
                    assignment_reason = "Assigned to staff with lowest workload (critical priority)"
                else:
                    # For normal tasks, use balanced assignment
                    assigned_staff = eligible_staff[0]  # Already sorted by workload
                    assignment_reason = "Assigned using balanced workload distribution"
            
            # Update task assignment
            if assigned_staff:
                await self._update_task_assignment(task_id, task_type, assigned_staff.staff_id)
                await self._update_staff_workload(assigned_staff.staff_id, task_id)
            
            return StaffAssignmentResponse(
                assigned_staff_id=assigned_staff.staff_id if assigned_staff else None,
                assignment_reason=assignment_reason,
                eligible_staff_count=len(eligible_staff),
                alternative_staff=eligible_staff[:5],  # Return top 5 alternatives
                assignment_successful=assigned_staff is not None
            )
            
        except Exception as e:
            logger.error(f"Error in smart staff assignment: {str(e)}")
            return StaffAssignmentResponse(
                assigned_staff_id=None,
                assignment_reason=f"Assignment failed: {str(e)}",
                eligible_staff_count=0,
                alternative_staff=[],
                assignment_successful=False
            )
    
    async def get_staff_schedule_overview(self, building_id: Optional[str] = None) -> dict:
        """Get overview of staff scheduling for admin dashboard"""
        try:
            # Get all active staff
            staff_filters = [('role', '==', 'staff'), ('status', '==', 'active')]
            if building_id:
                staff_filters.append(('building_id', '==', building_id))
            
            success, all_staff, error = await database_service.query_documents(
                COLLECTIONS['users'], filters=staff_filters
            )
            
            if not success:
                return {"error": f"Failed to get staff: {error}"}
            
            total_staff = len(all_staff)
            
            # Get current week's availability
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_start_str = week_start.strftime('%Y-%m-%d')
            
            availability_filters = [('week_start_date', '==', week_start_str)]
            success, availability_docs, error = await database_service.query_documents(
                COLLECTIONS['staff_availability'], filters=availability_filters
            )
            
            # Get real-time status
            success, status_docs, error = await database_service.query_documents(
                COLLECTIONS['staff_real_time_status']
            )
            
            # Get pending day-off requests
            dayoff_filters = [('status', '==', 'pending')]
            success, dayoff_docs, error = await database_service.query_documents(
                COLLECTIONS['day_off_requests'], filters=dayoff_filters
            )
            
            # Calculate statistics
            available_this_week = 0
            unavailable_count = 0
            staff_by_status = {}
            staff_by_department = {}
            
            for staff in all_staff:
                staff_id = staff.get('id') or staff.get('_doc_id')
                
                # Check availability for today
                today_name = today.strftime('%A').lower()
                staff_availability = next(
                    (a for a in availability_docs if a.get('staff_id') == staff_id), 
                    None
                )
                
                is_available_today = True
                if staff_availability:
                    is_available_today = staff_availability.get(today_name, True)
                
                if is_available_today:
                    available_this_week += 1
                else:
                    unavailable_count += 1
                
                # Status breakdown
                staff_status = next(
                    (s for s in status_docs if s.get('staff_id') == staff_id), 
                    {}
                )
                current_status = staff_status.get('current_status', 'available')
                staff_by_status[current_status] = staff_by_status.get(current_status, 0) + 1
                
                # Department breakdown
                departments = (
                    staff.get('staff_departments', []) or 
                    [staff.get('staff_department')] if staff.get('staff_department') else ['unassigned']
                )
                for dept in departments:
                    staff_by_department[dept] = staff_by_department.get(dept, 0) + 1
            
            return {
                "total_staff": total_staff,
                "available_this_week": available_this_week,
                "unavailable_count": unavailable_count,
                "pending_day_off_requests": len(dayoff_docs or []),
                "staff_by_status": staff_by_status,
                "staff_by_department": staff_by_department,
                "weekly_availability": availability_docs or []
            }
            
        except Exception as e:
            logger.error(f"Error getting staff schedule overview: {str(e)}")
            return {"error": str(e)}
    
    # Helper methods
    async def _get_active_task_count(self, staff_id: str) -> int:
        """Get count of active tasks for a staff member"""
        try:
            # Count maintenance tasks
            maintenance_filters = [
                ('assigned_to', '==', staff_id),
                ('status', 'in', ['assigned', 'in_progress'])
            ]
            success, maintenance_tasks, error = await database_service.query_documents(
                COLLECTIONS['maintenance_tasks'], filters=maintenance_filters
            )
            
            # Count job services
            job_filters = [
                ('assigned_to', '==', staff_id),
                ('status', 'in', ['assigned', 'in_progress'])
            ]
            success, job_services, error = await database_service.query_documents(
                COLLECTIONS['job_services'], filters=job_filters
            )
            
            return len(maintenance_tasks or []) + len(job_services or [])
            
        except Exception as e:
            logger.error(f"Error getting active task count: {str(e)}")
            return 0
    
    def _calculate_workload_level(self, active_task_count: int) -> WorkloadLevel:
        """Calculate workload level based on active tasks"""
        if active_task_count == 0:
            return WorkloadLevel.LOW
        elif active_task_count <= 2:
            return WorkloadLevel.MEDIUM
        elif active_task_count <= 4:
            return WorkloadLevel.HIGH
        else:
            return WorkloadLevel.OVERLOADED
    
    async def _is_scheduled_on_duty_today(self, staff_id: str) -> bool:
        """Check if staff is scheduled to be on duty today"""
        try:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_start_str = week_start.strftime('%Y-%m-%d')
            
            filters = [
                ('staff_id', '==', staff_id),
                ('week_start_date', '==', week_start_str)
            ]
            
            success, docs, error = await database_service.query_documents(
                COLLECTIONS['staff_availability'], filters=filters, limit=1
            )
            
            if not success or not docs:
                return True  # Default to on duty if no schedule found
            
            availability = docs[0]
            today_name = today.strftime('%A').lower()
            
            return availability.get(today_name, True)
            
        except Exception as e:
            logger.error(f"Error checking duty schedule: {str(e)}")
            return True
    
    async def _get_staff_real_time_status(self, staff_id: str) -> dict:
        """Get real-time status of a staff member"""
        try:
            filters = [('staff_id', '==', staff_id)]
            success, docs, error = await database_service.query_documents(
                COLLECTIONS['staff_real_time_status'], filters=filters, limit=1
            )
            
            if success and docs:
                return docs[0]
            
            # Return default status if not found
            return {
                'current_status': 'available',
                'workload_level': 'low',
                'active_task_count': 0,
                'is_scheduled_on_duty': True,
                'is_currently_available': True,
                'auto_assign_eligible': True
            }
            
        except Exception as e:
            logger.error(f"Error getting staff real-time status: {str(e)}")
            return {}
    
    async def _generate_day_off_request_id(self) -> str:
        """Generate formatted ID for day-off requests"""
        try:
            current_year = datetime.now().year
            
            # Get or create counter for this year
            counter_id = f"day_off_requests_{current_year}"
            success, counter_doc, error = await database_service.get_document(
                COLLECTIONS['counters'], counter_id
            )
            
            if not success or not counter_doc:
                # Create new counter
                counter_data = {
                    'year': current_year,
                    'counter': 1,
                    'last_updated': datetime.utcnow()
                }
                success, doc_id, error = await database_service.create_document(
                    COLLECTIONS['counters'], counter_data, document_id=counter_id
                )
                return f"DOR-{current_year}-00001"
            else:
                # Increment counter
                new_counter = counter_doc['counter'] + 1
                await database_service.update_document(
                    COLLECTIONS['counters'], counter_id,
                    {'counter': new_counter, 'last_updated': datetime.utcnow()}
                )
                return f"DOR-{current_year}-{new_counter:05d}"
                
        except Exception as e:
            logger.error(f"Error generating day-off request ID: {str(e)}")
            return f"DOR-{datetime.now().year}-{datetime.now().microsecond:05d}"
    
    async def _check_critical_tasks_impact(self, staff_id: str, request_date_str: str) -> bool:
        """Check if day-off request affects critical tasks"""
        try:
            request_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
            
            # Check for critical maintenance tasks on that date
            filters = [
                ('assigned_to', '==', staff_id),
                ('scheduled_date', '>=', request_date),
                ('scheduled_date', '<', request_date + timedelta(days=1)),
                ('priority', 'in', ['high', 'critical'])
            ]
            
            success, tasks, error = await database_service.query_documents(
                COLLECTIONS['maintenance_tasks'], filters=filters
            )
            
            return len(tasks or []) > 0
            
        except Exception as e:
            logger.error(f"Error checking critical tasks impact: {str(e)}")
            return False
    
    async def _update_task_assignment(self, task_id: str, task_type: str, staff_id: str):
        """Update task assignment in the respective collection"""
        try:
            collection = COLLECTIONS.get(task_type + 's', COLLECTIONS['maintenance_tasks'])
            update_data = {
                'assigned_to': staff_id,
                'status': 'assigned',
                'updated_at': datetime.utcnow()
            }
            
            await database_service.update_document(collection, task_id, update_data)
            
        except Exception as e:
            logger.error(f"Error updating task assignment: {str(e)}")
    
    async def _update_staff_workload(self, staff_id: str, task_id: str):
        """Update staff workload with new task"""
        try:
            # Get current real-time status
            filters = [('staff_id', '==', staff_id)]
            success, docs, error = await database_service.query_documents(
                COLLECTIONS['staff_real_time_status'], filters=filters, limit=1
            )
            
            if success and docs:
                doc_id = docs[0].get('_doc_id') or docs[0].get('id')
                current_tasks = docs[0].get('active_task_ids', [])
                current_tasks.append(task_id)
                
                new_count = len(current_tasks)
                new_workload = self._calculate_workload_level(new_count)
                
                update_data = {
                    'active_task_count': new_count,
                    'active_task_ids': current_tasks,
                    'workload_level': new_workload.value,
                    'updated_at': datetime.utcnow()
                }
                
                await database_service.update_document(
                    COLLECTIONS['staff_real_time_status'], doc_id, update_data
                )
                
        except Exception as e:
            logger.error(f"Error updating staff workload: {str(e)}")

# Create service instance
staff_scheduling_service = StaffSchedulingService()
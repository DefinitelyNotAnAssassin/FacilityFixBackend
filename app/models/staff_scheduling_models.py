from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, date, time
from enum import Enum

# --------------------------------------------------------------------------
# Enums for Staff Scheduling
# --------------------------------------------------------------------------

class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ON_BREAK = "on_break"
    BUSY = "busy"
    OFF_DUTY = "off_duty"

class DayOffStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUBMITTED = "submitted"

class WorkloadLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    OVERLOADED = "overloaded"

# --------------------------------------------------------------------------
# Staff Availability Model
# --------------------------------------------------------------------------

class StaffAvailability(BaseModel):
    """Weekly availability schedule for staff members"""
    id: Optional[str] = None
    staff_id: str
    week_start_date: date
    week_end_date: date

    # Daily availability (True = Available, False = Unavailable)
    monday: bool = Field(default=True)
    tuesday: bool = Field(default=True)
    wednesday: bool = Field(default=True)  
    thursday: bool = Field(default=True)
    friday: bool = Field(default=True)
    saturday: bool = Field(default=False)
    sunday: bool = Field(default=False)

    # Time slots for each day (optional - for future enhancements)
    monday_hours: Optional[str] = None
    tuesday_hours: Optional[str] = None
    wednesday_hours: Optional[str] = None
    thursday_hours: Optional[str] = None
    friday_hours: Optional[str] = None
    saturday_hours: Optional[str] = None
    sunday_hours: Optional[str] = None

    status: ScheduleStatus = ScheduleStatus.ACTIVE
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class StaffRealTimeStatus(BaseModel):
    """Real-time status and availability of staff members"""
    id: Optional [str] = None
    staff_id: str # User ID of staff member
    current_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE 
    workload_level: WorkloadLevel = WorkloadLevel.LOW

    # Current assignments
    active_task_count: int = Field (default=0, ge=0)
    active_task_ids: List[str] = Field (default_factory=list)

    # Location and contact info
    current_location: Optional [str] = None 
    contact_number: Optional [str] = None

    # Status timing
    status_updated_at: Optional [datetime] = None 
    last_activity_at: Optional [datetime] = None

    # Break and duty tracking
    break_start_time: Optional [datetime] = None 
    duty_start_time: Optional [datetime] = None 
    duty_end_time: Optional [datetime] = None

    # Auto-assignment eligibility
    is_scheduled_on_duty: bool = Field(default=False) # Based on schedule
    is_currently_available: bool = Field(default=True) # Real-time availability 
    auto_assign_eligible: bool = Field(default=True) # Computed field
    
    created_at: Optional [datetime] = None 
    updated_at: Optional [datetime] = None


class DayOffRequest (BaseModel):
    """Staff day-off and leave requests"""
    id: Optional [str] = None
    formatted_id: Optional [str] = None # e.g., "DOR-2024-00001" 
    staff_id: str # User ID of staff member

    # Request details
    request_date: date
    reason: str
    description: Optional[str] = None
    request_type: str = Field (default="day_off") # day_off, sick_leave, vacation, emergency

    # Approval workflow
    status: DayOffStatus = DayOffStatus.PENDING
    requested_at: datetime
    approved_by: Optional [str] = None # Admin user ID
    approved_at: Optional [datetime] = None
    rejection_reason: Optional [str] = None 
    admin_notes: Optional [str] = None

    # Impact assessment
    affects_critical_tasks: bool = Field (default=False) 
    replacement_staff_id: Optional [str] = None
    impact_assessment: Optional [str] = None

    created_at: Optional [datetime] = None 
    updated_at: Optional [datetime] = None

# --------------------------------------------------------------------------
# Request/Response Models
# --------------------------------------------------------------------------
class WeeklyAvailabilityRequest(BaseModel): 
    """Request to submit weekly availability"""
    week_start_date: str # YYYY-MM-DD format
    monday: bool = True 
    tuesday: bool = True 
    wednesday: bool = True
    thursday: bool = True
    friday: bool = True
    saturday: bool = False
    sunday: bool = False

    # Optional time slots
    monday_hours: Optional [str] = None 
    tuesday_hours: Optional [str] = None 
    wednesday_hours: Optional [str] = None 
    thursday_hours: Optional [str] = None 
    friday_hours: Optional [str] = None 
    saturday_hours: Optional [str] = None 
    sunday_hours: Optional [str] = None

class StatusUpdateRequest(BaseModel): 
    """Request to update real-time status"""
    status: AvailabilityStatus 
    location: Optional [str] = None 
    notes: Optional [str] = None

class DayOffRequestSubmission (BaseModel): 
    """Request to submit a day-off request""" 
    request_date: str # YYYY-MM-DD 
    reason: str
    description: Optional [str] = None
    request_type: str = "day_off"

class DayOffRequestResponse(BaseModel):
    """Response for day-off request operations"""
    status: DayOffStatus
    reason: Optional [str] = None
    
    admin_notes: Optional [str] = None


class BulkApproveDayOffRequest(BaseModel):
    """Request to bulk approve day-off requests"""
    request_ids: List[str]
    admin_notes: Optional[str] = None


class BulkRejectDayOffRequest(BaseModel):
    """Request to bulk reject day-off requests"""
    request_ids: List[str]
    rejection_reason: str


class StaffScheduleOverview (BaseModel):
    """Overview of staff scheduling for admin dashboard""" 
    total_staff: int
    available_this_week: int
    unavailable_count: int
    pending_day_off_requests: int

    # Staff breakdown by status 
    staff_by_status: Dict[str, int] 
    staff_by_department: Dict[str, int]

    # This week's availability
    weekly_availability: List[Dict[str, Any]]

class EligibleStaffResponse(BaseModel):
    """Response for eligible staff for task assignment"""
    staff_id: str
    user_id: str
    first_name: str
    last_name: str
    departments: List[str]
    current_status: AvailabilityStatus
    workload_level: WorkloadLevel
    active_task_count: int
    is_scheduled_on_duty: bool
    is_currently_available: bool
    auto_assign_eligible: bool
    current_location: Optional [str] = None
    last_activity_at: Optional [datetime] = None

class StaffAssignmentRequest(BaseModel):
    """Request for smart staff assignment"""
    task_id: str
    task_type: str # maintenance_task, job_service, concern_slip 
    required_departments: List[str]
    priority: str = "medium" # low, medium, high, critical 
    preferred_staff_id: Optional[str] = None
    location: Optional[str] = None
    estimated_duration: Optional [int] = None # in minutes

class StaffAssignmentResponse(BaseModel):
    """Response for staff assignment"""
    assigned_staff_id: Optional [str] = None
    assignment_reason: str
    eligible_staff_count: int
    alternative_staff: List[EligibleStaffResponse] = Field (default_factory=list) 
    assignment_successful: bool

# --------------------------------------------------------------------------
# Analytics and Reporting Models
# --------------------------------------------------------------------------

class StaffworkloadAnalytics (BaseModel):
    """Analytics for staff workload and performance"""
    staff_id: str
    period_start: date
    period_end: date

    # Task statistics
    total_tasks_assigned: int
    total_tasks_completed: int
    completion_rate: float
    average_task_duration: Optional[float] = None # in hours

    # Availability statistics
    total_available_hours: float 
    total_working_hours: float 
    utilization_rate: float
    
    # Performance metrics
    on_time_completion_rate: float
    quality_rating_average: Optional [float] = None
    created_at: Optional [datetime] = None

class DepartmentScheduleAnalytics (BaseModel): 
    """Analytics for department-level scheduling"""
    department: str
    period_start: date
    period_end: date

    # Staff metrics
    total_staff: int
    average_availability_rate: float 
    total_day_off_requests: int 
    approved_day_off_rate: float

    # Workload distribution
    workload_distribution: Dict[str, int] # {workload_level: count} peak_demand_days: List[str]
    created_at: Optional [datetime] = None
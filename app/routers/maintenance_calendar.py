from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from app.auth.dependencies import get_current_user, require_staff_or_admin
from ..services.maintenance_scheduler_service import maintenance_scheduler_service
from ..services.equipment_usage_service import equipment_usage_service
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS

router = APIRouter(prefix="/maintenance-calendar", tags=["Maintenance Calendar"])

# Request/Response Models
class MaintenanceScheduleCreate(BaseModel):
    equipment_id: str
    building_id: str
    schedule_name: str
    description: str
    schedule_type: str = "time_based"  # time_based, usage_based
    recurrence_pattern: Optional[str] = None
    interval_value: Optional[int] = None
    specific_days: Optional[List[str]] = []
    specific_dates: Optional[List[int]] = []
    usage_threshold: Optional[int] = None
    usage_unit: Optional[str] = None
    estimated_duration: Optional[int] = None
    required_skills: Optional[List[str]] = []
    required_parts: Optional[List[str]] = []
    safety_requirements: Optional[List[str]] = []
    preferred_time_slots: Optional[List[str]] = []
    priority: str = "medium"

class MaintenanceScheduleUpdate(BaseModel):
    schedule_name: Optional[str] = None
    description: Optional[str] = None
    schedule_type: Optional[str] = None
    recurrence_pattern: Optional[str] = None
    interval_value: Optional[int] = None
    specific_days: Optional[List[str]] = None
    specific_dates: Optional[List[int]] = None
    usage_threshold: Optional[int] = None
    usage_unit: Optional[str] = None
    estimated_duration: Optional[int] = None
    required_skills: Optional[List[str]] = None
    required_parts: Optional[List[str]] = None
    safety_requirements: Optional[List[str]] = None
    preferred_time_slots: Optional[List[str]] = None
    priority: Optional[str] = None
    is_active: Optional[bool] = None

class TaskStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None
    actual_duration: Optional[int] = None
    parts_used: Optional[List[Dict]] = []
    completion_notes: Optional[str] = None
    quality_rating: Optional[int] = None

class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None
    status: str
    priority: str
    category: str
    assigned_to: Optional[str] = None
    equipment_id: Optional[str] = None
    equipment_name: Optional[str] = None

# Schedule Management Endpoints
@router.post("/schedules", response_model=Dict[str, Any])
async def create_maintenance_schedule(
    schedule_data: MaintenanceScheduleCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new maintenance schedule"""
    try:
        # Verify user has admin/staff role
        if current_user.get('role') not in ['admin', 'staff']:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        success, schedule_id, error = await maintenance_scheduler_service.create_maintenance_schedule(
            schedule_data.dict(exclude_none=True),
            current_user['uid']
        )
        
        if success:
            return {
                "success": True,
                "schedule_id": schedule_id,
                "message": "Maintenance schedule created successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/schedules", response_model=Dict[str, Any])
async def get_maintenance_schedules(
    building_id: str = Query(..., description="Building ID"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment ID"),
    active_only: bool = Query(True, description="Show only active schedules"),
    current_user: dict = Depends(get_current_user)
):
    """Get maintenance schedules"""
    try:
        success, schedules, error = await maintenance_scheduler_service.get_maintenance_schedules(
            building_id, equipment_id, active_only
        )
        
        if success:
            return {
                "success": True,
                "schedules": schedules,
                "count": len(schedules)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/schedules/{schedule_id}", response_model=Dict[str, Any])
async def update_maintenance_schedule(
    schedule_id: str,
    update_data: MaintenanceScheduleUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a maintenance schedule"""
    try:
        # Verify user has admin/staff role
        if current_user.get('role') not in ['admin', 'staff']:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        success, error = await maintenance_scheduler_service.update_maintenance_schedule(
            schedule_id,
            update_data.dict(exclude_none=True),
            current_user['uid']
        )
        
        if success:
            return {
                "success": True,
                "message": "Maintenance schedule updated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/schedules/{schedule_id}", response_model=Dict[str, Any])
async def delete_maintenance_schedule(
    schedule_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a maintenance schedule"""
    try:
        # Verify user has admin role
        if current_user.get('role') != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Deactivate instead of delete to preserve history
        success, error = await maintenance_scheduler_service.update_maintenance_schedule(
            schedule_id,
            {'is_active': False},
            current_user['uid']
        )
        
        if success:
            return {
                "success": True,
                "message": "Maintenance schedule deactivated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Task Management Endpoints
@router.post("/tasks", response_model=Dict[str, Any])
async def create_maintenance_task(
    task_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Create a new maintenance task"""
    try:
        # Verify user has admin/staff role
        if current_user.get('role') not in ['admin', 'staff']:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Add metadata
        task_data['created_at'] = datetime.now().isoformat()
        task_data['created_by'] = current_user['uid']
        task_data['updated_at'] = datetime.now().isoformat()
        task_data['updated_by'] = current_user['uid']
        
        # Use the task code as the document ID
        task_id = task_data.get('taskCode', task_data.get('id'))
        
        # Save to database
        success, doc_id, error = await database_service.create_document(
            COLLECTIONS['maintenance_tasks'],
            task_data,
            document_id=task_id,
            validate=False
        )
        
        if success:
            return {
                "success": True,
                "task_id": doc_id,
                "message": "Maintenance task created successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to create maintenance task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/tasks", response_model=Dict[str, Any])
async def get_maintenance_tasks(
    building_id: str = Query(..., description="Building ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment"),
    category: Optional[str] = Query(None, description="Filter by category"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: dict = Depends(get_current_user)
):
    """Get maintenance tasks with filters"""
    try:
        filters = {}
        if status:
            filters['status'] = status
        if assigned_to:
            filters['assigned_to'] = assigned_to
        if equipment_id:
            filters['equipment_id'] = equipment_id
        if category:
            filters['category'] = category
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        success, tasks, error = await maintenance_scheduler_service.get_maintenance_tasks(
            building_id, filters
        )
        
        if success:
            return {
                "success": True,
                "tasks": tasks,
                "count": len(tasks)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_maintenance_task_by_id(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a single maintenance task by ID"""
    try:
        success, task_doc, error = await database_service.get_document(
            COLLECTIONS['maintenance_tasks'],
            task_id
        )
        
        if success and task_doc:
            return {
                "success": True,
                "task": task_doc
            }
        elif not success:
            raise HTTPException(status_code=400, detail=error)
        else:
            raise HTTPException(status_code=404, detail="Task not found")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/tasks/{task_id}/status", response_model=Dict[str, Any])
async def update_task_status(
    task_id: str,
    status_update: TaskStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update maintenance task status"""
    try:
        success, error = await maintenance_scheduler_service.update_task_status(
            task_id,
            status_update.status,
            current_user['uid'],
            status_update.notes
        )
        
        if success:
            # Update additional fields if provided
            if status_update.actual_duration or status_update.parts_used or status_update.completion_notes or status_update.quality_rating:
                update_data = {}
                if status_update.actual_duration:
                    update_data['actual_duration'] = status_update.actual_duration
                if status_update.parts_used:
                    update_data['parts_used'] = status_update.parts_used
                if status_update.completion_notes:
                    update_data['completion_notes'] = status_update.completion_notes
                if status_update.quality_rating:
                    update_data['quality_rating'] = status_update.quality_rating
                
                if update_data:
                    await database_service.update_document(
                        COLLECTIONS['maintenance_tasks'],
                        task_id,
                        update_data
                    )
            
            return {
                "success": True,
                "message": "Task status updated successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Calendar View Endpoints
@router.get("/calendar", response_model=Dict[str, Any])
async def get_calendar_events(
    building_id: str = Query(..., description="Building ID"),
    start_date: datetime = Query(..., description="Calendar start date"),
    end_date: datetime = Query(..., description="Calendar end date"),
    view_type: str = Query("month", description="Calendar view type (day, week, month)"),
    assigned_to: Optional[str] = Query(None, description="Filter by assigned user"),
    current_user: dict = Depends(get_current_user)
):
    """Get calendar events for maintenance tasks"""
    try:
        # Get maintenance tasks for the date range
        filters = {
            'date_from': start_date,
            'date_to': end_date
        }
        if assigned_to:
            filters['assigned_to'] = assigned_to
        
        success, tasks, error = await maintenance_scheduler_service.get_maintenance_tasks(
            building_id, filters
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=error)
        
        # Convert tasks to calendar events
        events = []
        for task in tasks:
            try:
                # Get equipment name
                equipment_name = "Unknown Equipment"
                if task.get('equipment_id'):
                    success, equipment_doc, error = database_service.get_document(
                        COLLECTIONS['equipment'], 
                        task['equipment_id']
                    )
                    if success:
                        equipment_name = equipment_doc.get('equipment_name', 'Unknown Equipment')
                
                # Calculate end time if duration is available
                start_time = task.get('scheduled_date')
                end_time = None
                if start_time and task.get('estimated_duration'):
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_time = start_time + timedelta(minutes=task['estimated_duration'])
                
                event = CalendarEvent(
                    id=task.get('id', ''),
                    title=task.get('task_title', 'Maintenance Task'),
                    start=start_time,
                    end=end_time,
                    description=task.get('task_description', ''),
                    location=task.get('location', ''),
                    status=task.get('status', 'scheduled'),
                    priority=task.get('priority', 'medium'),
                    category=task.get('category', 'maintenance'),
                    assigned_to=task.get('assigned_to'),
                    equipment_id=task.get('equipment_id'),
                    equipment_name=equipment_name
                )
                
                events.append(event.dict())
                
            except Exception as e:
                # Skip invalid tasks but log the error
                print(f"Error processing task {task.get('id')}: {str(e)}")
                continue
        
        return {
            "success": True,
            "events": events,
            "count": len(events),
            "view_type": view_type,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/calendar/summary", response_model=Dict[str, Any])
async def get_calendar_summary(
    building_id: str = Query(..., description="Building ID"),
    period: str = Query("week", description="Summary period (day, week, month)"),
    current_user: dict = Depends(get_current_user)
):
    """Get calendar summary statistics"""
    try:
        # Calculate date range based on period
        now = datetime.now()
        if period == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == "week":
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59)
        else:  # month
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1) - timedelta(seconds=1)
            else:
                end_date = start_date.replace(month=now.month + 1) - timedelta(seconds=1)
        
        # Get tasks for the period
        success, tasks, error = await maintenance_scheduler_service.get_maintenance_tasks(
            building_id, 
            {'date_from': start_date, 'date_to': end_date}
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=error)
        
        # Calculate summary statistics
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.get('status') == 'completed'])
        in_progress_tasks = len([t for t in tasks if t.get('status') == 'in_progress'])
        scheduled_tasks = len([t for t in tasks if t.get('status') == 'scheduled'])
        overdue_tasks = len([t for t in tasks if t.get('status') == 'overdue'])
        
        # Group by priority
        priority_breakdown = {
            'low': len([t for t in tasks if t.get('priority') == 'low']),
            'medium': len([t for t in tasks if t.get('priority') == 'medium']),
            'high': len([t for t in tasks if t.get('priority') == 'high']),
            'critical': len([t for t in tasks if t.get('priority') == 'critical'])
        }
        
        # Group by category
        category_breakdown = {}
        for task in tasks:
            category = task.get('category', 'unknown')
            category_breakdown[category] = category_breakdown.get(category, 0) + 1
        
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "success": True,
            "summary": {
                "period": period,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "scheduled_tasks": scheduled_tasks,
                "overdue_tasks": overdue_tasks,
                "completion_rate": round(completion_rate, 1),
                "priority_breakdown": priority_breakdown,
                "category_breakdown": category_breakdown
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Equipment Usage Endpoints
@router.post("/equipment/{equipment_id}/usage", response_model=Dict[str, Any])
async def log_equipment_usage(
    equipment_id: str,
    usage_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Log equipment usage"""
    try:
        success, log_id, error = await equipment_usage_service.log_equipment_usage(
            equipment_id,
            usage_data,
            current_user['uid']
        )
        
        if success:
            return {
                "success": True,
                "log_id": log_id,
                "message": "Equipment usage logged successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/equipment/{equipment_id}/usage", response_model=Dict[str, Any])
async def get_equipment_usage_history(
    equipment_id: str,
    days_back: int = Query(30, description="Days of history to retrieve"),
    usage_type: Optional[str] = Query(None, description="Filter by usage type"),
    current_user: dict = Depends(get_current_user)
):
    """Get equipment usage history"""
    try:
        success, usage_logs, error = await equipment_usage_service.get_equipment_usage_history(
            equipment_id, days_back, usage_type
        )
        
        if success:
            return {
                "success": True,
                "usage_logs": usage_logs,
                "count": len(usage_logs),
                "days_back": days_back
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/equipment/{equipment_id}/analytics", response_model=Dict[str, Any])
async def get_equipment_usage_analytics(
    equipment_id: str,
    period_days: int = Query(30, description="Analysis period in days"),
    current_user: dict = Depends(get_current_user)
):
    """Get equipment usage analytics"""
    try:
        success, analytics, error = await equipment_usage_service.get_usage_analytics(
            equipment_id, period_days
        )
        
        if success:
            return {
                "success": True,
                "analytics": analytics
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Utility Endpoints
@router.post("/generate-tasks", response_model=Dict[str, Any])
async def generate_maintenance_tasks(
    days_ahead: int = Query(30, description="Days ahead to generate tasks"),
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger maintenance task generation"""
    try:
        # Verify user has admin role
        if current_user.get('role') != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        success, tasks_generated, error = await maintenance_scheduler_service.generate_scheduled_tasks(days_ahead)
        
        if success:
            return {
                "success": True,
                "tasks_generated": tasks_generated,
                "days_ahead": days_ahead,
                "message": f"Generated {tasks_generated} maintenance tasks"
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/usage-thresholds", response_model=Dict[str, Any])
async def check_usage_thresholds(
    building_id: Optional[str] = Query(None, description="Filter by building ID"),
    current_user: dict = Depends(get_current_user)
):
    """Check equipment usage against maintenance thresholds"""
    try:
        success, threshold_alerts, error = await equipment_usage_service.check_usage_thresholds(building_id)
        
        if success:
            return {
                "success": True,
                "threshold_alerts": threshold_alerts,
                "count": len(threshold_alerts)
            }
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to check usage thresholds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/next-ipm-code", response_model=Dict[str, Any])
async def get_next_ipm_code(
    current_user: dict = Depends(require_staff_or_admin)  # Using require_staff_or_admin dependency instead of manual role check
):
    """Get the next sequential IPM code"""
    try:
        current_year = datetime.now().year
        
        success, tasks_doc, error = await database_service.get_document(
            COLLECTIONS['maintenance_tasks'],
            'ipm_counter'
        )
        
        if success and tasks_doc:
            # Get the last counter and year
            last_counter = tasks_doc.get('counter', 0)
            last_year = tasks_doc.get('year', current_year)
            
            # Reset counter if year changed
            if last_year != current_year:
                next_counter = 1
            else:
                next_counter = last_counter + 1
            
            await database_service.update_document(
                COLLECTIONS['maintenance_tasks'],
                'ipm_counter',
                {
                    'counter': next_counter,
                    'year': current_year,
                    'updated_at': datetime.now().isoformat(),
                    'updated_by': current_user['uid']
                },
                validate=False
            )
        else:
            next_counter = 1
            await database_service.create_document(
                COLLECTIONS['maintenance_tasks'],
                {
                    'counter': next_counter,
                    'year': current_year,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'created_by': current_user['uid'],
                    'updated_by': current_user['uid']
                },
                document_id='ipm_counter',
                validate=False
            )
        
        # Format the code
        code = f"IPM-{current_year}-{str(next_counter).zfill(5)}"
        
        return {
            "success": True,
            "code": code,
            "counter": next_counter,
            "year": current_year
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to generate IPM code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/next-epm-code", response_model=Dict[str, Any])
async def get_next_epm_code(
    current_user: dict = Depends(get_current_user)  # Using get_current_user instead of require_staff_or_admin
):
    """Get the next sequential EPM code"""
    try:
        if current_user.get('role') not in ['admin', 'staff']:
            print(f"[ERROR] EPM code access denied for user {current_user.get('email')} with role {current_user.get('role')}")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        print(f"[DEBUG] Generating EPM code for user {current_user.get('email')}")
        
        current_year = datetime.now().year
        
        success, tasks_doc, error = await database_service.get_document(
            COLLECTIONS['maintenance_tasks'],
            'epm_counter'
        )
        
        if success and tasks_doc:
            # Get the last counter and year
            last_counter = tasks_doc.get('counter', 0)
            last_year = tasks_doc.get('year', current_year)
            
            # Reset counter if year changed
            if last_year != current_year:
                next_counter = 1
            else:
                next_counter = last_counter + 1
            
            await database_service.update_document(
                COLLECTIONS['maintenance_tasks'],
                'epm_counter',
                {
                    'counter': next_counter,
                    'year': current_year,
                    'updated_at': datetime.now().isoformat(),
                    'updated_by': current_user['uid']
                },
                validate=False
            )
        else:
            next_counter = 1
            await database_service.create_document(
                COLLECTIONS['maintenance_tasks'],
                {
                    'counter': next_counter,
                    'year': current_year,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'created_by': current_user['uid'],
                    'updated_by': current_user['uid']
                },
                document_id='epm_counter',
                validate=False
            )
        
        # Format the code
        code = f"EPM-{current_year}-{str(next_counter).zfill(5)}"
        
        print(f"[DEBUG] Generated EPM code: {code}")
        
        return {
            "success": True,
            "code": code,
            "counter": next_counter,
            "year": current_year
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to generate EPM code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

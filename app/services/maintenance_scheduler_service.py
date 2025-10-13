from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from dateutil.relativedelta import relativedelta
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.database_models import (
    MaintenanceSchedule, MaintenanceTask, EquipmentUsageLog, 
    MaintenanceTemplate, Equipment
)
from firebase_admin import firestore 






logger = logging.getLogger(__name__)

class MaintenanceSchedulerService:
    def __init__(self):
        self.db = database_service

    # Schedule Management
    async def create_maintenance_schedule(self, schedule_data: dict, created_by: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Create a new maintenance schedule"""
        try:
            schedule = MaintenanceSchedule(**schedule_data)
            schedule.created_by = created_by
            schedule.created_at = datetime.now()
            schedule.updated_at = datetime.now()
            
            # Calculate next due date
            next_due = self._calculate_next_due_date(schedule)
            schedule.next_due_date = next_due
            
            success, schedule_id, error = await self.db.create_document(
                COLLECTIONS['maintenance_schedules'], 
                schedule.dict(exclude_none=True)
            )
            
            if success:
                logger.info(f"Created maintenance schedule {schedule_id}")
                # Generate initial tasks if schedule is active
                if schedule.is_active:
                    await self._generate_tasks_for_schedule(schedule_id, schedule)
                return True, schedule_id, None
            else:
                logger.error(f"Failed to create maintenance schedule: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"Error creating maintenance schedule: {str(e)}")
            return False, None, str(e)

    async def update_maintenance_schedule(self, schedule_id: str, update_data: dict, updated_by: str) -> Tuple[bool, Optional[str]]:
        """Update an existing maintenance schedule"""
        try:
            # Get existing schedule
            success, schedule_doc, error = await self.db.get_document(COLLECTIONS['maintenance_schedules'], schedule_id)
            if not success:
                return False, f"Schedule not found: {error}"
            
            # Update fields
            update_data['updated_at'] = datetime.now()
            
            # Recalculate next due date if scheduling parameters changed
            scheduling_fields = ['recurrence_pattern', 'interval_value', 'usage_threshold', 'specific_days', 'specific_dates']
            if any(field in update_data for field in scheduling_fields):
                schedule = MaintenanceSchedule(**{**schedule_doc, **update_data})
                update_data['next_due_date'] = self._calculate_next_due_date(schedule)
            
            success, error = await self.db.update_document(COLLECTIONS['maintenance_schedules'], schedule_id, update_data)
            
            if success:
                logger.info(f"Updated maintenance schedule {schedule_id}")
                return True, None
            else:
                logger.error(f"Failed to update maintenance schedule: {error}")
                return False, error
                
        except Exception as e:
            logger.error(f"Error updating maintenance schedule: {str(e)}")
            return False, str(e)

    async def get_maintenance_schedules(self, building_id: str, equipment_id: Optional[str] = None, active_only: bool = True) -> Tuple[bool, List[dict], Optional[str]]:
        """Get maintenance schedules for a building or equipment"""
        try:
            filters = [('building_id', '==', building_id)]
            
            if equipment_id:
                filters.append(('equipment_id', '==', equipment_id))
            
            if active_only:
                filters.append(('is_active', '==', True))
            
            success, schedules, error = await self.db.query_documents(COLLECTIONS['maintenance_schedules'], filters)
            
            if success:
                return True, schedules, None
            else:
                logger.error(f"Failed to get maintenance schedules: {error}")
                return False, [], error
                
        except Exception as e:
            logger.error(f"Error getting maintenance schedules: {str(e)}")
            return False, [], str(e)

    # Task Generation
    async def generate_scheduled_tasks(self, days_ahead: int = 30) -> Tuple[bool, int, Optional[str]]:
        """Generate maintenance tasks for all active schedules within the specified days ahead"""
        try:
            logger.info(f"Generating scheduled tasks for next {days_ahead} days")
            
            # Get all active schedules
            success, schedules, error = await self.db.query_documents(
                COLLECTIONS['maintenance_schedules'], 
                [('is_active', '==', True)]
            )
            
            if not success:
                return False, 0, f"Failed to get schedules: {error}"
            
            tasks_generated = 0
            end_date = datetime.now() + timedelta(days=days_ahead)
            
            for schedule_doc in schedules:
                try:
                    schedule = MaintenanceSchedule(**schedule_doc)
                    generated_count = await self._generate_tasks_for_schedule_period(schedule, end_date)
                    tasks_generated += generated_count
                    
                    # Update last_generated timestamp
                    await self.db.update_document(
                        COLLECTIONS['maintenance_schedules'], 
                        schedule.id, 
                        {'last_generated': datetime.now()}
                    )
                    
                except Exception as e:
                    logger.error(f"Error generating tasks for schedule {schedule_doc.get('id')}: {str(e)}")
                    continue
            
            logger.info(f"Generated {tasks_generated} maintenance tasks")
            return True, tasks_generated, None
            
        except Exception as e:
            logger.error(f"Error generating scheduled tasks: {str(e)}")
            return False, 0, str(e)

    async def _generate_tasks_for_schedule_period(self, schedule: MaintenanceSchedule, end_date: datetime) -> int:
        """Generate tasks for a specific schedule up to end_date"""
        tasks_generated = 0
        current_date = schedule.next_due_date or datetime.now()
        
        while current_date <= end_date:
            # Check if task already exists for this date
            existing_task = await self._check_existing_task(schedule.id, current_date)
            
            if not existing_task:
                # Generate task
                task_data = await self._create_task_from_schedule(schedule, current_date)
                success, task_id, error = await self.db.create_document(COLLECTIONS['maintenance_tasks'], task_data)
                
                if success:
                    tasks_generated += 1
                    logger.debug(f"Generated task {task_id} for schedule {schedule.id}")
                else:
                    logger.error(f"Failed to create task for schedule {schedule.id}: {error}")
            
            # Calculate next occurrence
            current_date = self._calculate_next_occurrence(schedule, current_date)
            
            # Safety break to prevent infinite loops
            if tasks_generated > 100:  # Reasonable limit
                logger.warning(f"Generated maximum tasks (100) for schedule {schedule.id}")
                break
        
        return tasks_generated

    async def _create_task_from_schedule(self, schedule: MaintenanceSchedule, scheduled_date: datetime) -> dict:
        """Create a maintenance task from a schedule"""
        # Get equipment details
        success, equipment_doc, error = await self.db.get_document(COLLECTIONS['equipment'], schedule.equipment_id)
        equipment_name = equipment_doc.get('equipment_name', 'Unknown Equipment') if success else 'Unknown Equipment'
        location = equipment_doc.get('location', 'Unknown Location') if success else 'Unknown Location'
        
        # Get template if available
        template_data = {}
        if hasattr(schedule, 'template_id') and schedule.template_id:
            success, template_doc, error = await self.db.get_document(COLLECTIONS['maintenance_templates'], schedule.template_id)
            if success:
                template_data = template_doc
        
        task_data = {
            'schedule_id': schedule.id,
            'template_id': getattr(schedule, 'template_id', None),
            'equipment_id': schedule.equipment_id,
            'building_id': schedule.building_id,
            'task_title': f"{schedule.schedule_name} - {equipment_name}",
            'task_description': schedule.description,
            'location': location,
            'category': 'preventive',
            'priority': schedule.priority,
            'task_type': 'scheduled',
            'scheduled_date': scheduled_date,
            'estimated_duration': schedule.estimated_duration or template_data.get('estimated_duration'),
            'status': 'scheduled',
            'recurrence_type': schedule.recurrence_pattern or 'none',
            'required_parts': schedule.required_parts or template_data.get('required_parts', []),
            'created_by': 'system',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        return task_data

    async def _check_existing_task(self, schedule_id: str, scheduled_date: datetime) -> bool:
        """Check if a task already exists for this schedule and date"""
        try:
            # Check for tasks on the same day
            start_of_day = scheduled_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = scheduled_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            success, tasks, error = await self.db.query_documents(
                COLLECTIONS['maintenance_tasks'],
                [
                    ('schedule_id', '==', schedule_id),
                    ('scheduled_date', '>=', start_of_day),
                    ('scheduled_date', '<=', end_of_day)
                ]
            )
            
            return success and len(tasks) > 0
            
        except Exception as e:
            logger.error(f"Error checking existing task: {str(e)}")
            return False

    # Usage-Based Scheduling
    async def check_usage_based_schedules(self) -> Tuple[bool, int, Optional[str]]:
        """Check usage-based schedules and generate tasks when thresholds are met"""
        try:
            logger.info("Checking usage-based maintenance schedules")
            
            # Get all active usage-based schedules
            success, schedules, error = await self.db.query_documents(
                COLLECTIONS['maintenance_schedules'],
                [
                    ('is_active', '==', True),
                    ('schedule_type', '==', 'usage_based')
                ]
            )
            
            if not success:
                return False, 0, f"Failed to get usage-based schedules: {error}"
            
            tasks_generated = 0
            
            for schedule_doc in schedules:
                try:
                    schedule = MaintenanceSchedule(**schedule_doc)
                    
                    # Get current usage for equipment
                    current_usage = await self._get_equipment_current_usage(schedule.equipment_id, schedule.usage_unit)
                    
                    # Get last maintenance usage
                    last_maintenance_usage = await self._get_last_maintenance_usage(schedule.equipment_id, schedule.id)
                    
                    # Check if threshold is met
                    usage_since_maintenance = current_usage - last_maintenance_usage
                    
                    if usage_since_maintenance >= schedule.usage_threshold:
                        # Generate maintenance task
                        task_data = await self._create_task_from_schedule(schedule, datetime.now())
                        task_data['task_description'] += f" (Usage threshold reached: {usage_since_maintenance} {schedule.usage_unit})"
                        
                        success, task_id, error = await self.db.create_document(COLLECTIONS['maintenance_tasks'], task_data)
                        
                        if success:
                            tasks_generated += 1
                            logger.info(f"Generated usage-based task {task_id} for equipment {schedule.equipment_id}")
                            
                            # Update schedule's last generated
                            await self.db.update_document(
                                COLLECTIONS['maintenance_schedules'],
                                schedule.id,
                                {'last_generated': datetime.now()}
                            )
                        else:
                            logger.error(f"Failed to create usage-based task: {error}")
                    
                except Exception as e:
                    logger.error(f"Error processing usage-based schedule {schedule_doc.get('id')}: {str(e)}")
                    continue
            
            logger.info(f"Generated {tasks_generated} usage-based maintenance tasks")
            return True, tasks_generated, None
            
        except Exception as e:
            logger.error(f"Error checking usage-based schedules: {str(e)}")
            return False, 0, str(e)

    async def _get_equipment_current_usage(self, equipment_id: str, usage_unit: str) -> float:
        """Get current total usage for equipment"""
        try:
            success, usage_logs, error = await self.db.query_documents(
                COLLECTIONS['equipment_usage_logs'],
                [
                    ('equipment_id', '==', equipment_id),
                    ('usage_unit', '==', usage_unit)
                ]
            )
            
            if success:
                return sum(log.get('usage_value', 0) for log in usage_logs)
            else:
                logger.warning(f"Failed to get usage logs for equipment {equipment_id}: {error}")
                return 0.0
                
        except Exception as e:
            logger.error(f"Error getting equipment usage: {str(e)}")
            return 0.0

    async def _get_last_maintenance_usage(self, equipment_id: str, schedule_id: str) -> float:
        """Get usage value at last maintenance for this schedule"""
        try:
            # Get last completed task for this schedule
            success, tasks, error = await self.db.query_documents(
                COLLECTIONS['maintenance_tasks'],
                [
                    ('equipment_id', '==', equipment_id),
                    ('schedule_id', '==', schedule_id),
                    ('status', '==', 'completed')
                ]
            )
            
            if success and tasks:
                # Sort by completed_at in descending order and get the first one
                sorted_tasks = sorted(
                    tasks, 
                    key=lambda x: x.get('completed_at', datetime.min), 
                    reverse=True
                )
                if sorted_tasks:
                    last_task = sorted_tasks[0]
                    # Return usage value recorded at completion, or 0 if not recorded
                    return last_task.get('usage_at_completion', 0.0)
            
            return 0.0
                
        except Exception as e:
            logger.error(f"Error getting last maintenance usage: {str(e)}")
            return 0.0

    # Date Calculation Utilities
    def _calculate_next_due_date(self, schedule: MaintenanceSchedule) -> datetime:
        """Calculate the next due date for a maintenance schedule"""
        try:
            if schedule.schedule_type == 'usage_based':
                # For usage-based, return current time as it's checked dynamically
                return datetime.now()
            
            base_date = datetime.now()
            
            if schedule.recurrence_pattern == 'daily':
                return base_date + timedelta(days=schedule.interval_value or 1)
            
            elif schedule.recurrence_pattern == 'weekly':
                days_ahead = (schedule.interval_value or 1) * 7
                next_date = base_date + timedelta(days=days_ahead)
                
                # Adjust to specific days if specified
                if schedule.specific_days:
                    # Find next occurrence of specified weekdays
                    weekday_map = {
                        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                        'friday': 4, 'saturday': 5, 'sunday': 6
                    }
                    target_weekdays = [weekday_map.get(day.lower()) for day in schedule.specific_days if day.lower() in weekday_map]
                    
                    if target_weekdays:
                        current_weekday = base_date.weekday()
                        days_until_next = min(
                            (day - current_weekday) % 7 or 7 
                            for day in target_weekdays
                        )
                        next_date = base_date + timedelta(days=days_until_next)
                
                return next_date
            
            elif schedule.recurrence_pattern == 'monthly':
                months_ahead = schedule.interval_value or 1
                next_date = base_date + relativedelta(months=months_ahead)
                
                # Adjust to specific dates if specified
                if schedule.specific_dates:
                    target_day = min(schedule.specific_dates)  # Use first specified date
                    next_date = next_date.replace(day=min(target_day, 28))  # Ensure valid day
                
                return next_date
            
            elif schedule.recurrence_pattern == 'quarterly':
                return base_date + relativedelta(months=3 * (schedule.interval_value or 1))
            
            elif schedule.recurrence_pattern == 'yearly':
                return base_date + relativedelta(years=schedule.interval_value or 1)
            
            else:
                # Default to monthly if pattern not recognized
                return base_date + relativedelta(months=1)
                
        except Exception as e:
            logger.error(f"Error calculating next due date: {str(e)}")
            return datetime.now() + timedelta(days=30)  # Default to 30 days

    def _calculate_next_occurrence(self, schedule: MaintenanceSchedule, current_date: datetime) -> datetime:
        """Calculate the next occurrence after current_date"""
        try:
            if schedule.recurrence_pattern == 'daily':
                return current_date + timedelta(days=schedule.interval_value or 1)
            
            elif schedule.recurrence_pattern == 'weekly':
                return current_date + timedelta(days=7 * (schedule.interval_value or 1))
            
            elif schedule.recurrence_pattern == 'monthly':
                return current_date + relativedelta(months=schedule.interval_value or 1)
            
            elif schedule.recurrence_pattern == 'quarterly':
                return current_date + relativedelta(months=3 * (schedule.interval_value or 1))
            
            elif schedule.recurrence_pattern == 'yearly':
                return current_date + relativedelta(years=schedule.interval_value or 1)
            
            else:
                return current_date + timedelta(days=30)  # Default
                
        except Exception as e:
            logger.error(f"Error calculating next occurrence: {str(e)}")
            return current_date + timedelta(days=30)

    # Task Management
    async def get_maintenance_tasks(self, building_id: str, filters: Optional[Dict] = None) -> Tuple[bool, List[dict], Optional[str]]:
        """Get maintenance tasks with optional filters"""
        try:
            query_filters = [('building_id', '==', building_id)]
            
            if filters:
                if 'status' in filters:
                    query_filters.append(('status', '==', filters['status']))
                if 'assigned_to' in filters:
                    query_filters.append(('assigned_to', '==', filters['assigned_to']))
                if 'equipment_id' in filters:
                    query_filters.append(('equipment_id', '==', filters['equipment_id']))
                if 'category' in filters:
                    query_filters.append(('category', '==', filters['category']))
                if 'date_from' in filters:
                    query_filters.append(('scheduled_date', '>=', filters['date_from']))
                if 'date_to' in filters:
                    query_filters.append(('scheduled_date', '<=', filters['date_to']))
            
            success, tasks, error = await self.db.query_documents(
                COLLECTIONS['maintenance_tasks'], 
                query_filters
            )
            
            if success:
                # Sort by scheduled_date
                sorted_tasks = sorted(
                    tasks, 
                    key=lambda x: x.get('scheduled_date', datetime.min)
                )
                return True, sorted_tasks, None
            else:
                logger.error(f"Failed to get maintenance tasks: {error}")
                return False, [], error
                
        except Exception as e:
            logger.error(f"Error getting maintenance tasks: {str(e)}")
            return False, [], str(e)

    async def update_task_status(self, task_id: str, status: str, updated_by: str, notes: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Update maintenance task status"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now()
            }
            
            if status == 'in_progress':
                update_data['started_at'] = datetime.now()
            elif status == 'completed':
                update_data['completed_at'] = datetime.now()
            
            if notes:
                update_data['completion_notes'] = notes
            
            success, error = await self.db.update_document(COLLECTIONS['maintenance_tasks'], task_id, update_data)
            
            if success:
                logger.info(f"Updated task {task_id} status to {status}")
                
                # If task is completed, handle recurring task generation
                if status == 'completed':
                    await self._handle_task_completion(task_id)
                
                return True, None
            else:
                logger.error(f"Failed to update task status: {error}")
                return False, error
                
        except Exception as e:
            logger.error(f"Error updating task status: {str(e)}")
            return False, str(e)

    async def _handle_task_completion(self, task_id: str):
        """Handle post-completion actions for a maintenance task"""
        try:
            # Get completed task
            success, task_doc, error = await self.db.get_document(COLLECTIONS['maintenance_tasks'], task_id)
            if not success:
                return
            
            task = MaintenanceTask(**task_doc)
            
            # If task has a schedule, update the schedule's next due date
            if task.schedule_id:
                success, schedule_doc, error = await self.db.get_document(COLLECTIONS['maintenance_schedules'], task.schedule_id)
                if success:
                    schedule = MaintenanceSchedule(**schedule_doc)
                    next_due = self._calculate_next_due_date(schedule)
                    
                    await self.db.update_document(
                        COLLECTIONS['maintenance_schedules'],
                        task.schedule_id,
                        {'next_due_date': next_due}
                    )
            
            logger.info(f"Handled completion for task {task_id}")
            
        except Exception as e:
            logger.error(f"Error handling task completion: {str(e)}")

    async def _generate_tasks_for_schedule(self, schedule_id: str, schedule: MaintenanceSchedule):
        """Generate initial tasks for a new schedule"""
        try:
            # Generate tasks for the next 30 days
            end_date = datetime.now() + timedelta(days=30)
            await self._generate_tasks_for_schedule_period(schedule, end_date)
        except Exception as e:
            logger.error(f"Error generating initial tasks for schedule {schedule_id}: {str(e)}")

# Create singleton instance
maintenance_scheduler_service = MaintenanceSchedulerService()
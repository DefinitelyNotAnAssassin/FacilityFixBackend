from typing import Dict, List, Any
from datetime import datetime, timedelta, timezone
from app.database.firestore_client import FirestoreClient
from app.services.concern_slip_service import ConcernSlipService
from app.services.job_service_service import JobServiceService
from app.services.work_order_permit_service import WorkOrderPermitService
from app.services.maintenance_task_service import MaintenanceTaskService
import logging

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self):
        self.db = FirestoreClient()
        self.concern_service = ConcernSlipService()
        self.job_service = JobServiceService()
        self.permit_service = WorkOrderPermitService()
        self.maintenance_service = MaintenanceTaskService()

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get key statistics for admin dashboard with comprehensive data from all sources"""
        try:
            # Get data from all sources
            all_concerns = await self.concern_service.get_all_concern_slips()
            all_job_services = await self.job_service.get_all_job_services()
            all_maintenance_tasks = await self.maintenance_service.list_tasks()
            
            # Calculate concern slip metrics
            pending_concerns = [c for c in all_concerns if c.status == "pending"]
            approved_concerns = [c for c in all_concerns if c.status == "approved"]
            completed_concerns = [c for c in all_concerns if c.status == "completed"]
            
            # Calculate job service metrics
            active_jobs = [j for j in all_job_services if j.status in ["assigned", "in_progress"]]
            completed_jobs = [j for j in all_job_services if j.status == "completed"]
            
            # Calculate maintenance task metrics
            scheduled_maintenance = [m for m in all_maintenance_tasks if m.status == "scheduled"]
            completed_maintenance = [m for m in all_maintenance_tasks if m.status == "completed"]
            overdue_maintenance = [m for m in all_maintenance_tasks if m.status == "overdue"]
            
            # Calculate work order permits
            try:
                all_permits = await self.permit_service.get_all_permits()
                pending_permits = [p for p in all_permits if p.status == "pending"]
            except Exception as e:
                logger.warning(f"Could not retrieve work permits: {e}")
                pending_permits = []
            
            # Calculate completion rates
            total_concerns = len(all_concerns)
            total_jobs = len(all_job_services)
            total_maintenance = len(all_maintenance_tasks)
            
            concern_completion_rate = (len(completed_concerns) / total_concerns * 100) if total_concerns > 0 else 0
            job_completion_rate = (len(completed_jobs) / total_jobs * 100) if total_jobs > 0 else 0
            maintenance_completion_rate = (len(completed_maintenance) / total_maintenance * 100) if total_maintenance > 0 else 0
            
            # Overall completion rate
            total_tasks = total_concerns + total_jobs + total_maintenance
            total_completed = len(completed_concerns) + len(completed_jobs) + len(completed_maintenance)
            overall_completion_rate = (total_completed / total_tasks * 100) if total_tasks > 0 else 0

            # Calculate items completed today
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            completed_today = 0

            for concern in completed_concerns:
                if concern.updated_at:
                    # Normalize both datetimes to naive for comparison
                    updated_at = concern.updated_at.replace(tzinfo=None) if concern.updated_at.tzinfo else concern.updated_at
                    if updated_at >= today_start:
                        completed_today += 1

            for job in completed_jobs:
                if job.updated_at:
                    updated_at = job.updated_at.replace(tzinfo=None) if job.updated_at.tzinfo else job.updated_at
                    if updated_at >= today_start:
                        completed_today += 1

            for maintenance in completed_maintenance:
                if maintenance.updated_at:
                    updated_at = maintenance.updated_at.replace(tzinfo=None) if maintenance.updated_at.tzinfo else maintenance.updated_at
                    if updated_at >= today_start:
                        completed_today += 1

            # Calculate average resolution time (in days)
            resolution_times = []

            for concern in completed_concerns:
                if concern.created_at and concern.updated_at:
                    # Normalize both datetimes to naive for comparison
                    created_at = concern.created_at.replace(tzinfo=None) if concern.created_at.tzinfo else concern.created_at
                    updated_at = concern.updated_at.replace(tzinfo=None) if concern.updated_at.tzinfo else concern.updated_at
                    time_diff = updated_at - created_at
                    resolution_times.append(time_diff.total_seconds() / 86400)  # Convert to days

            for job in completed_jobs:
                if job.created_at and job.updated_at:
                    created_at = job.created_at.replace(tzinfo=None) if job.created_at.tzinfo else job.created_at
                    updated_at = job.updated_at.replace(tzinfo=None) if job.updated_at.tzinfo else job.updated_at
                    time_diff = updated_at - created_at
                    resolution_times.append(time_diff.total_seconds() / 86400)

            for maintenance in completed_maintenance:
                if maintenance.created_at and maintenance.updated_at:
                    created_at = maintenance.created_at.replace(tzinfo=None) if maintenance.created_at.tzinfo else maintenance.created_at
                    updated_at = maintenance.updated_at.replace(tzinfo=None) if maintenance.updated_at.tzinfo else maintenance.updated_at
                    time_diff = updated_at - created_at
                    resolution_times.append(time_diff.total_seconds() / 86400)

            average_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0

            # Calculate comparison metrics
            # Yesterday's completed count
            yesterday_start = (datetime.utcnow() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday_start + timedelta(days=1)
            completed_yesterday = 0

            for concern in completed_concerns:
                if concern.updated_at:
                    updated_at = concern.updated_at.replace(tzinfo=None) if concern.updated_at.tzinfo else concern.updated_at
                    if yesterday_start <= updated_at < yesterday_end:
                        completed_yesterday += 1

            for job in completed_jobs:
                if job.updated_at:
                    updated_at = job.updated_at.replace(tzinfo=None) if job.updated_at.tzinfo else job.updated_at
                    if yesterday_start <= updated_at < yesterday_end:
                        completed_yesterday += 1

            for maintenance in completed_maintenance:
                if maintenance.updated_at:
                    updated_at = maintenance.updated_at.replace(tzinfo=None) if maintenance.updated_at.tzinfo else maintenance.updated_at
                    if yesterday_start <= updated_at < yesterday_end:
                        completed_yesterday += 1

            # Last week's pending count (7 days ago)
            last_week_date = datetime.utcnow() - timedelta(days=7)
            # Note: For simplicity, we'll use current pending as baseline (proper implementation would store historical data)
            # This is a placeholder - in production, you'd query historical snapshots

            # Last month's total requests
            last_month_start = (datetime.utcnow() - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            total_requests_last_month = 0

            for concern in all_concerns:
                if concern.created_at:
                    created_at = concern.created_at.replace(tzinfo=None) if concern.created_at.tzinfo else concern.created_at
                    if created_at < last_month_start:
                        total_requests_last_month += 1

            for job in all_job_services:
                if job.created_at:
                    created_at = job.created_at.replace(tzinfo=None) if job.created_at.tzinfo else job.created_at
                    if created_at < last_month_start:
                        total_requests_last_month += 1

            for maintenance in all_maintenance_tasks:
                if maintenance.created_at:
                    created_at = maintenance.created_at.replace(tzinfo=None) if maintenance.created_at.tzinfo else maintenance.created_at
                    if created_at < last_month_start:
                        total_requests_last_month += 1

            # Calculate percentage changes
            completed_today_change = 0.0
            if completed_yesterday > 0:
                completed_today_change = ((completed_today - completed_yesterday) / completed_yesterday) * 100

            total_requests_change = 0.0
            if total_requests_last_month > 0:
                requests_this_month = total_tasks - total_requests_last_month
                total_requests_change = ((requests_this_month - total_requests_last_month) / total_requests_last_month) * 100

            # For pending items and resolution time, use simple heuristics
            # (Proper implementation would require historical data storage)
            pending_items_change = 0.0  # Placeholder
            resolution_time_change = 0.0  # Placeholder

            return {
                "concern_slips": {
                    "total_requests": total_concerns,
                    "pending_concerns": len(pending_concerns),
                    "approved_concerns": len(approved_concerns),
                    "completed_concerns": len(completed_concerns),
                    "completion_rate": round(concern_completion_rate, 2)
                },
                "job_services": {
                    "total_jobs": total_jobs,
                    "active_jobs": len(active_jobs),
                    "completed_jobs": len(completed_jobs),
                    "completion_rate": round(job_completion_rate, 2)
                },
                "maintenance_tasks": {
                    "total_tasks": total_maintenance,
                    "scheduled_tasks": len(scheduled_maintenance),
                    "completed_tasks": len(completed_maintenance),
                    "overdue_tasks": len(overdue_maintenance),
                    "completion_rate": round(maintenance_completion_rate, 2)
                },
                "work_permits": {
                    "pending_permits": len(pending_permits)
                },
                "overall_metrics": {
                    "total_requests": total_tasks,
                    "total_completed": total_completed,
                    "completion_rate": round(overall_completion_rate, 2),
                    "pending_items": len(pending_concerns) + len(active_jobs) + len(scheduled_maintenance) + len(pending_permits),
                    "completed_today": completed_today,
                    "average_resolution_time_days": round(average_resolution_time, 2),
                    "comparisons": {
                        "total_requests_change": abs(round(total_requests_change, 1)),
                        "total_requests_increasing": total_requests_change >= 0,
                        "pending_items_change": abs(round(pending_items_change, 1)),
                        "pending_items_increasing": pending_items_change >= 0,
                        "completed_today_change": abs(round(completed_today_change, 1)),
                        "completed_today_increasing": completed_today_change >= 0,
                        "resolution_time_change": abs(round(resolution_time_change, 1)),
                        "resolution_time_improving": resolution_time_change <= 0  # Lower is better for resolution time
                    }
                },
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {str(e)}")
            raise Exception(f"Failed to get dashboard stats: {str(e)}")

    async def get_work_order_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get work order trends over specified period from all data sources"""
        try:
            # Use timezone-naive datetime to match the data in the database
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
        
            # Get all data sources in date range
            all_concerns = await self.concern_service.get_all_concern_slips()
            all_job_services = await self.job_service.get_all_job_services()
            all_maintenance_tasks = await self.maintenance_service.list_tasks()
            
            # Filter by date range
            filtered_concerns = self._filter_by_date_range(all_concerns, start_date, end_date)
            filtered_jobs = self._filter_by_date_range(all_job_services, start_date, end_date)
            filtered_maintenance = self._filter_by_date_range(all_maintenance_tasks, start_date, end_date)
            
            # Group by day for trends
            daily_concerns = self._group_by_day(filtered_concerns)
            daily_jobs = self._group_by_day(filtered_jobs)
            daily_maintenance = self._group_by_day(filtered_maintenance)
            
            # Combine daily counts
            all_dates = set(daily_concerns.keys()) | set(daily_jobs.keys()) | set(daily_maintenance.keys())
            daily_totals = {}
            
            for date_key in all_dates:
                daily_totals[date_key] = {
                    "concern_slips": daily_concerns.get(date_key, 0),
                    "job_services": daily_jobs.get(date_key, 0),
                    "maintenance_tasks": daily_maintenance.get(date_key, 0),
                    "total": daily_concerns.get(date_key, 0) + daily_jobs.get(date_key, 0) + daily_maintenance.get(date_key, 0)
                }
            
            total_items = len(filtered_concerns) + len(filtered_jobs) + len(filtered_maintenance)
            
            return {
                "period_days": days,
                "summary": {
                    "total_concern_slips": len(filtered_concerns),
                    "total_job_services": len(filtered_jobs),
                    "total_maintenance_tasks": len(filtered_maintenance),
                    "total_items": total_items,
                    "average_per_day": total_items / days if days > 0 else 0
                },
                "daily_breakdown": daily_totals,
                "trends": {
                    "concern_slip_trend": self._calculate_trend(daily_concerns),
                    "job_service_trend": self._calculate_trend(daily_jobs),
                    "maintenance_trend": self._calculate_trend(daily_maintenance)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get work order trends: {str(e)}")
            raise Exception(f"Failed to get work order trends: {str(e)}")

    async def get_category_breakdown(self) -> Dict[str, Any]:
        """Get comprehensive breakdown of issues by category across all data sources"""
        try:
            # Get all data
            all_concerns = await self.concern_service.get_all_concern_slips()
            all_job_services = await self.job_service.get_all_job_services()
            all_maintenance_tasks = await self.maintenance_service.list_tasks()
            
            # Analyze categories
            concern_categories = {}
            concern_priorities = {}
            concern_statuses = {}
            
            job_categories = {}
            job_priorities = {}
            job_statuses = {}
            
            maintenance_categories = {}
            maintenance_priorities = {}
            maintenance_statuses = {}
            
            # Process concern slips
            for concern in all_concerns:
                category = concern.category or "uncategorized"
                priority = concern.priority or "medium"
                status = concern.status or "pending"
                
                concern_categories[category] = concern_categories.get(category, 0) + 1
                concern_priorities[priority] = concern_priorities.get(priority, 0) + 1
                concern_statuses[status] = concern_statuses.get(status, 0) + 1
            
            # Process job services
            for job in all_job_services:
                category = job.category or "uncategorized"
                priority = job.priority or "medium"
                status = job.status or "pending"
                
                job_categories[category] = job_categories.get(category, 0) + 1
                job_priorities[priority] = job_priorities.get(priority, 0) + 1
                job_statuses[status] = job_statuses.get(status, 0) + 1
            
            # Process maintenance tasks
            for task in all_maintenance_tasks:
                category = task.category or "preventive"
                priority = task.priority or "medium"
                status = task.status or "scheduled"
                
                maintenance_categories[category] = maintenance_categories.get(category, 0) + 1
                maintenance_priorities[priority] = maintenance_priorities.get(priority, 0) + 1
                maintenance_statuses[status] = maintenance_statuses.get(status, 0) + 1
            
            # Combine categories for overall view
            all_categories = {}
            for category in set(list(concern_categories.keys()) + list(job_categories.keys()) + list(maintenance_categories.keys())):
                all_categories[category] = (
                    concern_categories.get(category, 0) + 
                    job_categories.get(category, 0) + 
                    maintenance_categories.get(category, 0)
                )
            
            return {
                "concern_slips": {
                    "categories": concern_categories,
                    "priorities": concern_priorities,
                    "statuses": concern_statuses,
                    "total_analyzed": len(all_concerns)
                },
                "job_services": {
                    "categories": job_categories,
                    "priorities": job_priorities,
                    "statuses": job_statuses,
                    "total_analyzed": len(all_job_services)
                },
                "maintenance_tasks": {
                    "categories": maintenance_categories,
                    "priorities": maintenance_priorities,
                    "statuses": maintenance_statuses,
                    "total_analyzed": len(all_maintenance_tasks)
                },
                "combined_overview": {
                    "categories": all_categories,
                    "total_items": len(all_concerns) + len(all_job_services) + len(all_maintenance_tasks)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get category breakdown: {str(e)}")
            raise Exception(f"Failed to get category breakdown: {str(e)}")

    def _filter_by_date_range(self, items: List, start_date: datetime, end_date: datetime) -> List:
        """Filter items by date range with proper timezone handling"""
        filtered_items = []
        for item in items:
            item_date = item.created_at
            if item_date is None:
                continue
            
            # Convert all datetimes to the same timezone type for comparison
            # If start/end dates are timezone-naive (utc), ensure item_date is also naive
            if start_date.tzinfo is None and end_date.tzinfo is None:
                if item_date.tzinfo is not None:
                    item_date = item_date.replace(tzinfo=None)
            # If start/end dates are timezone-aware, ensure item_date is also aware
            else:
                if item_date.tzinfo is None:
                    item_date = item_date.replace(tzinfo=timezone.utc)
                if start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=timezone.utc)
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
            
            if start_date <= item_date <= end_date:
                filtered_items.append(item)
        
        return filtered_items

    def _group_by_day(self, items: List) -> Dict[str, int]:
        """Group items by day with proper timezone handling"""
        daily_counts = {}
        for item in items:
            item_date = item.created_at
            if item_date is None:
                continue
            
            # No need to modify timezone for grouping - just format as string
            date_key = item_date.strftime("%Y-%m-%d")
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
        
        return daily_counts

    def _calculate_trend(self, daily_data: Dict[str, int]) -> str:
        """Calculate trend direction from daily data"""
        if len(daily_data) < 2:
            return "stable"
        
        dates = sorted(daily_data.keys())
        first_half = sum(daily_data[date] for date in dates[:len(dates)//2])
        second_half = sum(daily_data[date] for date in dates[len(dates)//2:])
        
        if second_half > first_half * 1.1:
            return "increasing"
        elif second_half < first_half * 0.9:
            return "decreasing"
        else:
            return "stable"

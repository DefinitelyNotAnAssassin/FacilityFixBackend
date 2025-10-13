from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import logging
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

class ReportingService:
    def __init__(self):
        self.db = database_service
        self.analytics = AnalyticsService()

    async def generate_repair_trends_report(self, building_id: str, period: str = "monthly") -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Generate comprehensive repair trends report with Pandas analytics"""
        try:
            end_date = datetime.now()
            if period == "weekly":
                start_date = end_date - timedelta(weeks=12)  # 12 weeks
            elif period == "monthly":
                start_date = end_date - timedelta(days=365)  # 12 months
            elif period == "quarterly":
                start_date = end_date - timedelta(days=730)  # 2 years
            else:
                start_date = end_date - timedelta(days=30)  # default 30 days

            filters = [('building_id', '==', building_id)] if building_id else []
            
            # Get concern slips
            success, concern_slips, error = self.db.query_documents(
                COLLECTIONS['concern_slips'], filters
            )
            if not success:
                return False, {}, f"Failed to get concern slips: {error}"

            # Get job services
            success, job_services, error = self.db.query_documents(
                COLLECTIONS['job_services'], filters
            )
            if not success:
                return False, {}, f"Failed to get job services: {error}"

            concern_df = pd.DataFrame(concern_slips)
            job_df = pd.DataFrame(job_services)

            if not concern_df.empty:
                concern_df['created_at'] = pd.to_datetime(concern_df['created_at'])
                concern_df = concern_df[concern_df['created_at'] >= start_date]

            if not job_df.empty:
                job_df['created_at'] = pd.to_datetime(job_df['created_at'])
                job_df['completed_at'] = pd.to_datetime(job_df['completed_at'])
                job_df = job_df[job_df['created_at'] >= start_date]

            report = {
                'building_id': building_id,
                'period': period,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'summary': self._calculate_repair_summary(concern_df, job_df),
                'trends': self._calculate_repair_trends(concern_df, job_df, period),
                'category_analysis': self._analyze_repair_categories(concern_df),
                'performance_metrics': self._calculate_performance_metrics(job_df),
                'heat_map_data': await self._generate_heat_map_data(building_id, concern_df),
                'generated_at': datetime.now().isoformat()
            }

            return True, report, None

        except Exception as e:
            logger.error(f"Error generating repair trends report: {str(e)}")
            return False, {}, str(e)

    async def generate_staff_performance_report(self, staff_id: Optional[str] = None, building_id: Optional[str] = None, days: int = 30) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Generate staff performance analytics report"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            filters = [('created_at', '>=', start_date)]
            if building_id:
                filters.append(('building_id', '==', building_id))
            if staff_id:
                filters.append(('assigned_to', '==', staff_id))

            success, job_services, error = self.db.query_documents(
                COLLECTIONS['job_services'], filters
            )
            if not success:
                return False, {}, f"Failed to get job services: {error}"

            success, maintenance_tasks, error = self.db.query_documents(
                COLLECTIONS['maintenance_tasks'], filters
            )
            if not success:
                return False, {}, f"Failed to get maintenance tasks: {error}"

            job_df = pd.DataFrame(job_services)
            maintenance_df = pd.DataFrame(maintenance_tasks)

            if not job_df.empty:
                job_df['created_at'] = pd.to_datetime(job_df['created_at'])
                job_df['completed_at'] = pd.to_datetime(job_df['completed_at'])

            if not maintenance_df.empty:
                maintenance_df['created_at'] = pd.to_datetime(maintenance_df['created_at'])
                maintenance_df['completed_at'] = pd.to_datetime(maintenance_df['completed_at'])

            report = {
                'staff_id': staff_id,
                'building_id': building_id,
                'period_days': days,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'job_performance': self._analyze_job_performance(job_df),
                'maintenance_performance': self._analyze_maintenance_performance(maintenance_df),
                'workload_distribution': self._analyze_workload_distribution(job_df, maintenance_df),
                'efficiency_metrics': self._calculate_efficiency_metrics(job_df, maintenance_df),
                'generated_at': datetime.now().isoformat()
            }

            return True, report, None

        except Exception as e:
            logger.error(f"Error generating staff performance report: {str(e)}")
            return False, {}, str(e)

    async def generate_inventory_consumption_report(self, building_id: str, period: str = "monthly") -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Generate inventory consumption and trends report"""
        try:
            filters = [('building_id', '==', building_id)] if building_id else []
            
            success, transactions, error = self.db.query_documents(
                COLLECTIONS['inventory_transactions'], filters
            )
            if not success:
                return False, {}, f"Failed to get inventory transactions: {error}"

            success, inventory_items, error = self.db.query_documents(
                COLLECTIONS['inventory'], filters
            )
            if not success:
                return False, {}, f"Failed to get inventory items: {error}"

            trans_df = pd.DataFrame(transactions)
            inventory_df = pd.DataFrame(inventory_items)

            if not trans_df.empty:
                trans_df['created_at'] = pd.to_datetime(trans_df['created_at'])

            report = {
                'building_id': building_id,
                'period': period,
                'consumption_analysis': self._analyze_inventory_consumption(trans_df, inventory_df),
                'top_consumed_items': self._get_top_consumed_items(trans_df, inventory_df),
                'cost_analysis': self._analyze_inventory_costs(trans_df),
                'stock_level_trends': self._analyze_stock_trends(inventory_df),
                'reorder_recommendations': self._generate_reorder_recommendations(inventory_df, trans_df),
                'generated_at': datetime.now().isoformat()
            }

            return True, report, None

        except Exception as e:
            logger.error(f"Error generating inventory consumption report: {str(e)}")
            return False, {}, str(e)

    def _calculate_repair_summary(self, concern_df: pd.DataFrame, job_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate repair summary statistics"""
        try:
            summary = {
                'total_concerns': len(concern_df),
                'total_jobs': len(job_df),
                'completed_jobs': len(job_df[job_df['status'] == 'completed']) if not job_df.empty else 0,
                'pending_concerns': len(concern_df[concern_df['status'] == 'pending']) if not concern_df.empty else 0,
                'in_progress_jobs': len(job_df[job_df['status'] == 'in_progress']) if not job_df.empty else 0,
                'completion_rate': 0,
                'average_resolution_time': 0
            }

            if not job_df.empty and len(job_df) > 0:
                completed_jobs = job_df[job_df['status'] == 'completed']
                summary['completion_rate'] = (len(completed_jobs) / len(job_df)) * 100

                if not completed_jobs.empty:
                    resolution_times = (completed_jobs['completed_at'] - completed_jobs['created_at']).dt.total_seconds() / 3600
                    summary['average_resolution_time'] = resolution_times.mean()

            return summary

        except Exception as e:
            logger.error(f"Error calculating repair summary: {str(e)}")
            return {}

    def _calculate_repair_trends(self, concern_df: pd.DataFrame, job_df: pd.DataFrame, period: str) -> Dict[str, Any]:
        """Calculate repair trends over time"""
        try:
            trends = {
                'concern_trends': {},
                'completion_trends': {},
                'category_trends': {}
            }

            if not concern_df.empty:
                # Group by time period
                if period == "weekly":
                    concern_trends = concern_df.groupby(concern_df['created_at'].dt.to_period('W')).size()
                elif period == "monthly":
                    concern_trends = concern_df.groupby(concern_df['created_at'].dt.to_period('M')).size()
                else:
                    concern_trends = concern_df.groupby(concern_df['created_at'].dt.date).size()

                trends['concern_trends'] = concern_trends.to_dict()

            if not job_df.empty:
                completed_jobs = job_df[job_df['status'] == 'completed']
                if not completed_jobs.empty:
                    if period == "weekly":
                        completion_trends = completed_jobs.groupby(completed_jobs['completed_at'].dt.to_period('W')).size()
                    elif period == "monthly":
                        completion_trends = completed_jobs.groupby(completed_jobs['completed_at'].dt.to_period('M')).size()
                    else:
                        completion_trends = completed_jobs.groupby(completed_jobs['completed_at'].dt.date).size()

                    trends['completion_trends'] = completion_trends.to_dict()

            return trends

        except Exception as e:
            logger.error(f"Error calculating repair trends: {str(e)}")
            return {}

    def _analyze_repair_categories(self, concern_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze repair requests by category"""
        try:
            if concern_df.empty:
                return {}

            category_analysis = {
                'category_distribution': concern_df['category'].value_counts().to_dict(),
                'priority_distribution': concern_df['priority'].value_counts().to_dict(),
                'category_by_priority': concern_df.groupby(['category', 'priority']).size().to_dict()
            }

            return category_analysis

        except Exception as e:
            logger.error(f"Error analyzing repair categories: {str(e)}")
            return {}

    def _calculate_performance_metrics(self, job_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate performance metrics"""
        try:
            if job_df.empty:
                return {}

            completed_jobs = job_df[job_df['status'] == 'completed']
            
            metrics = {
                'total_jobs': len(job_df),
                'completed_jobs': len(completed_jobs),
                'completion_rate': (len(completed_jobs) / len(job_df)) * 100 if len(job_df) > 0 else 0,
                'average_completion_time': 0,
                'on_time_completion_rate': 0
            }

            if not completed_jobs.empty:
                # Calculate average completion time
                completion_times = (completed_jobs['completed_at'] - completed_jobs['created_at']).dt.total_seconds() / 3600
                metrics['average_completion_time'] = completion_times.mean()

                # Calculate on-time completion rate (assuming scheduled_date exists)
                if 'scheduled_date' in completed_jobs.columns:
                    on_time_jobs = completed_jobs[completed_jobs['completed_at'] <= completed_jobs['scheduled_date']]
                    metrics['on_time_completion_rate'] = (len(on_time_jobs) / len(completed_jobs)) * 100

            return metrics

        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")
            return {}

    async def _generate_heat_map_data(self, building_id: str, concern_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate heat map data for frequently reported areas"""
        try:
            if concern_df.empty:
                return {}

            location_frequency = concern_df['location'].value_counts().to_dict()
            category_location = concern_df.groupby(['location', 'category']).size().to_dict()

            heat_map_data = {
                'location_frequency': location_frequency,
                'category_by_location': category_location,
                'high_frequency_areas': list(concern_df['location'].value_counts().head(10).index)
            }

            return heat_map_data

        except Exception as e:
            logger.error(f"Error generating heat map data: {str(e)}")
            return {}

    def _analyze_job_performance(self, job_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze job performance metrics"""
        try:
            if job_df.empty:
                return {}

            performance = {
                'total_jobs': len(job_df),
                'completed_jobs': len(job_df[job_df['status'] == 'completed']),
                'in_progress_jobs': len(job_df[job_df['status'] == 'in_progress']),
                'average_completion_time': 0,
                'jobs_by_category': job_df['category'].value_counts().to_dict()
            }

            completed_jobs = job_df[job_df['status'] == 'completed']
            if not completed_jobs.empty:
                completion_times = (completed_jobs['completed_at'] - completed_jobs['created_at']).dt.total_seconds() / 3600
                performance['average_completion_time'] = completion_times.mean()

            return performance

        except Exception as e:
            logger.error(f"Error analyzing job performance: {str(e)}")
            return {}

    def _analyze_maintenance_performance(self, maintenance_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze maintenance performance metrics"""
        try:
            if maintenance_df.empty:
                return {}

            performance = {
                'total_tasks': len(maintenance_df),
                'completed_tasks': len(maintenance_df[maintenance_df['status'] == 'completed']),
                'scheduled_tasks': len(maintenance_df[maintenance_df['status'] == 'scheduled']),
                'overdue_tasks': len(maintenance_df[maintenance_df['status'] == 'overdue']),
                'tasks_by_category': maintenance_df['category'].value_counts().to_dict()
            }

            return performance

        except Exception as e:
            logger.error(f"Error analyzing maintenance performance: {str(e)}")
            return {}

    def _analyze_workload_distribution(self, job_df: pd.DataFrame, maintenance_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze workload distribution across staff"""
        try:
            workload = {
                'job_distribution': {},
                'maintenance_distribution': {},
                'total_workload': {}
            }

            if not job_df.empty and 'assigned_to' in job_df.columns:
                workload['job_distribution'] = job_df['assigned_to'].value_counts().to_dict()

            if not maintenance_df.empty and 'assigned_to' in maintenance_df.columns:
                workload['maintenance_distribution'] = maintenance_df['assigned_to'].value_counts().to_dict()

            # Combine workloads
            all_staff = set()
            if workload['job_distribution']:
                all_staff.update(workload['job_distribution'].keys())
            if workload['maintenance_distribution']:
                all_staff.update(workload['maintenance_distribution'].keys())

            for staff in all_staff:
                job_count = workload['job_distribution'].get(staff, 0)
                maintenance_count = workload['maintenance_distribution'].get(staff, 0)
                workload['total_workload'][staff] = job_count + maintenance_count

            return workload

        except Exception as e:
            logger.error(f"Error analyzing workload distribution: {str(e)}")
            return {}

    def _calculate_efficiency_metrics(self, job_df: pd.DataFrame, maintenance_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate efficiency metrics"""
        try:
            metrics = {
                'job_efficiency': 0,
                'maintenance_efficiency': 0,
                'overall_efficiency': 0
            }

            # Job efficiency (completion rate)
            if not job_df.empty:
                completed_jobs = len(job_df[job_df['status'] == 'completed'])
                metrics['job_efficiency'] = (completed_jobs / len(job_df)) * 100

            # Maintenance efficiency
            if not maintenance_df.empty:
                completed_maintenance = len(maintenance_df[maintenance_df['status'] == 'completed'])
                metrics['maintenance_efficiency'] = (completed_maintenance / len(maintenance_df)) * 100

            # Overall efficiency
            total_tasks = len(job_df) + len(maintenance_df)
            total_completed = len(job_df[job_df['status'] == 'completed']) + len(maintenance_df[maintenance_df['status'] == 'completed'])
            if total_tasks > 0:
                metrics['overall_efficiency'] = (total_completed / total_tasks) * 100

            return metrics

        except Exception as e:
            logger.error(f"Error calculating efficiency metrics: {str(e)}")
            return {}

    def _analyze_inventory_consumption(self, trans_df: pd.DataFrame, inventory_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze inventory consumption patterns"""
        try:
            if trans_df.empty:
                return {}

            consumption_data = trans_df[trans_df['transaction_type'] == 'out']
            
            analysis = {
                'total_transactions': len(consumption_data),
                'total_quantity_consumed': consumption_data['quantity'].sum(),
                'consumption_by_department': consumption_data.groupby('reference_type')['quantity'].sum().to_dict() if 'reference_type' in consumption_data.columns else {},
                'monthly_consumption': consumption_data.groupby(consumption_data['created_at'].dt.to_period('M'))['quantity'].sum().to_dict()
            }

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing inventory consumption: {str(e)}")
            return {}

    def _get_top_consumed_items(self, trans_df: pd.DataFrame, inventory_df: pd.DataFrame, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get top consumed inventory items"""
        try:
            if trans_df.empty or inventory_df.empty:
                return []

            consumption_data = trans_df[trans_df['transaction_type'] == 'out']
            top_items = consumption_data.groupby('inventory_id')['quantity'].sum().nlargest(top_n)

            result = []
            for inventory_id, quantity in top_items.items():
                item_info = inventory_df[inventory_df['id'] == inventory_id]
                if not item_info.empty:
                    result.append({
                        'inventory_id': inventory_id,
                        'item_name': item_info.iloc[0]['item_name'],
                        'total_consumed': quantity,
                        'department': item_info.iloc[0]['department'],
                        'classification': item_info.iloc[0]['classification']
                    })

            return result

        except Exception as e:
            logger.error(f"Error getting top consumed items: {str(e)}")
            return []

    def _analyze_inventory_costs(self, trans_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze inventory costs"""
        try:
            if trans_df.empty:
                return {}

            cost_analysis = {
                'total_cost_consumed': 0,
                'total_cost_restocked': 0,
                'monthly_cost_trends': {}
            }

            # Calculate costs for outgoing transactions
            out_transactions = trans_df[trans_df['transaction_type'] == 'out']
            if not out_transactions.empty and 'total_cost' in out_transactions.columns:
                cost_analysis['total_cost_consumed'] = out_transactions['total_cost'].sum()

            # Calculate costs for incoming transactions
            in_transactions = trans_df[trans_df['transaction_type'] == 'in']
            if not in_transactions.empty and 'total_cost' in in_transactions.columns:
                cost_analysis['total_cost_restocked'] = in_transactions['total_cost'].sum()

            return cost_analysis

        except Exception as e:
            logger.error(f"Error analyzing inventory costs: {str(e)}")
            return {}

    def _analyze_stock_trends(self, inventory_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze stock level trends"""
        try:
            if inventory_df.empty:
                return {}

            trends = {
                'low_stock_items': len(inventory_df[inventory_df['current_stock'] <= inventory_df['reorder_level']]),
                'out_of_stock_items': len(inventory_df[inventory_df['current_stock'] == 0]),
                'overstocked_items': 0,
                'stock_distribution': inventory_df['current_stock'].describe().to_dict()
            }

            # Calculate overstocked items (if max_stock_level exists)
            if 'max_stock_level' in inventory_df.columns:
                overstocked = inventory_df[inventory_df['current_stock'] > inventory_df['max_stock_level']]
                trends['overstocked_items'] = len(overstocked)

            return trends

        except Exception as e:
            logger.error(f"Error analyzing stock trends: {str(e)}")
            return {}

    def _generate_reorder_recommendations(self, inventory_df: pd.DataFrame, trans_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate reorder recommendations based on consumption patterns"""
        try:
            if inventory_df.empty:
                return []

            recommendations = []
            low_stock_items = inventory_df[inventory_df['current_stock'] <= inventory_df['reorder_level']]

            for _, item in low_stock_items.iterrows():
                # Calculate average consumption if transaction data is available
                avg_consumption = 0
                if not trans_df.empty:
                    item_transactions = trans_df[
                        (trans_df['inventory_id'] == item['id']) & 
                        (trans_df['transaction_type'] == 'out')
                    ]
                    if not item_transactions.empty:
                        # Calculate daily average consumption over last 30 days
                        recent_transactions = item_transactions[
                            item_transactions['created_at'] >= (datetime.now() - timedelta(days=30))
                        ]
                        if not recent_transactions.empty:
                            avg_consumption = recent_transactions['quantity'].sum() / 30

                recommendations.append({
                    'inventory_id': item['id'],
                    'item_name': item['item_name'],
                    'current_stock': item['current_stock'],
                    'reorder_level': item['reorder_level'],
                    'recommended_quantity': max(item['reorder_level'] * 2, int(avg_consumption * 30)),
                    'average_daily_consumption': avg_consumption,
                    'urgency': 'high' if item['current_stock'] == 0 else 'medium'
                })

            return recommendations

        except Exception as e:
            logger.error(f"Error generating reorder recommendations: {str(e)}")
            return []

# Create singleton instance
reporting_service = ReportingService()

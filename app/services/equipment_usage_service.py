from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.database_models import EquipmentUsageLog, Equipment

logger = logging.getLogger(__name__)

class EquipmentUsageService:
    def __init__(self):
        self.db = database_service

    async def log_equipment_usage(self, equipment_id: str, usage_data: dict, recorded_by: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """Log equipment usage"""
        try:
            # Validate equipment exists
            success, equipment_doc, error = self.db.get_document(COLLECTIONS['equipment'], equipment_id)
            if not success:
                return False, None, f"Equipment not found: {error}"
            
            equipment = Equipment(**equipment_doc)
            
            # Create usage log entry
            usage_log = EquipmentUsageLog(
                equipment_id=equipment_id,
                building_id=equipment.building_id,
                usage_type=usage_data['usage_type'],
                usage_value=usage_data['usage_value'],
                usage_unit=usage_data['usage_unit'],
                recorded_by=recorded_by or 'system',
                recording_method=usage_data.get('recording_method', 'manual'),
                notes=usage_data.get('notes'),
                recorded_at=usage_data.get('recorded_at', datetime.now()),
                created_at=datetime.now()
            )
            
            success, log_id, error = self.db.create_document(
                COLLECTIONS['equipment_usage_logs'], 
                usage_log.dict(exclude_none=True)
            )
            
            if success:
                logger.info(f"Logged usage for equipment {equipment_id}: {usage_data['usage_value']} {usage_data['usage_unit']}")
                
                # Update equipment's last usage timestamp
                await self.db.update_document(
                    COLLECTIONS['equipment'],
                    equipment_id,
                    {'last_usage_logged': datetime.now()}
                )
                
                return True, log_id, None
            else:
                logger.error(f"Failed to log equipment usage: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"Error logging equipment usage: {str(e)}")
            return False, None, str(e)

    async def get_equipment_usage_history(self, equipment_id: str, days_back: int = 30, usage_type: Optional[str] = None) -> Tuple[bool, List[dict], Optional[str]]:
        """Get equipment usage history"""
        try:
            start_date = datetime.now() - timedelta(days=days_back)
            
            filters = [
                ('equipment_id', '==', equipment_id),
                ('recorded_at', '>=', start_date)
            ]
            
            if usage_type:
                filters.append(('usage_type', '==', usage_type))
            
            success, usage_logs, error = self.db.query_documents(
                COLLECTIONS['equipment_usage_logs'],
                filters,
                order_by='recorded_at',
                order_direction='desc'
            )
            
            if success:
                return True, usage_logs, None
            else:
                logger.error(f"Failed to get equipment usage history: {error}")
                return False, [], error
                
        except Exception as e:
            logger.error(f"Error getting equipment usage history: {str(e)}")
            return False, [], str(e)

    async def get_total_equipment_usage(self, equipment_id: str, usage_type: str, since_date: Optional[datetime] = None) -> Tuple[bool, float, Optional[str]]:
        """Get total usage for equipment since a specific date"""
        try:
            filters = [
                ('equipment_id', '==', equipment_id),
                ('usage_type', '==', usage_type)
            ]
            
            if since_date:
                filters.append(('recorded_at', '>=', since_date))
            
            success, usage_logs, error = self.db.query_documents(
                COLLECTIONS['equipment_usage_logs'],
                filters
            )
            
            if success:
                total_usage = sum(log.get('usage_value', 0) for log in usage_logs)
                return True, total_usage, None
            else:
                logger.error(f"Failed to get total equipment usage: {error}")
                return False, 0.0, error
                
        except Exception as e:
            logger.error(f"Error getting total equipment usage: {str(e)}")
            return False, 0.0, str(e)

    async def get_usage_analytics(self, equipment_id: str, period_days: int = 30) -> Tuple[bool, Dict, Optional[str]]:
        """Get usage analytics for equipment"""
        try:
            start_date = datetime.now() - timedelta(days=period_days)
            
            success, usage_logs, error = self.db.query_documents(
                COLLECTIONS['equipment_usage_logs'],
                [
                    ('equipment_id', '==', equipment_id),
                    ('recorded_at', '>=', start_date)
                ],
                order_by='recorded_at'
            )
            
            if not success:
                return False, {}, error
            
            if not usage_logs:
                return True, {
                    'total_usage': 0,
                    'average_daily_usage': 0,
                    'peak_usage_day': None,
                    'usage_trend': 'no_data',
                    'period_days': period_days
                }, None
            
            # Calculate analytics
            analytics = self._calculate_usage_analytics(usage_logs, period_days)
            
            return True, analytics, None
            
        except Exception as e:
            logger.error(f"Error getting usage analytics: {str(e)}")
            return False, {}, str(e)

    def _calculate_usage_analytics(self, usage_logs: List[dict], period_days: int) -> Dict:
        """Calculate usage analytics from logs"""
        try:
            # Group usage by type and date
            usage_by_type = {}
            usage_by_date = {}
            
            for log in usage_logs:
                usage_type = log.get('usage_type', 'unknown')
                usage_value = log.get('usage_value', 0)
                recorded_date = log.get('recorded_at')
                
                if isinstance(recorded_date, str):
                    recorded_date = datetime.fromisoformat(recorded_date.replace('Z', '+00:00'))
                
                date_key = recorded_date.date() if recorded_date else datetime.now().date()
                
                # By type
                if usage_type not in usage_by_type:
                    usage_by_type[usage_type] = {'total': 0, 'count': 0}
                usage_by_type[usage_type]['total'] += usage_value
                usage_by_type[usage_type]['count'] += 1
                
                # By date
                if date_key not in usage_by_date:
                    usage_by_date[date_key] = 0
                usage_by_date[date_key] += usage_value
            
            # Calculate totals and averages
            total_usage = sum(type_data['total'] for type_data in usage_by_type.values())
            average_daily_usage = total_usage / max(period_days, 1)
            
            # Find peak usage day
            peak_usage_day = None
            peak_usage_value = 0
            if usage_by_date:
                peak_date = max(usage_by_date.keys(), key=lambda d: usage_by_date[d])
                peak_usage_value = usage_by_date[peak_date]
                peak_usage_day = {
                    'date': peak_date.isoformat(),
                    'usage': peak_usage_value
                }
            
            # Calculate trend (simple comparison of first half vs second half)
            usage_trend = 'stable'
            if len(usage_by_date) >= 4:
                dates = sorted(usage_by_date.keys())
                mid_point = len(dates) // 2
                first_half_avg = sum(usage_by_date[d] for d in dates[:mid_point]) / mid_point
                second_half_avg = sum(usage_by_date[d] for d in dates[mid_point:]) / (len(dates) - mid_point)
                
                if second_half_avg > first_half_avg * 1.1:
                    usage_trend = 'increasing'
                elif second_half_avg < first_half_avg * 0.9:
                    usage_trend = 'decreasing'
            
            return {
                'total_usage': total_usage,
                'average_daily_usage': round(average_daily_usage, 2),
                'peak_usage_day': peak_usage_day,
                'usage_trend': usage_trend,
                'usage_by_type': usage_by_type,
                'period_days': period_days,
                'total_logs': len(usage_logs)
            }
            
        except Exception as e:
            logger.error(f"Error calculating usage analytics: {str(e)}")
            return {}

    async def bulk_log_usage(self, usage_entries: List[dict], recorded_by: Optional[str] = None) -> Tuple[bool, int, List[str]]:
        """Bulk log multiple usage entries"""
        try:
            successful_logs = 0
            errors = []
            
            for entry in usage_entries:
                try:
                    success, log_id, error = await self.log_equipment_usage(
                        entry['equipment_id'],
                        entry,
                        recorded_by
                    )
                    
                    if success:
                        successful_logs += 1
                    else:
                        errors.append(f"Equipment {entry['equipment_id']}: {error}")
                        
                except Exception as e:
                    errors.append(f"Equipment {entry.get('equipment_id', 'unknown')}: {str(e)}")
            
            logger.info(f"Bulk logged {successful_logs}/{len(usage_entries)} usage entries")
            return True, successful_logs, errors
            
        except Exception as e:
            logger.error(f"Error in bulk usage logging: {str(e)}")
            return False, 0, [str(e)]

    async def get_equipment_usage_summary(self, building_id: str, period_days: int = 30) -> Tuple[bool, Dict, Optional[str]]:
        """Get usage summary for all equipment in a building"""
        try:
            # Get all equipment in building
            success, equipment_list, error = self.db.query_documents(
                COLLECTIONS['equipment'],
                [('building_id', '==', building_id)]
            )
            
            if not success:
                return False, {}, error
            
            start_date = datetime.now() - timedelta(days=period_days)
            
            # Get usage logs for all equipment
            success, usage_logs, error = self.db.query_documents(
                COLLECTIONS['equipment_usage_logs'],
                [
                    ('building_id', '==', building_id),
                    ('recorded_at', '>=', start_date)
                ]
            )
            
            if not success:
                return False, {}, error
            
            # Group by equipment
            equipment_usage = {}
            for equipment in equipment_list:
                equipment_id = equipment.get('id')
                equipment_usage[equipment_id] = {
                    'equipment_name': equipment.get('equipment_name'),
                    'equipment_type': equipment.get('equipment_type'),
                    'location': equipment.get('location'),
                    'total_usage': 0,
                    'usage_types': {},
                    'last_logged': None
                }
            
            # Aggregate usage data
            for log in usage_logs:
                equipment_id = log.get('equipment_id')
                if equipment_id in equipment_usage:
                    usage_value = log.get('usage_value', 0)
                    usage_type = log.get('usage_type', 'unknown')
                    recorded_at = log.get('recorded_at')
                    
                    equipment_usage[equipment_id]['total_usage'] += usage_value
                    
                    if usage_type not in equipment_usage[equipment_id]['usage_types']:
                        equipment_usage[equipment_id]['usage_types'][usage_type] = 0
                    equipment_usage[equipment_id]['usage_types'][usage_type] += usage_value
                    
                    # Update last logged time
                    if not equipment_usage[equipment_id]['last_logged'] or recorded_at > equipment_usage[equipment_id]['last_logged']:
                        equipment_usage[equipment_id]['last_logged'] = recorded_at
            
            summary = {
                'building_id': building_id,
                'period_days': period_days,
                'total_equipment': len(equipment_list),
                'equipment_with_usage': len([eq for eq in equipment_usage.values() if eq['total_usage'] > 0]),
                'equipment_usage': equipment_usage,
                'generated_at': datetime.now().isoformat()
            }
            
            return True, summary, None
            
        except Exception as e:
            logger.error(f"Error getting equipment usage summary: {str(e)}")
            return False, {}, str(e)

    async def check_usage_thresholds(self, building_id: Optional[str] = None) -> Tuple[bool, List[Dict], Optional[str]]:
        """Check equipment usage against maintenance thresholds"""
        try:
            # Get maintenance schedules with usage thresholds
            filters = [('schedule_type', '==', 'usage_based')]
            if building_id:
                filters.append(('building_id', '==', building_id))
            
            success, schedules, error = self.db.query_documents(
                COLLECTIONS['maintenance_schedules'],
                filters
            )
            
            if not success:
                return False, [], error
            
            threshold_alerts = []
            
            for schedule in schedules:
                try:
                    equipment_id = schedule.get('equipment_id')
                    usage_threshold = schedule.get('usage_threshold', 0)
                    usage_unit = schedule.get('usage_unit', 'hours')
                    
                    # Get current total usage
                    success, total_usage, error = await self.get_total_equipment_usage(
                        equipment_id, 
                        usage_unit
                    )
                    
                    if success and total_usage >= usage_threshold:
                        # Get equipment details
                        success, equipment_doc, error = self.db.get_document(COLLECTIONS['equipment'], equipment_id)
                        equipment_name = equipment_doc.get('equipment_name', 'Unknown') if success else 'Unknown'
                        
                        threshold_alerts.append({
                            'schedule_id': schedule.get('id'),
                            'equipment_id': equipment_id,
                            'equipment_name': equipment_name,
                            'current_usage': total_usage,
                            'threshold': usage_threshold,
                            'usage_unit': usage_unit,
                            'percentage_of_threshold': round((total_usage / usage_threshold) * 100, 1)
                        })
                        
                except Exception as e:
                    logger.error(f"Error checking threshold for schedule {schedule.get('id')}: {str(e)}")
                    continue
            
            return True, threshold_alerts, None
            
        except Exception as e:
            logger.error(f"Error checking usage thresholds: {str(e)}")
            return False, [], str(e)

# Create singleton instance
equipment_usage_service = EquipmentUsageService()

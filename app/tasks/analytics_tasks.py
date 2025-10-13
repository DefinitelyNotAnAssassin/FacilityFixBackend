from celery import current_task
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging
from ..core.celery_app import celery_app
from ..services.inventory_service import inventory_service
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def generate_daily_usage_analytics(self, building_id: str = None):
    """Generate daily usage analytics for inventory items"""
    try:
        logger.info(f"Starting daily analytics generation for building: {building_id or 'all'}")
        
        # Get all buildings if none specified
        buildings_to_process = []
        if building_id:
            buildings_to_process = [building_id]
        else:
            # Get all buildings from database
            success, buildings, error = database_service.query_documents(
                COLLECTIONS['buildings'], []
            )
            if success:
                buildings_to_process = [b.get('id') for b in buildings if b.get('id')]
        
        total_processed = 0
        for building in buildings_to_process:
            processed_count = _generate_building_analytics(building, "daily")
            total_processed += processed_count
            
            # Update task progress
            current_task.update_state(
                state='PROGRESS',
                meta={'current': total_processed, 'total': len(buildings_to_process)}
            )
        
        logger.info(f"Completed daily analytics generation. Processed {total_processed} items")
        return {
            'status': 'completed',
            'buildings_processed': len(buildings_to_process),
            'items_processed': total_processed,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating daily analytics: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def generate_weekly_usage_analytics(self, building_id: str = None):
    """Generate weekly usage analytics for inventory items"""
    try:
        logger.info(f"Starting weekly analytics generation for building: {building_id or 'all'}")
        
        buildings_to_process = []
        if building_id:
            buildings_to_process = [building_id]
        else:
            success, buildings, error = database_service.query_documents(
                COLLECTIONS['buildings'], []
            )
            if success:
                buildings_to_process = [b.get('id') for b in buildings if b.get('id')]
        
        total_processed = 0
        for building in buildings_to_process:
            processed_count = _generate_building_analytics(building, "weekly")
            total_processed += processed_count
        
        logger.info(f"Completed weekly analytics generation. Processed {total_processed} items")
        return {
            'status': 'completed',
            'buildings_processed': len(buildings_to_process),
            'items_processed': total_processed,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating weekly analytics: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def generate_monthly_usage_analytics(self, building_id: str = None):
    """Generate monthly usage analytics for inventory items"""
    try:
        logger.info(f"Starting monthly analytics generation for building: {building_id or 'all'}")
        
        buildings_to_process = []
        if building_id:
            buildings_to_process = [building_id]
        else:
            success, buildings, error = database_service.query_documents(
                COLLECTIONS['buildings'], []
            )
            if success:
                buildings_to_process = [b.get('id') for b in buildings if b.get('id')]
        
        total_processed = 0
        for building in buildings_to_process:
            processed_count = _generate_building_analytics(building, "monthly")
            total_processed += processed_count
        
        logger.info(f"Completed monthly analytics generation. Processed {total_processed} items")
        return {
            'status': 'completed',
            'buildings_processed': len(buildings_to_process),
            'items_processed': total_processed,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating monthly analytics: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task
def generate_inventory_usage_report(building_id: str, start_date: str, end_date: str):
    """Generate comprehensive inventory usage report for a specific period"""
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        logger.info(f"Generating usage report for building {building_id} from {start_date} to {end_date}")
        
        # Get all inventory items for the building
        success, items, error = inventory_service.get_inventory_by_building(building_id)
        if not success:
            raise Exception(f"Failed to get inventory items: {error}")
        
        report_data = {
            'building_id': building_id,
            'period_start': start_date,
            'period_end': end_date,
            'generated_at': datetime.now().isoformat(),
            'items': []
        }
        
        for item in items:
            item_id = item.get('id')
            if not item_id:
                continue
                
            # Get transactions for this item in the period
            success, transactions, error = inventory_service.get_inventory_transactions(
                inventory_id=item_id
            )
            
            if success:
                # Filter transactions by date range
                period_transactions = [
                    t for t in transactions
                    if start_dt <= t.get('created_at', datetime.min) <= end_dt
                ]
                
                # Calculate usage statistics
                total_consumed = sum(
                    t.get('quantity', 0) for t in period_transactions
                    if t.get('transaction_type') == 'out'
                )
                total_restocked = sum(
                    t.get('quantity', 0) for t in period_transactions
                    if t.get('transaction_type') == 'in'
                )
                
                item_report = {
                    'item_id': item_id,
                    'item_name': item.get('item_name'),
                    'department': item.get('department'),
                    'classification': item.get('classification'),
                    'total_consumed': total_consumed,
                    'total_restocked': total_restocked,
                    'transaction_count': len(period_transactions),
                    'current_stock': item.get('current_stock', 0),
                    'reorder_level': item.get('reorder_level', 0)
                }
                
                report_data['items'].append(item_report)
        
        # Save report to database
        success, report_id, error = database_service.create_document(
            COLLECTIONS['inventory_usage_reports'],
            report_data
        )
        
        if success:
            logger.info(f"Usage report generated successfully: {report_id}")
            return {
                'status': 'completed',
                'report_id': report_id,
                'items_analyzed': len(report_data['items'])
            }
        else:
            raise Exception(f"Failed to save report: {error}")
            
    except Exception as e:
        logger.error(f"Error generating usage report: {str(e)}")
        raise

def _generate_building_analytics(building_id: str, period_type: str) -> int:
    """Helper function to generate analytics for a specific building and period"""
    try:
        # Calculate period dates
        end_date = datetime.now()
        if period_type == "daily":
            start_date = end_date - timedelta(days=1)
        elif period_type == "weekly":
            start_date = end_date - timedelta(weeks=1)
        elif period_type == "monthly":
            start_date = end_date - timedelta(days=30)
        else:
            raise ValueError(f"Invalid period type: {period_type}")
        
        # Get all inventory items for the building
        success, items, error = inventory_service.get_inventory_by_building(building_id)
        if not success:
            logger.error(f"Failed to get inventory for building {building_id}: {error}")
            return 0
        
        processed_count = 0
        
        for item in items:
            item_id = item.get('id')
            if not item_id:
                continue
                
            try:
                # Get transactions for this period
                success, transactions, error = inventory_service.get_inventory_transactions(
                    inventory_id=item_id
                )
                
                if not success:
                    continue
                
                # Filter transactions by date range
                period_transactions = [
                    t for t in transactions
                    if start_date <= t.get('created_at', datetime.min) <= end_date
                ]
                
                if not period_transactions:
                    continue
                
                # Calculate analytics
                total_consumed = sum(
                    t.get('quantity', 0) for t in period_transactions
                    if t.get('transaction_type') == 'out'
                )
                total_restocked = sum(
                    t.get('quantity', 0) for t in period_transactions
                    if t.get('transaction_type') == 'in'
                )
                
                # Calculate average daily usage
                days_in_period = (end_date - start_date).days or 1
                average_daily_usage = total_consumed / days_in_period
                
                # Find peak usage
                daily_usage = {}
                for transaction in period_transactions:
                    if transaction.get('transaction_type') == 'out':
                        date_key = transaction.get('created_at').strftime('%Y-%m-%d')
                        daily_usage[date_key] = daily_usage.get(date_key, 0) + transaction.get('quantity', 0)
                
                peak_usage_date = None
                peak_usage_amount = 0
                if daily_usage:
                    peak_date_key = max(daily_usage, key=daily_usage.get)
                    peak_usage_date = datetime.strptime(peak_date_key, '%Y-%m-%d')
                    peak_usage_amount = daily_usage[peak_date_key]
                
                # Calculate costs
                cost_consumed = sum(
                    (t.get('quantity', 0) * t.get('cost_per_unit', 0))
                    for t in period_transactions
                    if t.get('transaction_type') == 'out' and t.get('cost_per_unit')
                )
                cost_restocked = sum(
                    (t.get('quantity', 0) * t.get('cost_per_unit', 0))
                    for t in period_transactions
                    if t.get('transaction_type') == 'in' and t.get('cost_per_unit')
                )
                
                # Create analytics record
                analytics_data = {
                    'inventory_id': item_id,
                    'building_id': building_id,
                    'period_start': start_date,
                    'period_end': end_date,
                    'period_type': period_type,
                    'total_consumed': total_consumed,
                    'total_restocked': total_restocked,
                    'average_daily_usage': average_daily_usage,
                    'peak_usage_date': peak_usage_date,
                    'peak_usage_amount': peak_usage_amount,
                    'cost_consumed': cost_consumed if cost_consumed > 0 else None,
                    'cost_restocked': cost_restocked if cost_restocked > 0 else None,
                    'stockout_days': 0,  # Would need to calculate from stock levels
                    'created_at': datetime.now()
                }
                
                # Save analytics to database
                success, analytics_id, error = database_service.create_document(
                    COLLECTIONS['inventory_usage_analytics'],
                    analytics_data
                )
                
                if success:
                    processed_count += 1
                else:
                    logger.error(f"Failed to save analytics for item {item_id}: {error}")
                    
            except Exception as e:
                logger.error(f"Error processing analytics for item {item_id}: {str(e)}")
                continue
        
        return processed_count
        
    except Exception as e:
        logger.error(f"Error generating analytics for building {building_id}: {str(e)}")
        return 0

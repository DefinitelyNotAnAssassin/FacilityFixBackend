#!/usr/bin/env python3
"""
Simple test script for Inventory Forecasting functionality.
Tests the forecasting calculations with mock data.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockDatabaseService:
    """Mock database service for testing"""

    def __init__(self):
        self.inventory_data = []
        self.transaction_data = []

    async def query_documents(self, collection: str, filters: List) -> tuple:
        """Mock query method"""
        if collection == 'inventory':
            return True, self.inventory_data, None
        elif collection == 'inventory_transactions':
            # Filter transactions based on provided filters
            filtered_transactions = []
            for transaction in self.transaction_data:
                match = True
                for filter_item in filters:
                    field, op, value = filter_item
                    if op == '==' and field in transaction:
                        if transaction[field] != value:
                            match = False
                            break
                    elif op == '>=' and field in transaction:
                        if transaction[field] < value:
                            match = False
                            break
                    elif op == '<=' and field in transaction:
                        if transaction[field] > value:
                            match = False
                            break
                if match:
                    filtered_transactions.append(transaction)
            return True, filtered_transactions, None
        return True, [], None

class MockInventoryService:
    """Mock inventory service for testing"""

    def __init__(self, db_service):
        self.db = db_service

    async def get_inventory_by_building(self, building_id: str, include_inactive: bool = False) -> tuple:
        """Mock get inventory by building"""
        return await self.db.query_documents('inventory', [('building_id', '==', building_id)])

    async def get_inventory_forecasting_data(self, building_id: str) -> tuple:
        """Test the forecasting data method"""
        try:
            # Get all active inventory items
            success, items, error = await self.get_inventory_by_building(building_id, include_inactive=False)
            if not success:
                return False, [], error

            forecasting_data = []

            for item in items:
                item_id = item['id']

                # Calculate monthly usage
                monthly_usage = await self._calculate_monthly_usage(item_id)

                # Calculate trend
                trend = await self._calculate_usage_trend(item_id)

                # Calculate days to minimum stock
                days_to_min = await self._calculate_days_to_minimum(item, monthly_usage)

                # Calculate reorder date
                reorder_date = await self._calculate_reorder_date(item, monthly_usage)

                # Format stock display
                current_stock = item.get('current_stock', 0)
                max_stock = item.get('max_stock_level', current_stock)
                stock_display = f"{current_stock}/{max_stock}"

                # Determine status
                status = "Active" if item.get('is_active', True) else "Inactive"

                forecasting_item = {
                    'id': item_id,
                    'name': item.get('item_name', ''),
                    'category': item.get('category', 'General'),
                    'status': status,
                    'stock': stock_display,
                    'usage': f"{monthly_usage:.1f}",
                    'trend': trend,
                    'daysToMin': days_to_min,
                    'reorderBy': reorder_date
                }

                forecasting_data.append(forecasting_item)

            return True, forecasting_data, None

        except Exception as e:
            error_msg = f"Error getting forecasting data: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg

    async def _calculate_monthly_usage(self, item_id: str) -> float:
        """Calculate average monthly usage for the last 3 months"""
        try:
            # Get transactions for the last 90 days
            ninety_days_ago = datetime.now() - timedelta(days=90)

            filters = [
                ('inventory_id', '==', item_id),
                ('transaction_type', '==', 'out'),
                ('created_at', '>=', ninety_days_ago)
            ]

            success, transactions, error = await self.db.query_documents('inventory_transactions', filters)

            if not success or not transactions:
                return 0.0

            # Calculate total consumed in 90 days
            total_consumed = sum(abs(t.get('quantity', 0)) for t in transactions)

            # Convert to monthly average
            monthly_usage = (total_consumed / 90) * 30

            return monthly_usage

        except Exception as e:
            logger.error(f"Error calculating monthly usage for {item_id}: {str(e)}")
            return 0.0

    async def _calculate_usage_trend(self, item_id: str) -> Dict[str, Any]:
        """Calculate usage trend (increasing, decreasing, stable)"""
        try:
            # Get current month usage
            current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            # Get previous month usage
            prev_month_end = current_month_start - timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Current month transactions
            current_filters = [
                ('inventory_id', '==', item_id),
                ('transaction_type', '==', 'out'),
                ('created_at', '>=', current_month_start),
                ('created_at', '<=', current_month_end)
            ]

            success_current, current_transactions, _ = await self.db.query_documents('inventory_transactions', current_filters)
            current_usage = sum(abs(t.get('quantity', 0)) for t in current_transactions) if success_current else 0

            # Previous month transactions
            prev_filters = [
                ('inventory_id', '==', item_id),
                ('transaction_type', '==', 'out'),
                ('created_at', '>=', prev_month_start),
                ('created_at', '<=', prev_month_end)
            ]

            success_prev, prev_transactions, _ = await self.db.query_documents('inventory_transactions', prev_filters)
            prev_usage = sum(abs(t.get('quantity', 0)) for t in prev_transactions) if success_prev else 0

            # Determine trend
            if prev_usage == 0:
                if current_usage > 0:
                    icon = "trending_up"
                    color = "green"
                else:
                    icon = "trending_flat"
                    color = "grey"
            else:
                change_percent = ((current_usage - prev_usage) / prev_usage) * 100
                if change_percent > 10:
                    icon = "trending_up"
                    color = "green"
                elif change_percent < -10:
                    icon = "trending_down"
                    color = "red"
                else:
                    icon = "trending_flat"
                    color = "grey"

            return {'icon': icon, 'color': color}

        except Exception as e:
            logger.error(f"Error calculating trend for {item_id}: {str(e)}")
            return {'icon': "trending_flat", 'color': "grey"}

    async def _calculate_days_to_minimum(self, item: Dict[str, Any], monthly_usage: float) -> str:
        """Calculate days until stock reaches reorder level"""
        try:
            current_stock = item.get('current_stock', 0)
            reorder_level = item.get('reorder_level', 0)

            if monthly_usage <= 0 or current_stock <= reorder_level:
                return "N/A"

            # Calculate daily usage
            daily_usage = monthly_usage / 30

            # Days to reach reorder level
            stock_above_reorder = current_stock - reorder_level
            days_to_min = stock_above_reorder / daily_usage

            if days_to_min < 0:
                return "0d"
            elif days_to_min < 30:
                return f"{int(days_to_min)}d"
            else:
                return f"{int(days_to_min)}d"

        except Exception as e:
            logger.error(f"Error calculating days to min for {item.get('id')}: {str(e)}")
            return "N/A"

    async def _calculate_reorder_date(self, item: Dict[str, Any], monthly_usage: float) -> str:
        """Calculate estimated reorder date"""
        try:
            current_stock = item.get('current_stock', 0)
            reorder_level = item.get('reorder_level', 0)

            if monthly_usage <= 0 or current_stock <= reorder_level:
                return "Immediate"

            # Calculate daily usage
            daily_usage = monthly_usage / 30

            # Days to reach reorder level
            stock_above_reorder = current_stock - reorder_level
            days_to_reorder = stock_above_reorder / daily_usage

            if days_to_reorder < 0:
                return "Immediate"

            reorder_date = datetime.now() + timedelta(days=days_to_reorder)
            return reorder_date.strftime("%b %d")

        except Exception as e:
            logger.error(f"Error calculating reorder date for {item.get('id')}: {str(e)}")
            return "Unknown"

async def test_forecasting():
    """Test the forecasting functionality with mock data"""
    logger.info("🚀 Testing Inventory Forecasting Functionality")
    logger.info("=" * 50)

    # Create mock database and service
    db_service = MockDatabaseService()
    inventory_service = MockInventoryService(db_service)

    # Setup test data
    logger.info("🔧 Setting up mock test data...")

    test_building_id = "test_building_001"

    # Add test inventory items
    test_items = [
        {
            'id': 'item_001',
            'building_id': test_building_id,
            'item_name': 'Light Bulb',
            'category': 'Electrical',
            'current_stock': 8,
            'reorder_level': 5,
            'max_stock_level': 10,
            'is_active': True
        },
        {
            'id': 'item_002',
            'building_id': test_building_id,
            'item_name': 'Pipe Fitting',
            'category': 'Plumbing',
            'current_stock': 9,
            'reorder_level': 3,
            'max_stock_level': 15,
            'is_active': True
        },
        {
            'id': 'item_003',
            'building_id': test_building_id,
            'item_name': 'Screwdriver Set',
            'category': 'General',
            'current_stock': 5,
            'reorder_level': 2,
            'max_stock_level': 10,
            'is_active': True
        }
    ]

    db_service.inventory_data = test_items

    # Add historical transactions (last 90 days)
    base_date = datetime.now() - timedelta(days=90)
    transactions = []

    # Light Bulb: High usage (2-3 per month)
    for i in range(12):  # 12 weeks
        transactions.append({
            'inventory_id': 'item_001',
            'transaction_type': 'out',
            'quantity': 2 + (i % 2),  # Alternate between 2 and 3
            'created_at': base_date + timedelta(days=i*7)
        })

    # Pipe Fitting: Medium usage (1-2 per month)
    for i in range(8):  # 8 weeks
        transactions.append({
            'inventory_id': 'item_002',
            'transaction_type': 'out',
            'quantity': 1 + (i % 2),  # Alternate between 1 and 2
            'created_at': base_date + timedelta(days=i*7)
        })

    # Screwdriver: Low usage (0-1 per month)
    for i in range(4):  # 4 weeks
        transactions.append({
            'inventory_id': 'item_003',
            'transaction_type': 'out',
            'quantity': i % 2,  # 0 or 1
            'created_at': base_date + timedelta(days=i*7)
        })

    db_service.transaction_data = transactions

    logger.info(f"✅ Set up {len(test_items)} test items and {len(transactions)} transactions")

    # Test forecasting
    logger.info("🔍 Testing forecasting calculations...")

    success, data, error = await inventory_service.get_inventory_forecasting_data(test_building_id)

    if success:
        logger.info(f"✅ Forecasting returned {len(data)} items")

        # Validate and display results
        for item in data:
            logger.info(f"\n📊 Item: {item['name']}")
            logger.info(f"   Stock: {item['stock']}")
            logger.info(f"   Usage/Month: {item['usage']}")
            logger.info(f"   Trend: {item['trend']['icon']} ({item['trend']['color']})")
            logger.info(f"   Days to Min: {item['daysToMin']}")
            logger.info(f"   Reorder By: {item['reorderBy']}")

        # Validate structure
        expected_fields = ['id', 'name', 'category', 'status', 'stock', 'usage', 'trend', 'daysToMin', 'reorderBy']
        all_valid = True

        for item in data:
            missing_fields = [field for field in expected_fields if field not in item]
            if missing_fields:
                logger.error(f"❌ Item {item.get('name')} missing fields: {missing_fields}")
                all_valid = False

        if all_valid:
            logger.info("✅ All items have correct structure")
            logger.info("🎉 Forecasting test completed successfully!")
            return True
        else:
            logger.error("❌ Some items have invalid structure")
            return False
    else:
        logger.error(f"❌ Forecasting failed: {error}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_forecasting())
    sys.exit(0 if success else 1)
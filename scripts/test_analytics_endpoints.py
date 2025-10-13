"""
Test script for analytics endpoints
Run this to verify all analytics features are working
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import logging
from app.services.analytics_service import AnalyticsService
from app.services.advanced_analytics_service import AdvancedAnalyticsService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_analytics():
    """Test basic analytics service"""
    logger.info("Testing Basic Analytics Service...")
    service = AnalyticsService()
    
    try:
        # Test dashboard stats
        logger.info("1. Testing dashboard stats...")
        stats = await service.get_dashboard_stats()
        logger.info(f"✓ Dashboard stats: {stats.get('total_requests', 0)} total requests")
        
        # Test work order trends
        logger.info("2. Testing work order trends...")
        trends = await service.get_work_order_trends(days=7)
        logger.info(f"✓ Work order trends: {trends.get('period_days')} days analyzed")
        
        # Test category breakdown
        logger.info("3. Testing category breakdown...")
        categories = await service.get_category_breakdown()
        logger.info(f"✓ Category breakdown: {categories.get('total_analyzed', 0)} concerns analyzed")
        
        return True
    except Exception as e:
        logger.error(f"✗ Basic analytics test failed: {e}")
        return False

async def test_advanced_analytics():
    """Test advanced analytics service"""
    logger.info("\nTesting Advanced Analytics Service...")
    service = AdvancedAnalyticsService()
    
    try:
        # Test heat map
        logger.info("1. Testing heat map generation...")
        heat_map = await service.generate_heat_map_data(days=30)
        logger.info(f"✓ Heat map: {len(heat_map.get('heat_map_matrix', []))} locations analyzed")
        
        # Test staff performance
        logger.info("2. Testing staff performance insights...")
        staff_perf = await service.get_staff_performance_insights(days=30)
        logger.info(f"✓ Staff performance: {staff_perf.get('total_staff_analyzed', 0)} staff analyzed")
        
        # Test equipment insights
        logger.info("3. Testing equipment insights...")
        equipment = await service.get_equipment_insights(days=90)
        logger.info(f"✓ Equipment insights: {len(equipment.get('equipment_analysis', []))} equipment types analyzed")
        
        # Test inventory analysis
        logger.info("4. Testing inventory analysis...")
        inventory = await service.get_inventory_linkage_analysis(days=60)
        logger.info(f"✓ Inventory analysis: ${inventory.get('total_projected_cost', 0):.2f} projected cost")
        
        # Test comprehensive report
        logger.info("5. Testing comprehensive report...")
        report = await service.generate_comprehensive_report(days=30)
        logger.info(f"✓ Comprehensive report: {len(report.get('recommendations', []))} recommendations")
        
        return True
    except Exception as e:
        logger.error(f"✗ Advanced analytics test failed: {e}")
        return False

async def test_export_data_generation():
    """Test data export generation"""
    logger.info("\nTesting Export Data Generation...")
    
    try:
        from app.routers.analytics import (
            _create_comprehensive_csv,
            _create_heat_map_csv,
            _create_staff_performance_csv,
            _create_equipment_csv
        )
        
        service = AdvancedAnalyticsService()
        
        # Generate sample data
        logger.info("1. Generating comprehensive report...")
        report = await service.generate_comprehensive_report(days=30)
        csv_data = _create_comprehensive_csv(report)
        logger.info(f"✓ Comprehensive CSV: {len(csv_data)} bytes")
        
        logger.info("2. Generating heat map data...")
        heat_map = await service.generate_heat_map_data(days=30)
        csv_data = _create_heat_map_csv(heat_map)
        logger.info(f"✓ Heat map CSV: {len(csv_data)} bytes")
        
        logger.info("3. Generating staff performance data...")
        staff = await service.get_staff_performance_insights(days=30)
        csv_data = _create_staff_performance_csv(staff)
        logger.info(f"✓ Staff performance CSV: {len(csv_data)} bytes")
        
        logger.info("4. Generating equipment data...")
        equipment = await service.get_equipment_insights(days=90)
        csv_data = _create_equipment_csv(equipment)
        logger.info(f"✓ Equipment CSV: {len(csv_data)} bytes")
        
        return True
    except Exception as e:
        logger.error(f"✗ Export generation test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("="*60)
    logger.info("ANALYTICS ENDPOINTS TEST SUITE")
    logger.info("="*60)
    
    results = []
    
    # Run tests
    results.append(await test_basic_analytics())
    results.append(await test_advanced_analytics())
    results.append(await test_export_data_generation())
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    passed = sum(results)
    total = len(results)
    logger.info(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        logger.info("✓ All tests passed!")
    else:
        logger.warning(f"✗ {total - passed} test(s) failed")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

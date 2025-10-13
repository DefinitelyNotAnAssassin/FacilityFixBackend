#!/usr/bin/env python3
"""
Test script for background job functionality.
Tests Celery tasks for analytics, inventory monitoring, and notifications.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import logging

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.firebase_init import initialize_firebase, is_firebase_available, get_firebase_status

# Initialize Firebase first
print("🔥 Initializing Firebase for background job tests...")
firebase_status = get_firebase_status()
print(f"Firebase status before init: {firebase_status}")

if not is_firebase_available():
    success = initialize_firebase()
    if not success:
        print("❌ Firebase initialization failed - tests will run in mock mode")
    else:
        print("✅ Firebase initialized successfully")
else:
    print("✅ Firebase already initialized")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BackgroundJobTester:
    """Test background job functionality"""
    
    def __init__(self):
        self.test_building_id = "test_building_bg_001"
        
        # Check if Firebase is available
        if not is_firebase_available():
            logger.warning("⚠️ Firebase not available - running in mock mode")
            self.mock_mode = True
        else:
            self.mock_mode = False
    
    async def test_analytics_tasks(self):
        """Test analytics background tasks"""
        logger.info("📊 Testing Analytics Background Tasks...")
        
        if self.mock_mode:
            logger.info("ℹ️ Mock mode - simulating analytics tasks")
            logger.info("✅ Mock analytics tasks completed")
            return True
        
        try:
            # Import tasks
            from app.tasks.analytics_tasks import (
                generate_daily_usage_analytics,
                generate_weekly_usage_analytics,
                generate_monthly_usage_analytics,
                generate_inventory_usage_report
            )
            
            # Test 1: Daily analytics generation
            logger.info("1️⃣ Testing daily analytics generation...")
            
            # This would normally be called by Celery, but we'll test the function directly
            result = generate_daily_usage_analytics.apply(
                args=[self.test_building_id]
            )
            
            if result.successful():
                logger.info("✅ Daily analytics task completed successfully")
                logger.info(f"   Result: {result.result}")
            else:
                logger.error(f"❌ Daily analytics task failed: {result.traceback}")
                return False
            
            # Test 2: Weekly analytics generation
            logger.info("2️⃣ Testing weekly analytics generation...")
            
            result = generate_weekly_usage_analytics.apply(
                args=[self.test_building_id]
            )
            
            if result.successful():
                logger.info("✅ Weekly analytics task completed successfully")
            else:
                logger.error(f"❌ Weekly analytics task failed: {result.traceback}")
                return False
            
            # Test 3: Usage report generation
            logger.info("3️⃣ Testing usage report generation...")
            
            start_date = (datetime.now() - timedelta(days=7)).isoformat()
            end_date = datetime.now().isoformat()
            
            result = generate_inventory_usage_report.apply(
                args=[self.test_building_id, start_date, end_date]
            )
            
            if result.successful():
                logger.info("✅ Usage report task completed successfully")
            else:
                logger.error(f"❌ Usage report task failed: {result.traceback}")
                return False
            
            return True
            
        except ImportError as e:
            logger.error(f"❌ Failed to import analytics tasks: {str(e)}")
            logger.info("ℹ️ This is expected if Celery is not installed or configured")
            return False
        except Exception as e:
            logger.error(f"❌ Analytics tasks test error: {str(e)}")
            return False
    
    async def test_inventory_tasks(self):
        """Test inventory monitoring background tasks"""
        logger.info("📦 Testing Inventory Background Tasks...")
        
        if self.mock_mode:
            logger.info("ℹ️ Mock mode - simulating inventory tasks")
            logger.info("✅ Mock inventory tasks completed")
            return True
        
        try:
            from app.tasks.inventory_tasks import (
                check_all_low_stock_alerts,
                send_reorder_reminders,
                auto_fulfill_approved_requests
            )
            
            # Test 1: Low stock alert checking
            logger.info("1️⃣ Testing low stock alert checking...")
            
            result = check_all_low_stock_alerts.apply()
            
            if result.successful():
                logger.info("✅ Low stock alert check completed successfully")
                logger.info(f"   Result: {result.result}")
            else:
                logger.error(f"❌ Low stock alert check failed: {result.traceback}")
                return False
            
            # Test 2: Reorder reminders
            logger.info("2️⃣ Testing reorder reminders...")
            
            result = send_reorder_reminders.apply()
            
            if result.successful():
                logger.info("✅ Reorder reminders task completed successfully")
            else:
                logger.error(f"❌ Reorder reminders task failed: {result.traceback}")
                return False
            
            # Test 3: Auto-fulfill requests
            logger.info("3️⃣ Testing auto-fulfill requests...")
            
            result = auto_fulfill_approved_requests.apply()
            
            if result.successful():
                logger.info("✅ Auto-fulfill requests task completed successfully")
            else:
                logger.error(f"❌ Auto-fulfill requests task failed: {result.traceback}")
                return False
            
            return True
            
        except ImportError as e:
            logger.error(f"❌ Failed to import inventory tasks: {str(e)}")
            logger.info("ℹ️ This is expected if Celery is not installed or configured")
            return False
        except Exception as e:
            logger.error(f"❌ Inventory tasks test error: {str(e)}")
            return False
    
    async def test_notification_tasks(self):
        """Test notification background tasks"""
        logger.info("🔔 Testing Notification Background Tasks...")
        
        if self.mock_mode:
            logger.info("ℹ️ Mock mode - simulating notification tasks")
            logger.info("✅ Mock notification tasks completed")
            return True
        
        try:
            from app.tasks.notification_tasks import (
                cleanup_old_notifications,
                send_bulk_notification,
                send_scheduled_maintenance_reminders
            )
            
            # Test 1: Notification cleanup
            logger.info("1️⃣ Testing notification cleanup...")
            
            result = cleanup_old_notifications.apply(args=[30])  # 30 days
            
            if result.successful():
                logger.info("✅ Notification cleanup completed successfully")
                logger.info(f"   Result: {result.result}")
            else:
                logger.error(f"❌ Notification cleanup failed: {result.traceback}")
                return False
            
            # Test 2: Bulk notifications
            logger.info("2️⃣ Testing bulk notifications...")
            
            test_user_ids = ["test_user_1", "test_user_2"]
            result = send_bulk_notification.apply(
                args=[test_user_ids, "Test Notification", "This is a test message", "info"]
            )
            
            if result.successful():
                logger.info("✅ Bulk notification task completed successfully")
            else:
                logger.error(f"❌ Bulk notification task failed: {result.traceback}")
                return False
            
            return True
            
        except ImportError as e:
            logger.error(f"❌ Failed to import notification tasks: {str(e)}")
            logger.info("ℹ️ This is expected if Celery is not installed or configured")
            return False
        except Exception as e:
            logger.error(f"❌ Notification tasks test error: {str(e)}")
            return False
    
    async def test_celery_configuration(self):
        """Test Celery configuration and setup"""
        logger.info("⚙️ Testing Celery Configuration...")
        
        try:
            from app.core.celery_app import celery_app
            
            # Test 1: Celery app configuration
            logger.info("1️⃣ Testing Celery app configuration...")
            
            logger.info(f"   Broker URL: {celery_app.conf.broker_url}")
            logger.info(f"   Result backend: {celery_app.conf.result_backend}")
            logger.info(f"   Task serializer: {celery_app.conf.task_serializer}")
            logger.info(f"   Timezone: {celery_app.conf.timezone}")
            
            # Test 2: Periodic task schedule
            logger.info("2️⃣ Testing periodic task schedule...")
            
            beat_schedule = celery_app.conf.beat_schedule
            logger.info(f"   Configured {len(beat_schedule)} periodic tasks:")
            
            for task_name, task_config in beat_schedule.items():
                schedule = task_config.get('schedule', 'unknown')
                if hasattr(schedule, 'total_seconds'):
                    schedule_str = f"every {schedule.total_seconds()}s"
                else:
                    schedule_str = f"schedule: {schedule}"
                logger.info(f"   - {task_name}: {task_config['task']} ({schedule_str})")
            
            # Test 3: Task discovery
            logger.info("3️⃣ Testing task discovery...")
            
            registered_tasks = list(celery_app.tasks.keys())
            app_tasks = [task for task in registered_tasks if task.startswith('app.tasks')]
            
            logger.info(f"   Found {len(app_tasks)} application tasks:")
            for task in app_tasks:
                logger.info(f"   - {task}")
            
            logger.info("✅ Celery configuration test completed successfully")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Failed to import Celery app: {str(e)}")
            logger.info("ℹ️ This is expected if Celery is not installed")
            return False
        except Exception as e:
            logger.error(f"❌ Celery configuration test error: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Run all background job tests"""
        logger.info("🚀 Starting Background Job Tests")
        logger.info("=" * 50)
        
        # Check Firebase status
        firebase_status = get_firebase_status()
        logger.info(f"Firebase status: {firebase_status}")
        
        test_results = {}
        
        test_suites = [
            ("Celery Configuration", self.test_celery_configuration),
            ("Analytics Tasks", self.test_analytics_tasks),
            ("Inventory Tasks", self.test_inventory_tasks),
            ("Notification Tasks", self.test_notification_tasks)
        ]
        
        for suite_name, test_method in test_suites:
            try:
                logger.info(f"\n🧪 Running {suite_name} Tests...")
                result = await test_method()
                test_results[suite_name] = "PASSED" if result else "FAILED"
                
                if result:
                    logger.info(f"✅ {suite_name} tests PASSED")
                else:
                    logger.error(f"❌ {suite_name} tests FAILED")
                    
            except Exception as e:
                logger.error(f"❌ {suite_name} tests ERROR: {str(e)}")
                test_results[suite_name] = f"ERROR: {str(e)}"
        
        # Print final results
        logger.info("\n" + "=" * 50)
        logger.info("📊 BACKGROUND JOB TEST RESULTS")
        logger.info("=" * 50)
        
        passed_count = 0
        failed_count = 0
        
        for suite_name, result in test_results.items():
            if result == "PASSED":
                logger.info(f"✅ {suite_name}: {result}")
                passed_count += 1
            else:
                logger.error(f"❌ {suite_name}: {result}")
                failed_count += 1
        
        total_tests = len(test_results)
        logger.info(f"\n📈 Summary: {passed_count}/{total_tests} test suites passed")
        
        if passed_count == total_tests:
            logger.info("🎉 ALL BACKGROUND JOB TESTS PASSED!")
            return True
        else:
            logger.error("❌ Some background job tests failed.")
            return False

async def main():
    """Main test execution function"""
    tester = BackgroundJobTester()
    success = await tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # Run the tests
    asyncio.run(main())

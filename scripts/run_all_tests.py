#!/usr/bin/env python3
"""
Master test runner for all FacilityFix inventory system tests.
Runs both API endpoint tests and background job tests.
"""

import asyncio
import subprocess
import sys
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MasterTestRunner:
    """Master test runner for the entire inventory system"""
    
    def __init__(self):
        self.script_dir = os.path.dirname(__file__)
        self.test_results = {}
    
    async def run_test_script(self, script_name: str, description: str) -> bool:
        """Run a test script and capture results"""
        logger.info(f"🚀 Running {description}...")
        
        script_path = os.path.join(self.script_dir, script_name)
        
        try:
            # Run the test script
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            # Log output
            if result.stdout:
                logger.info(f"📄 {description} Output:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"   {line}")
            
            if result.stderr:
                logger.error(f"📄 {description} Errors:")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        logger.error(f"   {line}")
            
            # Check result
            success = result.returncode == 0
            
            if success:
                logger.info(f"✅ {description} completed successfully")
            else:
                logger.error(f"❌ {description} failed with exit code {result.returncode}")
            
            return success
            
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {description} timed out after 5 minutes")
            return False
        except FileNotFoundError:
            logger.error(f"📁 Test script not found: {script_path}")
            return False
        except Exception as e:
            logger.error(f"💥 Error running {description}: {str(e)}")
            return False
    
    async def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        logger.info("🔍 Checking prerequisites...")
        
        prerequisites_met = True
        
        # Check Python version
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            logger.error("❌ Python 3.8+ is required")
            prerequisites_met = False
        else:
            logger.info(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # Check required modules
        required_modules = [
            'fastapi',
            'firebase_admin',
            'asyncio',
            'datetime'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
                logger.info(f"✅ Module available: {module}")
            except ImportError:
                logger.error(f"❌ Required module missing: {module}")
                prerequisites_met = False
        
        # Check optional modules (for background jobs)
        optional_modules = ['celery', 'redis']
        for module in optional_modules:
            try:
                __import__(module)
                logger.info(f"✅ Optional module available: {module}")
            except ImportError:
                logger.warning(f"⚠️ Optional module missing: {module} (background job tests may fail)")
        
        return prerequisites_met
    
    async def run_all_tests(self):
        """Run all test suites"""
        start_time = datetime.now()
        
        logger.info("🎯 FacilityFix Inventory System - Master Test Runner")
        logger.info("=" * 70)
        logger.info(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check prerequisites
        if not await self.check_prerequisites():
            logger.error("❌ Prerequisites not met. Please install required dependencies.")
            return False
        
        # Define test suites
        test_suites = [
            ("test_inventory_endpoints.py", "Inventory API Endpoints"),
            ("test_background_jobs.py", "Background Job System")
        ]
        
        # Run each test suite
        for script_name, description in test_suites:
            try:
                success = await self.run_test_script(script_name, description)
                self.test_results[description] = "PASSED" if success else "FAILED"
            except Exception as e:
                logger.error(f"💥 Unexpected error in {description}: {str(e)}")
                self.test_results[description] = f"ERROR: {str(e)}"
        
        # Calculate results
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Print final summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 MASTER TEST RESULTS SUMMARY")
        logger.info("=" * 70)
        
        passed_count = 0
        failed_count = 0
        error_count = 0
        
        for suite_name, result in self.test_results.items():
            if result == "PASSED":
                logger.info(f"✅ {suite_name}: {result}")
                passed_count += 1
            elif result == "FAILED":
                logger.error(f"❌ {suite_name}: {result}")
                failed_count += 1
            else:
                logger.error(f"💥 {suite_name}: {result}")
                error_count += 1
        
        total_suites = len(self.test_results)
        
        logger.info(f"\n📈 Test Summary:")
        logger.info(f"   Total test suites: {total_suites}")
        logger.info(f"   Passed: {passed_count}")
        logger.info(f"   Failed: {failed_count}")
        logger.info(f"   Errors: {error_count}")
        logger.info(f"   Duration: {duration.total_seconds():.2f} seconds")
        
        # Final verdict
        if passed_count == total_suites:
            logger.info("\n🎉 ALL TESTS PASSED! The inventory system is working correctly.")
            logger.info("✨ Your FacilityFix inventory management system is ready for production!")
            return True
        else:
            logger.error(f"\n❌ {failed_count + error_count} test suite(s) failed.")
            logger.error("🔧 Please review the test output above and fix any issues.")
            
            # Provide guidance
            if failed_count > 0:
                logger.info("\n💡 Troubleshooting tips:")
                logger.info("   - Check database connectivity")
                logger.info("   - Verify Firebase configuration")
                logger.info("   - Ensure all required environment variables are set")
            
            if error_count > 0:
                logger.info("   - Install missing dependencies")
                logger.info("   - Check Python version compatibility")
                logger.info("   - Verify file permissions")
            
            return False

async def main():
    """Main execution function"""
    runner = MasterTestRunner()
    success = await runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # Run all tests
    asyncio.run(main())

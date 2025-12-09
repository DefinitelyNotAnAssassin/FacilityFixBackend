#!/usr/bin/env python3
"""
API Test script for Inventory Forecasting endpoint.
Tests the actual FastAPI endpoint with authentication.
"""

import asyncio
import sys
import os
import json
from typing import Dict, Any
import logging

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InventoryForecastingAPITester:
    """Test the forecasting API endpoint"""

    def __init__(self):
        self.base_url = "http://localhost:8000"  # Adjust if your server runs on different port
        self.test_building_id = "test_building_001"
        self.auth_token = None  # You'll need to set this

    async def test_forecasting_api(self):
        """Test the forecasting API endpoint"""
        logger.info("🚀 Testing Inventory Forecasting API Endpoint")
        logger.info("=" * 50)

        try:
            import httpx

            # Test endpoint URL
            url = f"{self.base_url}/inventory/forecasting/{self.test_building_id}"

            headers = {
                'Content-Type': 'application/json',
            }

            # Add auth token if available
            if self.auth_token:
                headers['Authorization'] = f'Bearer {self.auth_token}'

            logger.info(f"📡 Making request to: {url}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)

                logger.info(f"📊 Response status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ API returned {len(data)} forecasting items")

                    # Validate response structure
                    if self._validate_response_structure(data):
                        logger.info("✅ Response structure is valid")

                        # Display sample results
                        if data:
                            self._display_sample_results(data[:3])  # Show first 3 items

                        logger.info("🎉 API test completed successfully!")
                        return True
                    else:
                        logger.error("❌ Response structure validation failed")
                        return False

                elif response.status_code == 401:
                    logger.warning("⚠️  Authentication required. Please set auth_token in the script")
                    logger.info("💡 To test with authentication, set self.auth_token in the script")
                    return False

                elif response.status_code == 403:
                    logger.error("❌ Forbidden - insufficient permissions")
                    return False

                else:
                    logger.error(f"❌ API request failed with status {response.status_code}")
                    try:
                        error_data = response.json()
                        logger.error(f"Error details: {error_data}")
                    except:
                        logger.error(f"Response text: {response.text}")
                    return False

        except ImportError:
            logger.error("❌ httpx not installed. Install with: pip install httpx")
            return False
        except Exception as e:
            logger.error(f"❌ API test failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _validate_response_structure(self, data: list) -> bool:
        """Validate the response structure matches expected format"""
        if not isinstance(data, list):
            logger.error("❌ Response is not a list")
            return False

        expected_fields = ['id', 'name', 'category', 'status', 'stock', 'usage', 'trend', 'daysToMin', 'reorderBy']

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                logger.error(f"❌ Item {i} is not a dictionary")
                return False

            missing_fields = [field for field in expected_fields if field not in item]
            if missing_fields:
                logger.error(f"❌ Item {i} ({item.get('name', 'Unknown')}) missing fields: {missing_fields}")
                return False

            # Validate trend structure
            trend = item.get('trend')
            if not isinstance(trend, dict) or 'icon' not in trend or 'color' not in trend:
                logger.error(f"❌ Item {i} has invalid trend structure: {trend}")
                return False

        return True

    def _display_sample_results(self, data: list):
        """Display sample forecasting results"""
        logger.info("📊 Sample API Results:")

        for item in data:
            logger.info(f"\n🔹 {item['name']} ({item['category']})")
            logger.info(f"   Status: {item['status']}")
            logger.info(f"   Stock: {item['stock']}")
            logger.info(f"   Monthly Usage: {item['usage']}")
            logger.info(f"   Trend: {item['trend']['icon']} ({item['trend']['color']})")
            logger.info(f"   Days to Min Stock: {item['daysToMin']}")
            logger.info(f"   Reorder By: {item['reorderBy']}")

async def main():
    """Main API test execution"""
    tester = InventoryForecastingAPITester()

    # Note: For testing with authentication, you would need to:
    # 1. Start your FastAPI server
    # 2. Get a valid JWT token
    # 3. Set tester.auth_token = "your_jwt_token_here"

    logger.info("ℹ️  Make sure your FastAPI server is running on http://localhost:8000")
    logger.info("ℹ️  For authenticated endpoints, set the auth_token in the script")

    success = await tester.test_forecasting_api()

    if success:
        print("\n🎉 API test completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 API test failed!")
        print("\n💡 Troubleshooting tips:")
        print("   1. Make sure your FastAPI server is running")
        print("   2. Check the server logs for errors")
        print("   3. Verify the building_id exists in your database")
        print("   4. Ensure you have proper authentication if required")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
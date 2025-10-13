"""
User Management API Endpoints Testing Script
Tests all user management API endpoints using HTTP requests
"""

import asyncio
import aiohttp
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_ADMIN_TOKEN = None  # Will be set after login

class APITester:
    """API endpoint testing class"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = None
        self.admin_token = None
        self.test_results = []
        self.test_user_id = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, success: bool, message: str = "", data: Any = None):
        """Log test results"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "FAIL"
        print(f"{status} {test_name}: {message}")
    
    async def make_request(self, method: str, endpoint: str, data: Dict = None, 
                          headers: Dict = None, params: Dict = None) -> tuple:
        """Make HTTP request"""
        url = f"{self.base_url}{endpoint}"
        
        # Add authorization header if admin token is available
        if self.admin_token and headers is None:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
        elif self.admin_token and headers:
            headers["Authorization"] = f"Bearer {self.admin_token}"
        
        try:
            async with self.session.request(
                method, url, json=data, headers=headers, params=params
            ) as response:
                response_data = await response.json()
                return response.status, response_data
        except Exception as e:
            return 500, {"error": str(e)}
    
    async def test_health_check(self):
        """Test API health check"""
        try:
            status, data = await self.make_request("GET", "/health")
            
            if status == 200 and data.get("status") == "healthy":
                self.log_test("Health Check", True, "API is healthy")
            else:
                self.log_test("Health Check", False, f"Health check failed: {data}")
        except Exception as e:
            self.log_test("Health Check", False, f"Health check error: {str(e)}")
    
    async def test_user_registration(self):
        """Test user registration endpoint"""
        try:
            # Note: This requires admin authentication in real scenario
            # For testing, we'll simulate the request structure
            
            user_data = {
                "email": f"apitest_{datetime.now().strftime('%Y%m%d_%H%M%S')}@facilityfix.test",
                "password": "TestPassword123!",
                "first_name": "API",
                "last_name": "Test",
                "phone_number": "+1234567890",
                "role": "staff",
                "building_id": "test_building_001",
                "department": "API Testing"
            }
            
            # This would normally require admin token
            status, data = await self.make_request("POST", "/auth/register", user_data)
            
            if status == 200 or status == 201:
                self.test_user_id = data.get("uid")
                self.log_test("User Registration", True, f"User registered: {self.test_user_id}")
            else:
                self.log_test("User Registration", False, f"Registration failed: {data}")
                
        except Exception as e:
            self.log_test("User Registration", False, f"Registration error: {str(e)}")
    
    async def test_get_users(self):
        """Test get users endpoint"""
        try:
            status, data = await self.make_request("GET", "/users/")
            
            if status == 200:
                users = data if isinstance(data, list) else []
                self.log_test("Get Users", True, f"Retrieved {len(users)} users")
            else:
                self.log_test("Get Users", False, f"Get users failed: {data}")
                
        except Exception as e:
            self.log_test("Get Users", False, f"Get users error: {str(e)}")
    
    async def test_get_user_by_id(self):
        """Test get specific user endpoint"""
        if not self.test_user_id:
            self.log_test("Get User By ID", False, "No test user ID available")
            return
        
        try:
            status, data = await self.make_request("GET", f"/users/{self.test_user_id}")
            
            if status == 200:
                self.log_test("Get User By ID", True, f"Retrieved user: {self.test_user_id}")
            else:
                self.log_test("Get User By ID", False, f"Get user failed: {data}")
                
        except Exception as e:
            self.log_test("Get User By ID", False, f"Get user error: {str(e)}")
    
    async def test_update_user(self):
        """Test update user endpoint"""
        if not self.test_user_id:
            self.log_test("Update User", False, "No test user ID available")
            return
        
        try:
            update_data = {
                "phone_number": "+9876543210",
                "department": "Updated API Testing"
            }
            
            status, data = await self.make_request("PUT", f"/users/{self.test_user_id}", update_data)
            
            if status == 200:
                self.log_test("Update User", True, "User updated successfully")
            else:
                self.log_test("Update User", False, f"Update failed: {data}")
                
        except Exception as e:
            self.log_test("Update User", False, f"Update error: {str(e)}")
    
    async def test_user_status_update(self):
        """Test user status update endpoint"""
        if not self.test_user_id:
            self.log_test("User Status Update", False, "No test user ID available")
            return
        
        try:
            status_data = {"status": "suspended"}
            
            status, data = await self.make_request("PATCH", f"/users/{self.test_user_id}/status", status_data)
            
            if status == 200:
                self.log_test("User Status Update", True, "Status updated successfully")
            else:
                self.log_test("User Status Update", False, f"Status update failed: {data}")
                
        except Exception as e:
            self.log_test("User Status Update", False, f"Status update error: {str(e)}")
    
    async def test_user_search(self):
        """Test user search endpoint"""
        try:
            params = {"q": "API"}
            
            status, data = await self.make_request("GET", "/profiles/search", params=params)
            
            if status == 200:
                results = data.get("results", [])
                self.log_test("User Search", True, f"Search returned {len(results)} results")
            else:
                self.log_test("User Search", False, f"Search failed: {data}")
                
        except Exception as e:
            self.log_test("User Search", False, f"Search error: {str(e)}")
    
    async def test_user_statistics(self):
        """Test user statistics endpoint"""
        try:
            status, data = await self.make_request("GET", "/users/stats/overview")
            
            if status == 200:
                total_users = data.get("total_users", 0)
                self.log_test("User Statistics", True, f"Statistics retrieved: {total_users} total users")
            else:
                self.log_test("User Statistics", False, f"Statistics failed: {data}")
                
        except Exception as e:
            self.log_test("User Statistics", False, f"Statistics error: {str(e)}")
    
    async def test_profile_completion(self):
        """Test profile completion endpoint"""
        if not self.test_user_id:
            self.log_test("Profile Completion", False, "No test user ID available")
            return
        
        try:
            status, data = await self.make_request("GET", f"/profiles/{self.test_user_id}/completion")
            
            if status == 200:
                completion = data.get("completion", {})
                percentage = completion.get("percentage", 0)
                self.log_test("Profile Completion", True, f"Completion: {percentage}%")
            else:
                self.log_test("Profile Completion", False, f"Completion check failed: {data}")
                
        except Exception as e:
            self.log_test("Profile Completion", False, f"Completion error: {str(e)}")
    
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"\n📊 API TEST SUMMARY")
        print(f"{'='*50}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test_name']}: {result['message']}")
    
    async def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting User Management API Tests")
        print("="*50)
        print("⚠️  Note: Some tests may fail without proper authentication")
        print("   Make sure the FastAPI server is running on localhost:8000")
        print()
        
        # Basic tests
        await self.test_health_check()
        
        # User management tests (may require authentication)
        await self.test_user_registration()
        await self.test_get_users()
        await self.test_get_user_by_id()
        await self.test_update_user()
        await self.test_user_status_update()
        await self.test_user_search()
        await self.test_user_statistics()
        await self.test_profile_completion()
        
        # Print summary
        self.print_summary()

async def main():
    """Main test function"""
    async with APITester() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    print("🔧 User Management API Endpoint Tester")
    print("Make sure your FastAPI server is running: uvicorn app.main:app --reload")
    print()
    
    asyncio.run(main())

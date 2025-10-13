"""
User Management System Testing Script
Tests all user management endpoints and functionality
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth.firebase_auth import firebase_auth
from app.database.database_service import database_service
from app.services.profile_service import profile_service
from app.models.user import UserCreate, UserRole, UserStatus
from app.database.collections import COLLECTIONS

class UserManagementTester:
    """Comprehensive user management testing"""
    
    def __init__(self):
        self.test_results = []
        self.test_users = []
        
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
        
        if data and not success:
            print(f"   Data: {json.dumps(data, indent=2, default=str)}")
    
    async def test_firebase_connection(self):
        """Test Firebase connection"""
        try:
            # Try to get a non-existent user to test connection
            user = await firebase_auth.get_user_by_email("nonexistent@test.com")
            self.log_test("Firebase Connection", True, "Firebase Auth is accessible")
        except Exception as e:
            if "auth/user-not-found" in str(e) or "There is no user record" in str(e):
                self.log_test("Firebase Connection", True, "Firebase Auth is working (expected user not found)")
            else:
                self.log_test("Firebase Connection", False, f"Firebase connection failed: {str(e)}")
    
    async def test_firestore_connection(self):
        """Test Firestore connection"""
        try:
            # Test basic Firestore operations
            success, collections, error = await database_service.query_collection(COLLECTIONS['users'], limit=1)
            if success:
                self.log_test("Firestore Connection", True, "Firestore is accessible")
            else:
                self.log_test("Firestore Connection", False, f"Firestore error: {error}")
        except Exception as e:
            self.log_test("Firestore Connection", False, f"Firestore connection failed: {str(e)}")
    
    async def test_user_creation(self):
        """Test user creation functionality"""
        try:
            # Create test user data
            test_user_data = {
                "email": f"testuser_{datetime.now().strftime('%Y%m%d_%H%M%S')}@facilityfix.test",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User",
                "phone_number": "+1234567890",
                "role": UserRole.STAFF.value,
                "building_id": "test_building_001",
                "unit_id": None,
                "department": "Testing"
            }
            
            # Create user in Firebase Auth
            firebase_user = await firebase_auth.create_user(
                email=test_user_data["email"],
                password=test_user_data["password"],
                display_name=f"{test_user_data['first_name']} {test_user_data['last_name']}"
            )
            
            # Set custom claims
            custom_claims = {
                "role": test_user_data["role"],
                "building_id": test_user_data["building_id"],
                "department": test_user_data["department"]
            }
            await firebase_auth.set_custom_claims(firebase_user["uid"], custom_claims)
            
            # Create user profile in Firestore
            user_profile_data = {
                "id": firebase_user["uid"],
                "email": test_user_data["email"],
                "first_name": test_user_data["first_name"],
                "last_name": test_user_data["last_name"],
                "phone_number": test_user_data["phone_number"],
                "role": test_user_data["role"],
                "building_id": test_user_data["building_id"],
                "unit_id": test_user_data["unit_id"],
                "department": test_user_data["department"],
                "status": UserStatus.ACTIVE.value,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            success, profile_id, error = await database_service.create_document(
                COLLECTIONS['users'],
                user_profile_data,
                validate=True
            )
            
            if success:
                self.test_users.append(firebase_user["uid"])
                self.log_test("User Creation", True, f"User created successfully: {firebase_user['uid']}")
                return firebase_user["uid"]
            else:
                self.log_test("User Creation", False, f"Profile creation failed: {error}")
                return None
                
        except Exception as e:
            self.log_test("User Creation", False, f"User creation failed: {str(e)}")
            return None
    
    async def test_user_retrieval(self, user_id: str):
        """Test user retrieval functionality"""
        try:
            # Test getting user profile
            success, user_data, error = await database_service.get_document(COLLECTIONS['users'], user_id)
            
            if success and user_data:
                self.log_test("User Retrieval", True, f"User retrieved successfully")
                return user_data
            else:
                self.log_test("User Retrieval", False, f"User retrieval failed: {error}")
                return None
                
        except Exception as e:
            self.log_test("User Retrieval", False, f"User retrieval error: {str(e)}")
            return None
    
    async def test_user_update(self, user_id: str):
        """Test user update functionality"""
        try:
            # Update user data
            update_data = {
                "phone_number": "+9876543210",
                "department": "Updated Testing Department",
                "updated_at": datetime.utcnow()
            }
            
            success, error = await database_service.update_document(
                COLLECTIONS['users'],
                user_id,
                update_data
            )
            
            if success:
                self.log_test("User Update", True, "User updated successfully")
                
                # Verify update
                success, updated_user, error = await database_service.get_document(COLLECTIONS['users'], user_id)
                if success and updated_user.get("phone_number") == "+9876543210":
                    self.log_test("User Update Verification", True, "Update verified successfully")
                else:
                    self.log_test("User Update Verification", False, "Update verification failed")
            else:
                self.log_test("User Update", False, f"User update failed: {error}")
                
        except Exception as e:
            self.log_test("User Update", False, f"User update error: {str(e)}")
    
    async def test_profile_service(self, user_id: str):
        """Test profile service functionality"""
        try:
            # Test complete profile retrieval
            success, complete_profile, error = await profile_service.get_complete_profile(user_id)
            
            if success and complete_profile:
                self.log_test("Profile Service - Complete Profile", True, "Complete profile retrieved")
                
                # Check completion score
                completion_score = complete_profile.get('completion_score', {})
                if 'percentage' in completion_score:
                    self.log_test("Profile Completion Score", True, 
                                f"Completion: {completion_score['percentage']}%")
                else:
                    self.log_test("Profile Completion Score", False, "No completion score calculated")
            else:
                self.log_test("Profile Service - Complete Profile", False, f"Failed: {error}")
                
        except Exception as e:
            self.log_test("Profile Service", False, f"Profile service error: {str(e)}")
    
    async def test_user_search(self):
        """Test user search functionality"""
        try:
            # Test search functionality
            success, search_results, error = await profile_service.search_users("Test")
            
            if success:
                self.log_test("User Search", True, f"Search returned {len(search_results)} results")
            else:
                self.log_test("User Search", False, f"Search failed: {error}")
                
        except Exception as e:
            self.log_test("User Search", False, f"Search error: {str(e)}")
    
    async def test_user_status_update(self, user_id: str):
        """Test user status update functionality"""
        try:
            # Test status update
            update_data = {
                "status": UserStatus.SUSPENDED.value,
                "updated_at": datetime.utcnow()
            }
            
            success, error = await database_service.update_document(
                COLLECTIONS['users'],
                user_id,
                update_data
            )
            
            if success:
                self.log_test("User Status Update", True, "Status updated to suspended")
                
                # Verify status update
                success, user_data, error = await database_service.get_document(COLLECTIONS['users'], user_id)
                if success and user_data.get("status") == UserStatus.SUSPENDED.value:
                    self.log_test("Status Update Verification", True, "Status change verified")
                else:
                    self.log_test("Status Update Verification", False, "Status change not verified")
            else:
                self.log_test("User Status Update", False, f"Status update failed: {error}")
                
        except Exception as e:
            self.log_test("User Status Update", False, f"Status update error: {str(e)}")
    
    async def test_user_deletion(self, user_id: str):
        """Test user deletion functionality"""
        try:
            # Test soft delete (status change to inactive)
            update_data = {
                "status": UserStatus.INACTIVE.value,
                "updated_at": datetime.utcnow()
            }
            
            success, error = await database_service.update_document(
                COLLECTIONS['users'],
                user_id,
                update_data
            )
            
            if success:
                self.log_test("User Soft Delete", True, "User deactivated successfully")
            else:
                self.log_test("User Soft Delete", False, f"Soft delete failed: {error}")
                
        except Exception as e:
            self.log_test("User Soft Delete", False, f"Soft delete error: {str(e)}")
    
    async def cleanup_test_users(self):
        """Clean up test users"""
        print("\n🧹 Cleaning up test users...")
        
        for user_id in self.test_users:
            try:
                # Delete from Firestore
                success, error = await database_service.delete_document(COLLECTIONS['users'], user_id)
                if success:
                    print(f"Deleted user profile: {user_id}")
                else:
                    print(f"Failed to delete user profile {user_id}: {error}")
                
                # Delete from Firebase Auth
                try:
                    firebase_auth.delete_user(user_id)
                    print(f"Deleted Firebase user: {user_id}")
                except Exception as e:
                    print(f"Failed to delete Firebase user {user_id}: {str(e)}")
                    
            except Exception as e:
                print(f"Cleanup error for {user_id}: {str(e)}")
    
    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"\nTEST SUMMARY")
        print(f"{'='*50}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test_name']}: {result['message']}")
    
    async def run_all_tests(self):
        """Run all user management tests"""
        print("Starting User Management System Tests")
        print("="*50)
        
        # Basic connectivity tests
        await self.test_firebase_connection()
        await self.test_firestore_connection()
        
        # User lifecycle tests
        user_id = await self.test_user_creation()
        
        if user_id:
            user_data = await self.test_user_retrieval(user_id)
            await self.test_user_update(user_id)
            await self.test_profile_service(user_id)
            await self.test_user_status_update(user_id)
            await self.test_user_search()
            await self.test_user_deletion(user_id)
        
        # Cleanup
        await self.cleanup_test_users()
        
        # Print summary
        self.print_summary()

async def main():
    """Main test function"""
    tester = UserManagementTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())

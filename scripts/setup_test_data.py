"""
Setup Test Data for User Management System
Creates sample users, buildings, and units for testing
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth.firebase_auth import firebase_auth
from app.database.database_service import database_service
from app.models.user import UserRole, UserStatus
from app.database.collections import COLLECTIONS

class TestDataSetup:
    """Setup test data for user management system"""
    
    def __init__(self):
        self.created_users = []
        self.created_buildings = []
        self.created_units = []
    
    async def create_test_buildings(self):
        """Create test buildings"""
        print("Creating test buildings...")
        
        buildings = [
            {
                "id": "building_001",
                "building_name": "Sunrise Tower",
                "address": "123 Main Street, Metro City",
                "total_floors": 25,
                "total_units": 100,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "building_002", 
                "building_name": "Ocean View Residences",
                "address": "456 Beach Avenue, Coastal City",
                "total_floors": 15,
                "total_units": 60,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        for building in buildings:
            try:
                success, building_id, error = await database_service.create_document(
                    COLLECTIONS['buildings'],
                    building,
                    validate=True
                )
                
                if success:
                    self.created_buildings.append(building_id)
                    print(f"Created building: {building['building_name']}")
                else:
                    print(f"Failed to create building {building['building_name']}: {error}")
                    
            except Exception as e:
                print(f"Error creating building {building['building_name']}: {str(e)}")
    
    async def create_test_units(self):
        """Create test units"""
        print("Creating test units...")
        
        units = [
            # Units for building_001
            {"id": "unit_001", "building_id": "building_001", "unit_number": "101", "floor_number": 1, "occupancy_status": "occupied"},
            {"id": "unit_002", "building_id": "building_001", "unit_number": "102", "floor_number": 1, "occupancy_status": "occupied"},
            {"id": "unit_003", "building_id": "building_001", "unit_number": "201", "floor_number": 2, "occupancy_status": "vacant"},
            
            # Units for building_002
            {"id": "unit_004", "building_id": "building_002", "unit_number": "301", "floor_number": 3, "occupancy_status": "occupied"},
            {"id": "unit_005", "building_id": "building_002", "unit_number": "302", "floor_number": 3, "occupancy_status": "vacant"},
        ]
        
        for unit in units:
            try:
                unit["created_at"] = datetime.utcnow()
                unit["updated_at"] = datetime.utcnow()
                
                success, unit_id, error = await database_service.create_document(
                    COLLECTIONS['units'],
                    unit,
                    validate=True
                )
                
                if success:
                    self.created_units.append(unit_id)
                    print(f"Created unit: {unit['unit_number']} in {unit['building_id']}")
                else:
                    print(f"Failed to create unit {unit['unit_number']}: {error}")
                    
            except Exception as e:
                print(f"Error creating unit {unit['unit_number']}: {str(e)}")
    
    async def create_test_users(self):
        """Create test users"""
        print("👥 Creating test users...")
        
        test_users = [
            {
                "email": "admin@facilityfix.test",
                "password": "AdminPass123!",
                "first_name": "System",
                "last_name": "Administrator",
                "phone_number": "+1234567890",
                "role": UserRole.ADMIN.value,
                "building_id": None,
                "unit_id": None,
                "department": "Administration"
            },
            {
                "email": "maintenance@facilityfix.test",
                "password": "StaffPass123!",
                "first_name": "John",
                "last_name": "Maintenance",
                "phone_number": "+1234567891",
                "role": UserRole.STAFF.value,
                "building_id": "building_001",
                "unit_id": None,
                "department": "Maintenance"
            },
            {
                "email": "tenant1@facilityfix.test",
                "password": "TenantPass123!",
                "first_name": "Alice",
                "last_name": "Johnson",
                "phone_number": "+1234567892",
                "role": UserRole.TENANT.value,
                "building_id": "building_001",
                "unit_id": "unit_001",
                "department": None
            },
            {
                "email": "tenant2@facilityfix.test",
                "password": "TenantPass123!",
                "first_name": "Bob",
                "last_name": "Smith",
                "phone_number": "+1234567893",
                "role": UserRole.TENANT.value,
                "building_id": "building_002",
                "unit_id": "unit_004",
                "department": None
            },
            {
                "email": "staff2@facilityfix.test",
                "password": "StaffPass123!",
                "first_name": "Sarah",
                "last_name": "Engineer",
                "phone_number": "+1234567894",
                "role": UserRole.STAFF.value,
                "building_id": "building_002",
                "unit_id": None,
                "department": "Engineering"
            }
        ]
        
        for user_data in test_users:
            try:
                # Create user in Firebase Auth
                firebase_user = await firebase_auth.create_user(
                    email=user_data["email"],
                    password=user_data["password"],
                    display_name=f"{user_data['first_name']} {user_data['last_name']}"
                )
                
                # Set custom claims
                custom_claims = {
                    "role": user_data["role"],
                    "building_id": user_data["building_id"],
                    "unit_id": user_data["unit_id"],
                    "department": user_data["department"]
                }
                await firebase_auth.set_custom_claims(firebase_user["uid"], custom_claims)
                
                # Create user profile in Firestore
                user_profile_data = {
                    "id": firebase_user["uid"],
                    "email": user_data["email"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "phone_number": user_data["phone_number"],
                    "role": user_data["role"],
                    "building_id": user_data["building_id"],
                    "unit_id": user_data["unit_id"],
                    "department": user_data["department"],
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
                    self.created_users.append(firebase_user["uid"])
                    print(f"Created user: {user_data['email']} ({user_data['role']})")
                else:
                    print(f"Failed to create profile for {user_data['email']}: {error}")
                    
            except Exception as e:
                print(f"Error creating user {user_data['email']}: {str(e)}")
    
    async def setup_all_test_data(self):
        """Setup all test data"""
        print("Setting up test data for User Management System")
        print("="*60)
        
        await self.create_test_buildings()
        await self.create_test_units()
        await self.create_test_users()
        
        print(f"\nSETUP SUMMARY")
        print(f"{'='*30}")
        print(f"Buildings created: {len(self.created_buildings)}")
        print(f"Units created: {len(self.created_units)}")
        print(f"Users created: {len(self.created_users)}")
        
        print(f"\nTest data setup complete!")
        print(f"You can now test the user management system with the created data.")

async def main():
    """Main setup function"""
    setup = TestDataSetup()
    await setup.setup_all_test_data()

if __name__ == "__main__":
    asyncio.run(main())

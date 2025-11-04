from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..models.user import UserRole
from ..models.database_models import UserProfile
import asyncio

class UserIdService:
    @staticmethod
    def get_role_prefix(role: UserRole) -> str:
        """Get the prefix for user ID based on role"""
        prefixes = {
            UserRole.ADMIN: "A",
            UserRole.STAFF: "S", 
            UserRole.TENANT: "T"
        }
        return prefixes[role]
    
    @staticmethod
    async def generate_user_id(role: UserRole) -> str:
        """Generate next available user ID for the role"""
        prefix = UserIdService.get_role_prefix(role)
        
        # Get all users with this role to find the highest number
        success, users, error = await database_service.query_documents(
            COLLECTIONS['users'],
            [("role", "==", role.value)]
        )
        
        if not success:
            # If query fails, start from 1
            return f"{prefix}-0001"
        
        # Find the highest existing number for this role
        max_number = 0
        for user in users:
            user_id = user.get('user_id', '')
            if user_id.startswith(f"{prefix}-"):
                try:
                    number = int(user_id.split('-')[1])
                    max_number = max(max_number, number)
                except (IndexError, ValueError):
                    continue
        
        # Generate next number
        next_number = max_number + 1
        return f"{prefix}-{next_number:04d}"
    
    @staticmethod
    async def get_user_profile(user_id: str) -> UserProfile:
        """Get user profile by user ID"""
        success, user_data, error = await database_service.get_document(
            COLLECTIONS['users'], 
            user_id
        )
        
        if not success or not user_data:
            return None
            
        return UserProfile(**user_data)
    
    @staticmethod
    def parse_building_unit(building_unit: str) -> tuple:
        """Parse building unit string into building_id and unit_id"""
        if not building_unit or '-' not in building_unit:
            return None, None
        
        parts = building_unit.split('-')
        if len(parts) != 2:
            return None, None
        
        building_id = parts[0].upper()
        unit_number = parts[1]
        
        return building_id, unit_number
    
    
    @staticmethod 
    async def get_staff_profile_from_staff_id(staff_id: str) -> UserProfile:
        """Get staff profile by staff ID"""
        success, user_data, error = await database_service.query_collection(
            COLLECTIONS['users'],
            [("staff_id", "==", staff_id)],
        
        )
        
        if not success or not user_data:
            print("No user data found for staff ID:", staff_id)
            print("Error:", error)
            print("User Data:", user_data)
            return None
        
            
        return UserProfile(**user_data[0])


    @staticmethod 
    async def get_user_full_name(user_id: str) -> str:
        """Get full name of user by user ID"""
        user_profile = await UserIdService.get_user_profile(user_id)
        if not user_profile:
            return "Unknown User"
        
        return f"{user_profile.first_name} {user_profile.last_name}"
user_id_service = UserIdService()

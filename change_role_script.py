import asyncio
import sys
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from app.auth.firebase_auth import firebase_auth
from datetime import datetime

async def change_user_role(user_id: str, new_role: str):
    """Change a user's role by user_id"""
    try:
        # Find user by user_id in Firestore
        success, users, error = await database_service.query_documents(
            COLLECTIONS['users'],
            [("user_id", "==", user_id)]
        )
        
        if not success or not users:
            print(f"User with ID {user_id} not found")
            return False
        
        user_profile = users[0]
        firebase_uid = user_profile['id']
        
        print(f"Found user: {user_profile.get('email')} (current role: {user_profile.get('role')})")
        
        # Update role in Firestore
        update_data = {
            "role": new_role,
            "updated_at": datetime.utcnow()
        }
        
        success, error = await database_service.update_document(
            COLLECTIONS['users'],
            firebase_uid,
            update_data
        )
        
        if not success:
            print(f"Failed to update user role in Firestore: {error}")
            return False
        
        # Update custom claims in Firebase
        current_claims = {
            "role": new_role,
            "user_id": user_id,
            "building_id": user_profile.get("building_id"),
            "unit_id": user_profile.get("unit_id"),
            "department": user_profile.get("department")
        }
        
        await firebase_auth.set_custom_claims(firebase_uid, current_claims)
        
        print(f"✅ Successfully changed user {user_id} role to {new_role}")
        print(f"📧 Email: {user_profile.get('email')}")
        print(f"🔄 Old role: {user_profile.get('role')} → New role: {new_role}")
        
        return True
        
    except Exception as e:
        print(f"Error changing user role: {str(e)}")
        return False

async def list_users():
    """List all users to help find the user_id"""
    try:
        success, users, error = await database_service.get_all_documents(COLLECTIONS['users'])
        
        if not success:
            print(f"Failed to get users: {error}")
            return
        
        print("\n📋 Current Users:")
        print("-" * 60)
        for user in users:
            print(f"User ID: {user.get('user_id', 'N/A')}")
            print(f"Email: {user.get('email', 'N/A')}")
            print(f"Role: {user.get('role', 'N/A')}")
            print(f"Name: {user.get('first_name', '')} {user.get('last_name', '')}")
            print("-" * 60)
            
    except Exception as e:
        print(f"Error listing users: {str(e)}")

async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python change_role_script.py list                    # List all users")
        print("  python change_role_script.py <user_id> <new_role>   # Change user role")
        print("")
        print("Examples:")
        print("  python change_role_script.py list")
        print("  python change_role_script.py A-0001 tenant")
        print("  python change_role_script.py T-0001 admin")
        print("")
        print("Valid roles: admin, staff, tenant")
        return
    
    if sys.argv[1] == "list":
        await list_users()
        return
    
    if len(sys.argv) < 3:
        print("Error: Please provide both user_id and new_role")
        print("Example: python change_role_script.py A-0001 tenant")
        return
    
    user_id = sys.argv[1]
    new_role = sys.argv[2].lower()
    
    if new_role not in ["admin", "staff", "tenant"]:
        print(f"Error: Invalid role '{new_role}'. Valid roles are: admin, staff, tenant")
        return
    
    print(f"🔄 Changing user {user_id} role to {new_role}...")
    success = await change_user_role(user_id, new_role)
    
    if success:
        print("\n✅ Role change completed successfully!")
        print("\n💡 Next steps:")
        print("1. Generate a new token using /auth/exchange-token endpoint")
        print("2. Use the new token to test the updated role permissions")
    else:
        print("\n❌ Role change failed!")

if __name__ == "__main__":
    asyncio.run(main())

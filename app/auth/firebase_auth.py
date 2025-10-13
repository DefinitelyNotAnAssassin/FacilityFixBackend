import firebase_admin
from firebase_admin import credentials, auth
import os
from typing import Optional
from ..core.firebase_init import initialize_firebase, is_firebase_available

class FirebaseAuth:
    def __init__(self):
        if not is_firebase_available():
            if not initialize_firebase():
                raise Exception("Firebase initialization failed - Auth not available")
    
    async def verify_token(self, token: str) -> Optional[dict]:
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            print(f"Token verification failed: {e}")
            return None
    
    async def create_user(self, email: str, password: str, display_name: str = None) -> dict:
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            return {
                "uid": user.uid,
                "email": user.email,
            }
        except Exception as e:
            raise Exception(f"User creation failed: {e}")
    
    async def set_custom_claims(self, uid: str, claims: dict):
        try:
            auth.set_custom_user_claims(uid, claims)
        except Exception as e:
            raise Exception(f"Setting custom claims failed: {e}")
    
    async def get_user_by_email(self, email: str):
        try:
            user = auth.get_user_by_email(email)
            return user
        except Exception as e:
            return None

    async def get_user(self, uid: str):
        """Get user by UID"""
        try:
            user = auth.get_user(uid)
            return user
        except Exception as e:
            print(f"Get user failed: {e}")
            return None
    
    async def create_custom_token(self, uid: str, additional_claims: dict = None) -> str:
        """Create a custom token for testing purposes"""
        try:
            custom_token = auth.create_custom_token(uid, additional_claims)
            return custom_token.decode('utf-8')
        except Exception as e:
            raise Exception(f"Custom token creation failed: {e}")
    
    async def delete_user(self, uid: str):
        """Delete a user from Firebase Auth"""
        try:
            auth.delete_user(uid)
        except Exception as e:
            raise Exception(f"User deletion failed: {e}")
    
    async def update_user(self, uid: str, **kwargs):
        """Update user properties in Firebase Auth"""
        try:
            auth.update_user(uid, **kwargs)
        except Exception as e:
            raise Exception(f"User update failed: {e}")

firebase_auth = FirebaseAuth()

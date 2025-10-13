from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from ..database.database_service import database_service
from ..database.collections import COLLECTIONS
from ..auth.firebase_auth import firebase_auth
import re

class ProfileService:
    def __init__(self):
        self.db = database_service
    
    async def get_complete_profile(self, user_ref: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch a profile by Firebase UID (doc id) OR by human user_id (e.g., T-0001).
        Returns the Firestore profile enriched with Firebase Auth data and a completion score.
        """
        try:
            # 1) Try treating user_ref as a Firestore document id (Firebase UID)
            ok, profile_data, err = await self.db.get_document(COLLECTIONS["users"], user_ref)

            # 2) If not found, resolve by the user_id field (e.g., T-0001)
            if not ok or not profile_data:
                q_ok, docs, q_err = await self.db.query_documents(
                    COLLECTIONS["users"],
                    filters=[("user_id", "==", user_ref)],
                    limit=1,
                )
                if not q_ok:
                    return False, None, q_err
                if not docs:
                    return False, None, f"Document {user_ref} not found in users"
                profile_data = docs[0]  # includes _doc_id if your db wrapper adds it

            # 3) Enrich with Firebase Auth info (prefer email, fallback to stored UID)
            try:
                fb_user = None
                email = profile_data.get("email")
                if email:
                    fb_user = await firebase_auth.get_user_by_email(email)
                elif profile_data.get("id"):  # Firebase UID stored in profile
                    fb_user = await firebase_auth.get_user(profile_data["id"])

                if fb_user:
                    profile_data.update({
                        "firebase_uid": fb_user.uid,
                        "email_verified": getattr(fb_user, "email_verified", None),
                        "last_sign_in": getattr(getattr(fb_user, "user_metadata", None), "last_sign_in_time", None),
                        "creation_time": getattr(getattr(fb_user, "user_metadata", None), "creation_time", None),
                        "provider_data": [
                            {
                                "provider_id": getattr(p, "provider_id", None),
                                "uid": getattr(p, "uid", None),
                                "email": getattr(p, "email", None),
                            }
                            for p in getattr(fb_user, "provider_data", []) or []
                        ],
                    })
            except Exception as e:
                # Firebase enrichment is optional
                profile_data["firebase_error"] = str(e)

            # 4) Compute completion score
            completion_score = self._calculate_profile_completion(profile_data)
            profile_data["completion_score"] = completion_score

            return True, profile_data, None

        except Exception as e:
            return False, None, f"Error retrieving complete profile: {str(e)}"
    
    def _calculate_profile_completion(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate profile completion percentage and missing fields"""
        required_fields = ['first_name', 'last_name', 'email', 'role']
        optional_fields = ['phone_number', 'department', 'building_id', 'unit_id']
        
        completed_required = sum(1 for field in required_fields if profile_data.get(field))
        completed_optional = sum(1 for field in optional_fields if profile_data.get(field))
        
        total_fields = len(required_fields) + len(optional_fields)
        completed_fields = completed_required + completed_optional
        
        percentage = (completed_fields / total_fields) * 100
        
        missing_required = [field for field in required_fields if not profile_data.get(field)]
        missing_optional = [field for field in optional_fields if not profile_data.get(field)]
        
        return {
            'percentage': round(percentage, 1),
            'completed_fields': completed_fields,
            'total_fields': total_fields,
            'missing_required': missing_required,
            'missing_optional': missing_optional,
            'is_complete': len(missing_required) == 0
        }
    
    async def validate_profile_update(self, user_id: str, update_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate profile update data"""
        try:
            # Phone number validation
            if 'phone_number' in update_data and update_data['phone_number']:
                phone = update_data['phone_number']
                # Basic phone validation (adjust regex as needed)
                if not re.match(r'^\+?[\d\s\-$$$$]{10,15}$', phone):
                    return False, "Invalid phone number format"
            
            # Name validation
            for field in ['first_name', 'last_name']:
                if field in update_data and update_data[field]:
                    name = update_data[field].strip()
                    if len(name) < 2 or len(name) > 50:
                        return False, f"{field.replace('_', ' ').title()} must be between 2 and 50 characters"
                    if not re.match(r'^[a-zA-Z\s\-\'\.]+$', name):
                        return False, f"{field.replace('_', ' ').title()} contains invalid characters"
            
            # Department validation
            if 'department' in update_data and update_data['department']:
                dept = update_data['department'].strip()
                if len(dept) > 100:
                    return False, "Department name too long (max 100 characters)"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    async def update_profile_with_history(self, user_id: str, update_data: Dict[str, Any], 
                                        updated_by: str) -> Tuple[bool, Optional[str]]:
        """Update profile and maintain history"""
        try:
            # Validate update
            is_valid, validation_error = await self.validate_profile_update(user_id, update_data)
            if not is_valid:
                return False, validation_error
            
            # Get current profile for history
            success, current_profile, error = await self.db.get_document(COLLECTIONS['users'], user_id)
            if not success:
                return False, f"Could not retrieve current profile: {error}"
            
            # Create history entry
            history_entry = {
                'user_id': user_id,
                'updated_by': updated_by,
                'updated_at': datetime.utcnow(),
                'changes': {},
                'previous_values': {}
            }
            
            # Track changes
            for field, new_value in update_data.items():
                if field != 'updated_at':  # Skip timestamp
                    old_value = current_profile.get(field)
                    if old_value != new_value:
                        history_entry['changes'][field] = new_value
                        history_entry['previous_values'][field] = old_value
            
            # Update profile
            update_data['updated_at'] = datetime.utcnow()
            success, error = await self.db.update_document(COLLECTIONS['users'], user_id, update_data)
            
            if not success:
                return False, error
            
            # Save history if there were changes
            if history_entry['changes']:
                await self._save_profile_history(history_entry)
            
            return True, None
            
        except Exception as e:
            return False, f"Error updating profile: {str(e)}"
    
    async def _save_profile_history(self, history_entry: Dict[str, Any]):
        """Save profile change history"""
        try:
            # Create profile_history collection entry
            await self.db.create_document('profile_history', history_entry, validate=False)
        except Exception as e:
            # History saving is optional, don't fail the main operation
            print(f"Warning: Could not save profile history: {str(e)}")
    
    async def get_profile_history(self, user_id: str, limit: int = 10) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get profile change history"""
        try:
            success, history, error = await self.db.query_collection(
                'profile_history',
                filters=[('user_id', '==', user_id)],
                limit=limit
            )
            
            if success:
                # Sort by date (most recent first)
                history.sort(key=lambda x: x.get('updated_at', datetime.min), reverse=True)
            
            return success, history if success else [], error
            
        except Exception as e:
            return False, [], f"Error retrieving profile history: {str(e)}"
    
    async def get_users_by_building(self, building_id: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Get all users in a specific building"""
        try:
            success, users, error = await self.db.query_collection(
                COLLECTIONS['users'],
                filters=[('building_id', '==', building_id), ('status', '==', 'active')]
            )
            
            return success, users if success else [], error
            
        except Exception as e:
            return False, [], f"Error retrieving building users: {str(e)}"
    
    async def search_users(self, search_term: str, filters: Dict[str, Any] = None) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """Search users by name, email, or department"""
        try:
            # Get all users (Firestore doesn't support full-text search natively)
            success, all_users, error = await self.db.query_collection(COLLECTIONS['users'])
            
            if not success:
                return False, [], error
            
            # Filter by search term
            search_term = search_term.lower()
            filtered_users = []
            
            for user in all_users:
                # Search in name, email, department
                searchable_text = ' '.join([
                    user.get('first_name', ''),
                    user.get('last_name', ''),
                    user.get('email', ''),
                    user.get('department', '')
                ]).lower()
                
                if search_term in searchable_text:
                    # Apply additional filters if provided
                    if filters:
                        match = True
                        for filter_key, filter_value in filters.items():
                            if user.get(filter_key) != filter_value:
                                match = False
                                break
                        if match:
                            filtered_users.append(user)
                    else:
                        filtered_users.append(user)
            
            return True, filtered_users, None
            
        except Exception as e:
            return False, [], f"Error searching users: {str(e)}"
    
    async def export_user_data(self, user_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Export complete user data for GDPR compliance"""
        try:
            # Get complete profile
            success, profile_data, error = await self.get_complete_profile(user_id)
            if not success:
                return False, None, error
            
            # Get profile history
            history_success, history_data, _ = await self.get_profile_history(user_id, limit=100)
            
            # Get user's repair requests
            requests_success, repair_requests, _ = await self.db.query_collection(
                COLLECTIONS['repair_requests'],
                filters=[('reported_by', '==', user_id)]
            )
            
            # Get user's maintenance tasks
            tasks_success, maintenance_tasks, _ = await self.db.query_collection(
                COLLECTIONS['maintenance_tasks'],
                filters=[('assigned_to', '==', user_id)]
            )
            
            export_data = {
                'profile': profile_data,
                'profile_history': history_data if history_success else [],
                'repair_requests': repair_requests if requests_success else [],
                'maintenance_tasks': maintenance_tasks if tasks_success else [],
                'export_date': datetime.utcnow(),
                'export_version': '1.0'
            }
            
            return True, export_data, None
            
        except Exception as e:
            return False, None, f"Error exporting user data: {str(e)}"

# Create global service instance
profile_service = ProfileService()

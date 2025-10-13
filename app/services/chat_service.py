"""
Chat Service - Business logic for chat functionality
Handles chat rooms, messages, and real-time communication
"""

from typing import Optional, List, Dict
from datetime import datetime
import logging

from google.cloud.firestore_v1 import FieldFilter, Query
from ..database.firestore_client import get_firestore_client
from ..database.collections import COLLECTIONS

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat rooms and messages"""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.chat_rooms_collection = self.db.collection(COLLECTIONS['chat_rooms'])
        self.chat_messages_collection = self.db.collection(COLLECTIONS['chat_messages'])
        self.users_collection = self.db.collection(COLLECTIONS['users'])
        self.user_profiles_collection = self.db.collection(COLLECTIONS['user_profiles'])
    
    # ===== Chat Room Operations =====
    
    async def get_or_create_room(
        self,
        participants: List[str],
        created_by: str,
        room_type: str = "direct",
        concern_slip_id: Optional[str] = None,
        job_service_id: Optional[str] = None,
        work_permit_id: Optional[str] = None,
        room_name: Optional[str] = None
    ) -> Dict:
        """Get existing chat room or create a new one"""
        try:
            # Check if room already exists for the reference
            query = self.chat_rooms_collection.where(filter=FieldFilter("is_active", "==", True))
            
            if concern_slip_id:
                query = query.where(filter=FieldFilter("concern_slip_id", "==", concern_slip_id))
            elif job_service_id:
                query = query.where(filter=FieldFilter("job_service_id", "==", job_service_id))
            elif work_permit_id:
                query = query.where(filter=FieldFilter("work_permit_id", "==", work_permit_id))
            else:
                # For direct messages, check if room with same participants exists
                # Sort participants for consistent comparison
                sorted_participants = sorted(participants)
                query = query.where(filter=FieldFilter("room_type", "==", "direct"))
            
            existing_rooms = query.stream()
            
            for room_doc in existing_rooms:
                room_data = room_doc.to_dict()
                room_data['id'] = room_doc.id
                
                # For direct messages, verify participants match
                if room_type == "direct":
                    room_participants = sorted(room_data.get('participants', []))
                    if room_participants == sorted_participants:
                        return room_data
                else:
                    # For other types, first match is good
                    return room_data
            
            # No existing room found, create new one
            return await self.create_room(
                participants=participants,
                created_by=created_by,
                room_type=room_type,
                concern_slip_id=concern_slip_id,
                job_service_id=job_service_id,
                work_permit_id=work_permit_id,
                room_name=room_name
            )
            
        except Exception as e:
            logger.error(f"Error getting or creating chat room: {str(e)}")
            raise
    
    async def create_room(
        self,
        participants: List[str],
        created_by: str,
        room_type: str,
        concern_slip_id: Optional[str] = None,
        job_service_id: Optional[str] = None,
        work_permit_id: Optional[str] = None,
        room_name: Optional[str] = None
    ) -> Dict:
        """Create a new chat room"""
        try:
            # Get participant details (names and roles)
            participant_roles = {}
            participant_names = {}
            
            for user_id in participants:
                user_data = await self._get_user_data(user_id)
                if user_data:
                    participant_roles[user_id] = user_data.get('role', 'tenant')
                    first_name = user_data.get('first_name', '')
                    last_name = user_data.get('last_name', '')
                    participant_names[user_id] = f"{first_name} {last_name}".strip()
            
            # Initialize unread counts
            unread_counts = {user_id: 0 for user_id in participants}
            
            room_data = {
                'participants': participants,
                'participant_roles': participant_roles,
                'participant_names': participant_names,
                'created_by': created_by,
                'room_type': room_type,
                'is_active': True,
                'last_message': None,
                'last_message_at': None,
                'unread_counts': unread_counts,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Add optional fields
            if concern_slip_id:
                room_data['concern_slip_id'] = concern_slip_id
            if job_service_id:
                room_data['job_service_id'] = job_service_id
            if work_permit_id:
                room_data['work_permit_id'] = work_permit_id
            if room_name:
                room_data['room_name'] = room_name
            
            # Create the room
            doc_ref = self.chat_rooms_collection.document()
            doc_ref.set(room_data)
            
            room_data['id'] = doc_ref.id
            
            logger.info(f"Created chat room {doc_ref.id} for {room_type}")
            return room_data
            
        except Exception as e:
            logger.error(f"Error creating chat room: {str(e)}")
            raise
    
    async def get_user_rooms(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get all chat rooms for a user"""
        try:
            query = (
                self.chat_rooms_collection
                .where(filter=FieldFilter("participants", "array_contains", user_id))
                .where(filter=FieldFilter("is_active", "==", True))
                .order_by("last_message_at", direction=Query.DESCENDING)
                .limit(limit)
            )
            
            rooms = []
            for doc in query.stream():
                room_data = doc.to_dict()
                room_data['id'] = doc.id
                rooms.append(room_data)
            
            return rooms
            
        except Exception as e:
            logger.error(f"Error getting user rooms: {str(e)}")
            raise
    
    async def get_room(self, room_id: str) -> Optional[Dict]:
        """Get a specific chat room"""
        try:
            doc = self.chat_rooms_collection.document(room_id).get()
            if doc.exists:
                room_data = doc.to_dict()
                room_data['id'] = doc.id
                return room_data
            return None
            
        except Exception as e:
            logger.error(f"Error getting room {room_id}: {str(e)}")
            raise
    
    # ===== Chat Message Operations =====
    
    async def send_message(
        self,
        room_id: str,
        sender_id: str,
        message_text: str,
        message_type: str = "text",
        attachments: Optional[List[str]] = None,
        reply_to: Optional[str] = None
    ) -> Dict:
        """Send a message to a chat room"""
        try:
            # Get sender details
            sender_data = await self._get_user_data(sender_id)
            if not sender_data:
                raise ValueError(f"Sender {sender_id} not found")
            
            sender_name = f"{sender_data.get('first_name', '')} {sender_data.get('last_name', '')}".strip()
            sender_role = sender_data.get('role', 'tenant')
            
            # Create message
            message_data = {
                'room_id': room_id,
                'sender_id': sender_id,
                'sender_name': sender_name,
                'sender_role': sender_role,
                'message_text': message_text,
                'message_type': message_type,
                'attachments': attachments or [],
                'reply_to': reply_to,
                'is_read': False,
                'read_by': [sender_id],  # Sender has "read" their own message
                'is_deleted': False,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            
            # Save message
            doc_ref = self.chat_messages_collection.document()
            doc_ref.set(message_data)
            message_data['id'] = doc_ref.id
            
            # Update room's last message
            await self._update_room_last_message(
                room_id=room_id,
                message_text=message_text,
                sender_id=sender_id
            )
            
            logger.info(f"Message sent to room {room_id} by {sender_id}")
            return message_data
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            raise
    
    async def get_room_messages(
        self,
        room_id: str,
        limit: int = 100,
        before_timestamp: Optional[datetime] = None
    ) -> List[Dict]:
        """Get messages for a chat room"""
        try:
            query = (
                self.chat_messages_collection
                .where(filter=FieldFilter("room_id", "==", room_id))
                .where(filter=FieldFilter("is_deleted", "==", False))
                .order_by("created_at", direction=Query.DESCENDING)
            )
            
            if before_timestamp:
                query = query.where(filter=FieldFilter("created_at", "<", before_timestamp))
            
            query = query.limit(limit)
            
            messages = []
            for doc in query.stream():
                message_data = doc.to_dict()
                message_data['id'] = doc.id
                messages.append(message_data)
            
            # Return in chronological order (oldest first)
            return list(reversed(messages))
            
        except Exception as e:
            logger.error(f"Error getting room messages: {str(e)}")
            raise
    
    async def mark_messages_as_read(self, room_id: str, user_id: str) -> int:
        """Mark all messages in a room as read for a user"""
        try:
            query = (
                self.chat_messages_collection
                .where(filter=FieldFilter("room_id", "==", room_id))
                .where(filter=FieldFilter("is_deleted", "==", False))
            )
            
            count = 0
            batch = self.db.batch()
            
            for doc in query.stream():
                message_data = doc.to_dict()
                read_by = message_data.get('read_by', [])
                
                # Only update if user hasn't read it yet
                if user_id not in read_by:
                    read_by.append(user_id)
                    batch.update(doc.reference, {
                        'read_by': read_by,
                        'updated_at': datetime.now()
                    })
                    count += 1
            
            if count > 0:
                batch.commit()
                
                # Reset unread count for user in room
                room_ref = self.chat_rooms_collection.document(room_id)
                room_ref.update({
                    f'unread_counts.{user_id}': 0,
                    'updated_at': datetime.now()
                })
            
            logger.info(f"Marked {count} messages as read for user {user_id} in room {room_id}")
            return count
            
        except Exception as e:
            logger.error(f"Error marking messages as read: {str(e)}")
            raise
    
    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """Soft delete a message (only by sender)"""
        try:
            doc_ref = self.chat_messages_collection.document(message_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return False
            
            message_data = doc.to_dict()
            
            # Only sender can delete their message
            if message_data.get('sender_id') != user_id:
                raise PermissionError("Only the sender can delete their message")
            
            doc_ref.update({
                'is_deleted': True,
                'deleted_at': datetime.now(),
                'updated_at': datetime.now()
            })
            
            logger.info(f"Message {message_id} deleted by {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting message: {str(e)}")
            raise
    
    # ===== Helper Methods =====
    
    async def _get_user_data(self, user_id: str) -> Optional[Dict]:
        """Get user data from users or user_profiles collection"""
        try:
            # Try user_profiles first
            doc = self.user_profiles_collection.document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            
            # Fallback to users collection
            doc = self.users_collection.document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user data for {user_id}: {str(e)}")
            return None
    
    async def _update_room_last_message(
        self,
        room_id: str,
        message_text: str,
        sender_id: str
    ):
        """Update room's last message preview and increment unread counts"""
        try:
            room_ref = self.chat_rooms_collection.document(room_id)
            room_doc = room_ref.get()
            
            if not room_doc.exists:
                return
            
            room_data = room_doc.to_dict()
            participants = room_data.get('participants', [])
            unread_counts = room_data.get('unread_counts', {})
            
            # Increment unread count for all participants except sender
            for participant_id in participants:
                if participant_id != sender_id:
                    current_count = unread_counts.get(participant_id, 0)
                    unread_counts[participant_id] = current_count + 1
            
            # Truncate message preview if too long
            preview = message_text[:100] + "..." if len(message_text) > 100 else message_text
            
            room_ref.update({
                'last_message': preview,
                'last_message_at': datetime.now(),
                'unread_counts': unread_counts,
                'updated_at': datetime.now()
            })
            
        except Exception as e:
            logger.error(f"Error updating room last message: {str(e)}")
    
    async def get_unread_count(self, user_id: str) -> int:
        """Get total unread message count for a user"""
        try:
            query = (
                self.chat_rooms_collection
                .where(filter=FieldFilter("participants", "array_contains", user_id))
                .where(filter=FieldFilter("is_active", "==", True))
            )
            
            total_unread = 0
            for doc in query.stream():
                room_data = doc.to_dict()
                unread_counts = room_data.get('unread_counts', {})
                total_unread += unread_counts.get(user_id, 0)
            
            return total_unread
            
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0


# Singleton instance
_chat_service = None

def get_chat_service() -> ChatService:
    """Get or create ChatService singleton"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service

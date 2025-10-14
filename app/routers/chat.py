"""
Chat Router - API endpoints for chat functionality
Handles chat rooms and messages
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..auth.dependencies import get_current_user
from ..services.chat_service import get_chat_service
from ..services.websocket_service import websocket_notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# ===== Request/Response Models =====

class CreateRoomRequest(BaseModel):
    participants: List[str] = Field(..., description="List of user IDs to include in the chat")
    room_type: str = Field(default="direct", description="Type of room: direct, concern_slip, job_service, work_permit")
    concern_slip_id: Optional[str] = None
    job_service_id: Optional[str] = None
    work_permit_id: Optional[str] = None
    room_name: Optional[str] = None

class SendMessageRequest(BaseModel):
    room_id: str = Field(..., description="ID of the chat room")
    message_text: str = Field(..., description="Message content")
    message_type: str = Field(default="text", description="Type of message: text, image, file, system")
    attachments: Optional[List[str]] = Field(default=None, description="List of attachment URLs")
    reply_to: Optional[str] = Field(default=None, description="ID of message being replied to")

class MarkAsReadRequest(BaseModel):
    room_id: str = Field(..., description="ID of the chat room")

# ===== Chat Room Endpoints =====

@router.post("/rooms")
async def create_or_get_room(
    request: CreateRoomRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new chat room or get existing one"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        # Ensure current user is in participants
        if user_id not in request.participants:
            request.participants.append(user_id)
        
        room = await chat_service.get_or_create_room(
            participants=request.participants,
            created_by=user_id,
            room_type=request.room_type,
            concern_slip_id=request.concern_slip_id,
            job_service_id=request.job_service_id,
            work_permit_id=request.work_permit_id,
            room_name=request.room_name
        )
        
        return {
            "success": True,
            "data": room,
            "message": "Chat room created or retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating/getting room: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rooms")
async def get_user_rooms(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Get all chat rooms for the current user"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        rooms = await chat_service.get_user_rooms(user_id=user_id, limit=limit)
        
        return {
            "success": True,
            "data": rooms,
            "count": len(rooms)
        }
        
    except Exception as e:
        logger.error(f"Error getting user rooms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rooms/{room_id}")
async def get_room(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific chat room"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        room = await chat_service.get_room(room_id=room_id)
        
        if not room:
            raise HTTPException(status_code=404, detail="Chat room not found")
        
        # Check if user is a participant
        if user_id not in room.get('participants', []):
            raise HTTPException(status_code=403, detail="Not authorized to access this room")
        
        return {
            "success": True,
            "data": room
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting room: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rooms/by-reference/{reference_type}/{reference_id}")
async def get_room_by_reference(
    reference_type: str,  # concern_slip, job_service, work_permit
    reference_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get chat room by reference (concern slip, job service, or work permit)"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        # Determine which field to query
        field_map = {
            'concern_slip': 'concern_slip_id',
            'job_service': 'job_service_id',
            'work_permit': 'work_permit_id'
        }
        
        if reference_type not in field_map:
            raise HTTPException(status_code=400, detail="Invalid reference type")
        
        # Build request based on reference type
        create_request = CreateRoomRequest(
            participants=[user_id],
            room_type=reference_type
        )
        
        if reference_type == 'concern_slip':
            create_request.concern_slip_id = reference_id
        elif reference_type == 'job_service':
            create_request.job_service_id = reference_id
        elif reference_type == 'work_permit':
            create_request.work_permit_id = reference_id
        
        # Get or create room
        room = await chat_service.get_or_create_room(
            participants=create_request.participants,
            created_by=user_id,
            room_type=create_request.room_type,
            concern_slip_id=create_request.concern_slip_id,
            job_service_id=create_request.job_service_id,
            work_permit_id=create_request.work_permit_id
        )
        
        return {
            "success": True,
            "data": room
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting room by reference: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== Message Endpoints =====

@router.post("/messages")
async def send_message(
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a message to a chat room"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        # Verify user is participant of the room
        room = await chat_service.get_room(room_id=request.room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Chat room not found")
        
        if user_id not in room.get('participants', []):
            raise HTTPException(status_code=403, detail="Not authorized to send messages in this room")
        
        # Send message
        message = await chat_service.send_message(
            room_id=request.room_id,
            sender_id=user_id,
            message_text=request.message_text,
            message_type=request.message_type,
            attachments=request.attachments,
            reply_to=request.reply_to
        )
        
        # Send real-time notification to other participants
        participants = room.get('participants', [])
        await websocket_notification_service.send_chat_message(
            room_id=request.room_id,
            message_data=message,
            participants=participants
        )
        
        return {
            "success": True,
            "data": message,
            "message": "Message sent successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rooms/{room_id}/messages")
async def get_room_messages(
    room_id: str,
    limit: int = Query(100, ge=1, le=200),
    before: Optional[str] = Query(None, description="ISO timestamp to get messages before"),
    current_user: dict = Depends(get_current_user)
):
    """Get messages for a chat room"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        # Verify user is participant of the room
        room = await chat_service.get_room(room_id=room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Chat room not found")
        
        if user_id not in room.get('participants', []):
            raise HTTPException(status_code=403, detail="Not authorized to view messages in this room")
        
        # Parse before timestamp if provided
        before_timestamp = None
        if before:
            try:
                before_timestamp = datetime.fromisoformat(before.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid timestamp format")
        
        # Get messages
        messages = await chat_service.get_room_messages(
            room_id=room_id,
            limit=limit,
            before_timestamp=before_timestamp
        )
        
        return {
            "success": True,
            "data": messages,
            "count": len(messages)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/messages/mark-read")
async def mark_messages_as_read(
    request: MarkAsReadRequest,
    current_user: dict = Depends(get_current_user)
):
    """Mark all messages in a room as read"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        # Verify user is participant of the room
        room = await chat_service.get_room(room_id=request.room_id)
        if not room:
            raise HTTPException(status_code=404, detail="Chat room not found")
        
        if user_id not in room.get('participants', []):
            raise HTTPException(status_code=403, detail="Not authorized to mark messages in this room")
        
        # Mark messages as read
        count = await chat_service.mark_messages_as_read(
            room_id=request.room_id,
            user_id=user_id
        )
        
        return {
            "success": True,
            "message": f"Marked {count} messages as read",
            "count": count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking messages as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a message (soft delete, only by sender)"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        success = await chat_service.delete_message(
            message_id=message_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return {
            "success": True,
            "message": "Message deleted successfully"
        }
        
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== Utility Endpoints =====

@router.get("/unread-count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get total unread message count for current user"""
    try:
        chat_service = get_chat_service()
        user_id = current_user.get('uid')
        
        count = await chat_service.get_unread_count(user_id=user_id)
        
        return {
            "success": True,
            "data": {
                "unread_count": count
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting unread count: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

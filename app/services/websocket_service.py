from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any
import json
import logging
from datetime import datetime
import asyncio
from uuid import uuid4

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket connection manager for real-time notifications"""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        # Store user roles for targeted broadcasting
        self.user_roles: Dict[str, str] = {}
        # Store building associations
        self.user_buildings: Dict[str, str] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, user_role: str, building_id: Optional[str] = None):
        """Accept a WebSocket connection and store user info"""
        try:
            await websocket.accept()
            
            # Initialize user connection set if not exists
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            
            # Add connection
            self.active_connections[user_id].add(websocket)
            
            # Store metadata
            self.connection_metadata[websocket] = {
                "user_id": user_id,
                "user_role": user_role,
                "building_id": building_id,
                "connected_at": datetime.now(),
                "connection_id": str(uuid4())
            }
            
            # Store user info for broadcasting
            self.user_roles[user_id] = user_role
            if building_id:
                self.user_buildings[user_id] = building_id
            
            logger.info(f"WebSocket connected: user_id={user_id}, role={user_role}, building_id={building_id}")
            
            # Send connection confirmation
            await self.send_personal_message(user_id, {
                "type": "connection_confirmed",
                "message": "WebSocket connection established",
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id
            })
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {str(e)}")
            raise
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        try:
            metadata = self.connection_metadata.get(websocket)
            if metadata:
                user_id = metadata["user_id"]
                
                # Remove from active connections
                if user_id in self.active_connections:
                    self.active_connections[user_id].discard(websocket)
                    
                    # If no more connections for this user, clean up
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]
                        if user_id in self.user_roles:
                            del self.user_roles[user_id]
                        if user_id in self.user_buildings:
                            del self.user_buildings[user_id]
                
                # Remove metadata
                del self.connection_metadata[websocket]
                
                logger.info(f"WebSocket disconnected: user_id={user_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {str(e)}")
    
    async def send_personal_message(self, user_id: str, message: Dict[str, Any]):
        """Send a message to a specific user (all their connections)"""
        if user_id not in self.active_connections:
            logger.warning(f"No active connections for user {user_id}")
            return
        
        message_json = json.dumps(message, default=str)
        connections_to_remove = []
        
        for websocket in self.active_connections[user_id].copy():
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {str(e)}")
                connections_to_remove.append(websocket)
        
        # Clean up failed connections
        for websocket in connections_to_remove:
            self.disconnect(websocket)
    
    async def broadcast_to_role(self, role: str, message: Dict[str, Any], building_id: Optional[str] = None):
        """Broadcast message to all users with a specific role"""
        message_json = json.dumps(message, default=str)
        sent_count = 0
        
        for user_id, user_role in self.user_roles.items():
            if user_role == role:
                # If building_id is specified, only send to users in that building
                if building_id and self.user_buildings.get(user_id) != building_id:
                    continue
                
                if user_id in self.active_connections:
                    connections_to_remove = []
                    
                    for websocket in self.active_connections[user_id].copy():
                        try:
                            await websocket.send_text(message_json)
                            sent_count += 1
                        except Exception as e:
                            logger.error(f"Error broadcasting to {role} user {user_id}: {str(e)}")
                            connections_to_remove.append(websocket)
                    
                    # Clean up failed connections
                    for websocket in connections_to_remove:
                        self.disconnect(websocket)
        
        logger.info(f"Broadcast to {role} role: {sent_count} messages sent")
    
    async def broadcast_to_building(self, building_id: str, message: Dict[str, Any], exclude_user: Optional[str] = None):
        """Broadcast message to all users in a specific building"""
        message_json = json.dumps(message, default=str)
        sent_count = 0
        
        for user_id, user_building_id in self.user_buildings.items():
            if user_building_id == building_id and user_id != exclude_user:
                if user_id in self.active_connections:
                    connections_to_remove = []
                    
                    for websocket in self.active_connections[user_id].copy():
                        try:
                            await websocket.send_text(message_json)
                            sent_count += 1
                        except Exception as e:
                            logger.error(f"Error broadcasting to building user {user_id}: {str(e)}")
                            connections_to_remove.append(websocket)
                    
                    # Clean up failed connections
                    for websocket in connections_to_remove:
                        self.disconnect(websocket)
        
        logger.info(f"Broadcast to building {building_id}: {sent_count} messages sent")
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all connected users"""
        message_json = json.dumps(message, default=str)
        sent_count = 0
        
        for user_id in list(self.active_connections.keys()):
            connections_to_remove = []
            
            for websocket in self.active_connections[user_id].copy():
                try:
                    await websocket.send_text(message_json)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
                    connections_to_remove.append(websocket)
            
            # Clean up failed connections
            for websocket in connections_to_remove:
                self.disconnect(websocket)
        
        logger.info(f"Broadcast to all: {sent_count} messages sent")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about active connections"""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        
        role_stats = {}
        building_stats = {}
        
        for user_id, role in self.user_roles.items():
            role_stats[role] = role_stats.get(role, 0) + len(self.active_connections.get(user_id, []))
        
        for user_id, building_id in self.user_buildings.items():
            building_stats[building_id] = building_stats.get(building_id, 0) + len(self.active_connections.get(user_id, []))
        
        return {
            "total_connections": total_connections,
            "total_users": len(self.active_connections),
            "role_breakdown": role_stats,
            "building_breakdown": building_stats,
            "timestamp": datetime.now().isoformat()
        }

class WebSocketNotificationService:
    """Service for sending real-time notifications via WebSocket"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager
    
    async def send_work_order_update(self, work_order_data: Dict[str, Any], notification_type: str):
        """Send work order updates via WebSocket"""
        try:
            message = {
                "type": "work_order_update",
                "notification_type": notification_type,
                "data": work_order_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send to assigned user if specified
            assigned_to = work_order_data.get('assigned_to')
            if assigned_to:
                await self.manager.send_personal_message(assigned_to, message)
            
            # Send to admin users in the building
            building_id = work_order_data.get('building_id')
            if building_id:
                await self.manager.broadcast_to_role('admin', message, building_id)
            
            # Send to the user who reported the issue
            reported_by = work_order_data.get('reported_by')
            if reported_by and reported_by != assigned_to:
                await self.manager.send_personal_message(reported_by, message)
            
            logger.info(f"Work order WebSocket notification sent: {notification_type}")
            
        except Exception as e:
            logger.error(f"Error sending work order WebSocket notification: {str(e)}")
    
    async def send_maintenance_update(self, maintenance_data: Dict[str, Any], notification_type: str):
        """Send maintenance updates via WebSocket"""
        try:
            message = {
                "type": "maintenance_update",
                "notification_type": notification_type,
                "data": maintenance_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send to assigned technician
            assigned_to = maintenance_data.get('assigned_to')
            if assigned_to:
                await self.manager.send_personal_message(assigned_to, message)
            
            # Send to admin users in the building
            building_id = maintenance_data.get('building_id')
            if building_id:
                await self.manager.broadcast_to_role('admin', message, building_id)
                
                # For high priority or overdue tasks, also notify all staff
                priority = maintenance_data.get('priority', 'medium')
                if priority in ['high', 'critical'] or notification_type == 'maintenance_overdue':
                    await self.manager.broadcast_to_role('staff', message, building_id)
            
            logger.info(f"Maintenance WebSocket notification sent: {notification_type}")
            
        except Exception as e:
            logger.error(f"Error sending maintenance WebSocket notification: {str(e)}")
    
    async def send_inventory_update(self, inventory_data: Dict[str, Any], notification_type: str):
        """Send inventory updates via WebSocket"""
        try:
            message = {
                "type": "inventory_update",
                "notification_type": notification_type,
                "data": inventory_data,
                "timestamp": datetime.now().isoformat()
            }
            
            building_id = inventory_data.get('building_id')
            
            if notification_type == 'low_stock_alert':
                # Send to admin and staff users
                if building_id:
                    await self.manager.broadcast_to_role('admin', message, building_id)
                    await self.manager.broadcast_to_role('staff', message, building_id)
            
            elif notification_type in ['inventory_request_approved', 'inventory_request_denied', 'inventory_request_fulfilled']:
                # Send to the requester
                requested_by = inventory_data.get('requested_by')
                if requested_by:
                    await self.manager.send_personal_message(requested_by, message)
            
            elif notification_type == 'inventory_request_created':
                # Send to admin users for approval
                if building_id:
                    await self.manager.broadcast_to_role('admin', message, building_id)
            
            logger.info(f"Inventory WebSocket notification sent: {notification_type}")
            
        except Exception as e:
            logger.error(f"Error sending inventory WebSocket notification: {str(e)}")
    
    async def send_announcement(self, announcement_data: Dict[str, Any]):
        """Send announcement via WebSocket"""
        try:
            message = {
                "type": "announcement",
                "data": announcement_data,
                "timestamp": datetime.now().isoformat()
            }
            
            building_id = announcement_data.get('building_id')
            audience = announcement_data.get('audience', 'all')
            
            if audience == 'all':
                if building_id:
                    await self.manager.broadcast_to_building(building_id, message)
                else:
                    await self.manager.broadcast_to_all(message)
            elif audience in ['admin', 'staff', 'tenant']:
                await self.manager.broadcast_to_role(audience, message, building_id)
            
            logger.info(f"Announcement WebSocket notification sent to {audience}")
            
        except Exception as e:
            logger.error(f"Error sending announcement WebSocket notification: {str(e)}")
    
    async def send_chat_message(self, room_id: str, message_data: Dict[str, Any], participants: List[str]):
        """Send chat message to all participants in a room"""
        try:
            websocket_message = {
                "type": "chat_message",
                "room_id": room_id,
                "data": message_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send to all participants except the sender
            sender_id = message_data.get('sender_id')
            sent_count = 0
            
            for participant_id in participants:
                if participant_id != sender_id:
                    await self.manager.send_personal_message(participant_id, websocket_message)
                    sent_count += 1
            
            logger.info(f"Chat message WebSocket notification sent to {sent_count} participants in room {room_id}")
            
        except Exception as e:
            logger.error(f"Error sending chat message WebSocket notification: {str(e)}")
    
    async def send_chat_room_update(self, room_id: str, update_type: str, participants: List[str], data: Optional[Dict[str, Any]] = None):
        """Send chat room updates (user joined, left, typing, etc.)"""
        try:
            websocket_message = {
                "type": "chat_room_update",
                "update_type": update_type,  # "user_joined", "user_left", "user_typing", "message_read"
                "room_id": room_id,
                "data": data or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Send to all participants
            for participant_id in participants:
                await self.manager.send_personal_message(participant_id, websocket_message)
            
            logger.info(f"Chat room update '{update_type}' sent to room {room_id}")
            
        except Exception as e:
            logger.error(f"Error sending chat room update WebSocket notification: {str(e)}")

# Create global instances
connection_manager = ConnectionManager()
websocket_notification_service = WebSocketNotificationService(connection_manager)

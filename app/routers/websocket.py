from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional
import logging
import json
from datetime import datetime

from ..services.websocket_service import connection_manager, websocket_notification_service
from ..auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

# WebSocket endpoint for real-time notifications
@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="Authentication token"),
    building_id: Optional[str] = Query(None, description="Building ID for filtering")
):
    """WebSocket endpoint for real-time notifications"""
    user_data = None
    
    try:
        # Authenticate user using token (you'll need to implement this)
        user_data = await authenticate_websocket_token(token)
        if not user_data:
            await websocket.close(code=1008, reason="Authentication failed")
            return
        
        user_id = user_data.get('uid')
        user_role = user_data.get('role', 'tenant')
        
        # Connect to WebSocket manager
        await connection_manager.connect(websocket, user_id, user_role, building_id)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                await handle_websocket_message(websocket, user_data, message)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Internal server error",
                    "timestamp": datetime.now().isoformat()
                }))
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        if websocket.client_state.CONNECTED:
            await websocket.close(code=1011, reason="Internal server error")
    
    finally:
        if user_data:
            connection_manager.disconnect(websocket)

async def authenticate_websocket_token(token: str) -> Optional[dict]:
    """Authenticate WebSocket connection using token"""
    try:
        # This is a simplified version - you should implement proper token validation
        # For now, we'll assume token validation and return mock user data
        # In production, integrate with your Firebase auth or JWT validation
        
        if not token or token == "invalid":
            return None
        
        # Mock user data - replace with actual authentication logic
        return {
            "uid": "user123",
            "role": "admin",
            "building_id": "building1"
        }
        
    except Exception as e:
        logger.error(f"Token authentication error: {str(e)}")
        return None

async def handle_websocket_message(websocket: WebSocket, user_data: dict, message: dict):
    """Handle incoming WebSocket messages"""
    try:
        message_type = message.get('type')
        user_id = user_data.get('uid')
        
        if message_type == 'ping':
            # Handle ping/pong for keep-alive
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            }))
        
        elif message_type == 'subscribe':
            # Handle subscription to specific notification types
            notification_types = message.get('notification_types', [])
            await websocket.send_text(json.dumps({
                "type": "subscription_confirmed",
                "notification_types": notification_types,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }))
        
        elif message_type == 'unsubscribe':
            # Handle unsubscription
            await websocket.send_text(json.dumps({
                "type": "unsubscription_confirmed",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }))
        
        elif message_type == 'get_stats':
            # Send connection statistics (admin only)
            if user_data.get('role') == 'admin':
                stats = connection_manager.get_connection_stats()
                await websocket.send_text(json.dumps({
                    "type": "connection_stats",
                    "data": stats
                }))
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Insufficient permissions",
                    "timestamp": datetime.now().isoformat()
                }))
        
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Unknown message type: {message_type}",
                "timestamp": datetime.now().isoformat()
            }))
    
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {str(e)}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Failed to process message", 
            "timestamp": datetime.now().isoformat()
        }))

# REST endpoints for WebSocket management
@router.get("/stats")
async def get_websocket_stats(current_user: dict = Depends(get_current_user)):
    """Get WebSocket connection statistics (admin only)"""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    stats = connection_manager.get_connection_stats()
    return stats

# Simple WebSocket test page
@router.get("/test")
async def get_websocket_test_page():
    """Get a simple HTML page for testing WebSocket connections"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FacilityFix WebSocket Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .messages { height: 400px; border: 1px solid #ccc; padding: 10px; overflow-y: scroll; background: #f9f9f9; }
            .controls { margin: 20px 0; }
            input, button { margin: 5px; padding: 8px; }
            .message { margin: 5px 0; padding: 5px; border-left: 3px solid #007bff; }
            .error { border-left-color: #dc3545; background: #f8d7da; }
            .success { border-left-color: #28a745; background: #d4edda; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏢 FacilityFix WebSocket Test</h1>
            
            <div class="controls">
                <input type="text" id="token" placeholder="Authentication Token" value="test-token">
                <input type="text" id="building_id" placeholder="Building ID (optional)" value="building1">
                <button onclick="connect()">Connect</button>
                <button onclick="disconnect()">Disconnect</button>
                <span id="status">Disconnected</span>
            </div>
            
            <div class="controls">
                <input type="text" id="messageInput" placeholder="Enter message...">
                <button onclick="sendMessage()">Send Message</button>
                <button onclick="sendPing()">Send Ping</button>
                <button onclick="getStats()">Get Stats</button>
            </div>
            
            <div id="messages" class="messages"></div>
        </div>
        
        <script>
            let ws = null;
            const messages = document.getElementById('messages');
            const status = document.getElementById('status');
            
            function addMessage(message, type = 'info') {
                const div = document.createElement('div');
                div.className = `message ${type}`;
                div.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong>: ${message}`;
                messages.appendChild(div);
                messages.scrollTop = messages.scrollHeight;
            }
            
            function connect() {
                const token = document.getElementById('token').value;
                const building_id = document.getElementById('building_id').value;
                
                let wsUrl = `ws://localhost:8001/api/ws/notifications?token=${token}`;
                if (building_id) {
                    wsUrl += `&building_id=${building_id}`;
                }
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function() {
                    status.textContent = 'Connected';
                    status.style.color = 'green';
                    addMessage('Connected to WebSocket', 'success');
                };
                
                ws.onclose = function() {
                    status.textContent = 'Disconnected';
                    status.style.color = 'red';
                    addMessage('Disconnected from WebSocket', 'error');
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addMessage(`Received: ${JSON.stringify(data, null, 2)}`);
                };
                
                ws.onerror = function(error) {
                    addMessage(`Error: ${error}`, 'error');
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                }
            }
            
            function sendMessage() {
                const input = document.getElementById('messageInput');
                if (ws && input.value) {
                    try {
                        const message = JSON.parse(input.value);
                        ws.send(JSON.stringify(message));
                        addMessage(`Sent: ${input.value}`);
                        input.value = '';
                    } catch (e) {
                        addMessage(`Invalid JSON: ${e.message}`, 'error');
                    }
                }
            }
            
            function sendPing() {
                if (ws) {
                    ws.send(JSON.stringify({type: 'ping'}));
                    addMessage('Sent ping');
                }
            }
            
            function getStats() {
                if (ws) {
                    ws.send(JSON.stringify({type: 'get_stats'}));
                    addMessage('Requested connection stats');
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

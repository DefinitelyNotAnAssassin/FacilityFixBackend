"""
Test script for inventory item request workflow
Tests staff requesting items and admin notifications
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

# Mock database for testing
class FakeDB:
    def __init__(self):
        self.inventory_items = {
            "inv_001": {
                "id": "inv_001",
                "name": "Wrench Set",
                "category": "Tools",
                "quantity": 10,
                "unit": "set",
                "location": "Storage A",
                "reorder_point": 3,
                "is_active": True
            },
            "inv_002": {
                "id": "inv_002",
                "name": "Safety Helmet",
                "category": "Safety Equipment",
                "quantity": 5,
                "unit": "piece",
                "location": "Storage B",
                "reorder_point": 5,
                "is_active": True
            }
        }
        
        self.users = {
            "staff_001": {
                "id": "staff_001",
                "name": "John Doe",
                "email": "john@facility.com",
                "role": "staff"
            },
            "admin_001": {
                "id": "admin_001",
                "name": "Admin One",
                "email": "admin1@facility.com",
                "role": "admin"
            },
            "admin_002": {
                "id": "admin_002",
                "name": "Admin Two",
                "email": "admin2@facility.com",
                "role": "admin"
            }
        }
        
        self.inventory_requests = {}
        self.notifications = []
        
    async def get_inventory_item(self, item_id: str) -> Optional[Dict]:
        return self.inventory_items.get(item_id)
    
    async def create_inventory_request(self, request_data: Dict) -> str:
        request_id = f"req_{len(self.inventory_requests) + 1:03d}"
        self.inventory_requests[request_id] = {
            "id": request_id,
            **request_data,
            "created_at": datetime.now(),
            "status": "pending"
        }
        return request_id
    
    async def get_users_by_role(self, role: str) -> List[Dict]:
        return [user for user in self.users.values() if user["role"] == role]
    
    async def create_notification(self, notification_data: Dict) -> str:
        notif_id = f"notif_{len(self.notifications) + 1:03d}"
        self.notifications.append({
            "id": notif_id,
            **notification_data,
            "created_at": datetime.now()
        })
        return notif_id
    
    async def get_user(self, user_id: str) -> Optional[Dict]:
        return self.users.get(user_id)


# Mock services
class MockInventoryService:
    def __init__(self, db: FakeDB):
        self.db = db
    
    async def create_inventory_request(
        self,
        item_id: str,
        requested_by: str,
        quantity: int,
        purpose: str,
        notes: Optional[str] = None
    ) -> str:
        """Create inventory request and notify admins"""
        
        # Get item details
        item = await self.db.get_inventory_item(item_id)
        if not item:
            raise ValueError(f"Inventory item {item_id} not found")
        
        # Get requester details
        requester = await self.db.get_user(requested_by)
        if not requester:
            raise ValueError(f"User {requested_by} not found")
        
        # Create the request
        request_data = {
            "item_id": item_id,
            "item_name": item["name"],
            "requested_by": requested_by,
            "requester_name": requester["name"],
            "quantity": quantity,
            "purpose": purpose,
            "notes": notes
        }
        
        request_id = await self.db.create_inventory_request(request_data)
        
        # Notify all admins
        admins = await self.db.get_users_by_role("admin")
        print(f"\n📝 Created inventory request {request_id}")
        print(f"   Item: {item['name']} x{quantity}")
        print(f"   Requested by: {requester['name']}")
        print(f"   Purpose: {purpose}")
        if notes:
            print(f"   Notes: {notes}")
        
        for admin in admins:
            notification_data = {
                "user_id": admin["id"],
                "type": "INVENTORY_REQUEST_SUBMITTED",
                "priority": "NORMAL",
                "title": f"New Inventory Request: {item['name']}",
                "message": f"{requester['name']} requested {quantity} {item['unit']} of {item['name']} for {purpose}",
                "channels": ["IN_APP", "PUSH"],
                "data": {
                    "request_id": request_id,
                    "item_id": item_id,
                    "item_name": item["name"],
                    "quantity": quantity,
                    "requester_id": requested_by,
                    "requester_name": requester["name"]
                },
                "requires_action": True,
                "action_url": f"/inventory/requests/{request_id}"
            }
            
            notif_id = await self.db.create_notification(notification_data)
            print(f"   ✅ Notified admin: {admin['name']} (notification: {notif_id})")
        
        return request_id


async def test_request_item():
    """Test inventory item request workflow"""
    
    print("=" * 70)
    print("TEST: Inventory Request Workflow")
    print("=" * 70)
    
    # Initialize test environment
    db = FakeDB()
    inventory_service = MockInventoryService(db)
    
    print("\n📦 Initial Inventory State:")
    for item_id, item in db.inventory_items.items():
        print(f"   {item_id}: {item['name']} - Quantity: {item['quantity']} {item['unit']}")
    
    print("\n👥 Users:")
    for user_id, user in db.users.items():
        print(f"   {user_id}: {user['name']} ({user['role']})")
    
    # Test Case 1: Staff requests wrench set
    print("\n" + "=" * 70)
    print("TEST CASE 1: Staff Requests Wrench Set for Maintenance")
    print("=" * 70)
    
    request_id_1 = await inventory_service.create_inventory_request(
        item_id="inv_001",
        requested_by="staff_001",
        quantity=2,
        purpose="Maintenance Task #MT-123",
        notes="Need for HVAC repair in Building A"
    )
    
    print(f"\n✅ Request created: {request_id_1}")
    
    # Verify request details
    request_1 = db.inventory_requests[request_id_1]
    print(f"\n📋 Request Details:")
    print(f"   Status: {request_1['status']}")
    print(f"   Item: {request_1['item_name']}")
    print(f"   Quantity: {request_1['quantity']}")
    print(f"   Requester: {request_1['requester_name']}")
    
    # Verify admin notifications
    admin_notifs_1 = [n for n in db.notifications if n.get('data', {}).get('request_id') == request_id_1]
    print(f"\n📬 Admin Notifications: {len(admin_notifs_1)}")
    for notif in admin_notifs_1:
        print(f"   - To: {db.users[notif['user_id']]['name']}")
        print(f"     Type: {notif['type']}")
        print(f"     Priority: {notif['priority']}")
        print(f"     Channels: {', '.join(notif['channels'])}")
        print(f"     Requires Action: {notif['requires_action']}")
        print(f"     Action URL: {notif.get('action_url', 'N/A')}")
    
    # Test Case 2: Staff requests safety helmets
    print("\n" + "=" * 70)
    print("TEST CASE 2: Staff Requests Safety Helmets")
    print("=" * 70)
    
    request_id_2 = await inventory_service.create_inventory_request(
        item_id="inv_002",
        requested_by="staff_001",
        quantity=3,
        purpose="Construction Project #CP-456",
        notes="Urgent - need by tomorrow"
    )
    
    print(f"\n✅ Request created: {request_id_2}")
    
    # Verify request details
    request_2 = db.inventory_requests[request_id_2]
    print(f"\n📋 Request Details:")
    print(f"   Status: {request_2['status']}")
    print(f"   Item: {request_2['item_name']}")
    print(f"   Quantity: {request_2['quantity']}")
    print(f"   Requester: {request_2['requester_name']}")
    
    # Verify admin notifications
    admin_notifs_2 = [n for n in db.notifications if n.get('data', {}).get('request_id') == request_id_2]
    print(f"\n📬 Admin Notifications: {len(admin_notifs_2)}")
    for notif in admin_notifs_2:
        print(f"   - To: {db.users[notif['user_id']]['name']}")
        print(f"     Type: {notif['type']}")
        print(f"     Priority: {notif['priority']}")
        print(f"     Message: {notif['message']}")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total Requests Created: {len(db.inventory_requests)}")
    print(f"Total Notifications Sent: {len(db.notifications)}")
    print(f"Total Admins Notified: {len(db.users_by_role('admin')) if hasattr(db, 'users_by_role') else 2}")
    
    print("\n✅ All tests completed successfully!")
    
    # Assertions
    assert len(db.inventory_requests) == 2, "Should have 2 requests"
    assert len(db.notifications) == 4, "Should have 4 notifications (2 requests × 2 admins)"
    
    for notif in db.notifications:
        assert notif['type'] == "INVENTORY_REQUEST_SUBMITTED", "Notification type should be INVENTORY_REQUEST_SUBMITTED"
        assert notif['priority'] == "NORMAL", "Priority should be NORMAL"
        assert "IN_APP" in notif['channels'], "Should include IN_APP channel"
        assert "PUSH" in notif['channels'], "Should include PUSH channel"
        assert notif['requires_action'] == True, "Should require admin action"
        assert notif.get('action_url'), "Should have action URL"
    
    print("\n✅ All assertions passed!")


if __name__ == "__main__":
    asyncio.run(test_request_item())

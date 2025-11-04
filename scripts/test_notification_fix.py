#!/usr/bin/env python3
"""
Quick test for concern slip notifications
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.notification_manager import NotificationManager
from app.models.notification_models import NotificationType

async def test_notifications():
    """Test concern slip notifications"""
    
    print("🧪 Testing Concern Slip Notifications")
    print("=" * 40)
    
    try:
        manager = NotificationManager()
        
        print("1. Testing basic notification creation...")
        success, notif_id, error = await manager.create_notification(
            notification_type=NotificationType.CONCERN_SLIP_SUBMITTED,
            recipient_id='test_admin_123',
            title='Test Notification',
            message='This is a test notification',
            related_entity_type='concern_slip',
            related_entity_id='CS-TEST-001'
        )
        
        print(f"   Result: Success={success}, ID={notif_id}, Error={error}")
        
        if success:
            print("✅ Basic notification creation successful")
        else:
            print(f"❌ Basic notification creation failed: {error}")
            return
        
        print("\n2. Testing concern slip submission notification...")
        await manager.notify_concern_slip_submitted(
            concern_slip_id='CS-TEST-002',
            title='Test leaky faucet',
            reported_by='test_tenant_456',
            category='plumbing',
            priority='medium',
            location='Unit 301 - Kitchen'
        )
        print("✅ Concern slip submission notification sent")
        
        print("\n3. Testing staff assignment notification...")
        await manager.notify_concern_slip_assigned(
            concern_slip_id='CS-TEST-002',
            title='Test leaky faucet',
            staff_id='test_staff_789',
            assigned_by='test_admin_123',
            category='plumbing',
            priority='medium',
            location='Unit 301 - Kitchen'
        )
        print("✅ Staff assignment notification sent")
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_notifications())
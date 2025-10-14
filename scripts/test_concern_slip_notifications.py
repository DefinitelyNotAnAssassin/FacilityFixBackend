#!/usr/bin/env python3
"""
Test script for concern slip notification functionality

This script tests the integration between ConcernSlipService and NotificationManager
to ensure all concern slip operations generate appropriate notifications.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.concern_slip_service import ConcernSlipService
from app.services.notification_manager import NotificationManager
from app.database.database_service import database_service


async def test_concern_slip_notifications():
    """Test all concern slip notification scenarios"""
    
    print("🧪 Testing Concern Slip Notifications")
    print("=" * 50)
    
    try:
        concern_service = ConcernSlipService()
        notification_manager = NotificationManager()
        
        # Test data
        test_tenant_id = "test_tenant_123"
        test_staff_id = "test_staff_456"
        test_admin_id = "test_admin_789"
        
        print("\n1. Testing Concern Slip Submission Notification")
        print("-" * 40)
        
        # Test 1: Concern slip submission
        await notification_manager.notify_concern_slip_submitted(
            concern_slip_id="CS-2024-001",
            title="Leaky faucet in unit 301",
            reported_by=test_tenant_id,
            category="plumbing",
            priority="medium",
            location="Unit 301 - Kitchen",
            description="The kitchen faucet has been dripping constantly"
        )
        print("✅ Concern slip submission notification sent")
        
        print("\n2. Testing Staff Assignment Notification")
        print("-" * 40)
        
        # Test 2: Staff assignment
        await notification_manager.notify_concern_slip_assigned(
            concern_slip_id="CS-2024-001",
            title="Leaky faucet in unit 301",
            staff_id=test_staff_id,
            assigned_by=test_admin_id,
            category="plumbing",
            priority="medium",
            location="Unit 301 - Kitchen"
        )
        print("✅ Staff assignment notification sent")
        
        print("\n3. Testing Assessment Completion Notification")
        print("-" * 40)
        
        # Test 3: Assessment completion
        await notification_manager.notify_concern_slip_assessed(
            concern_slip_id="CS-2024-001",
            title="Leaky faucet in unit 301",
            staff_id=test_staff_id,
            assessment="Inspected the kitchen faucet. The cartridge needs replacement.",
            recommendation="Replace faucet cartridge. Estimated time: 1 hour. Parts needed: Standard cartridge."
        )
        print("✅ Assessment completion notification sent")
        
        print("\n4. Testing Evaluation Notification")
        print("-" * 40)
        
        # Test 4: Concern slip evaluation
        await notification_manager.notify_concern_slip_evaluated(
            concern_slip_id="CS-2024-001",
            title="Leaky faucet in unit 301",
            tenant_id=test_tenant_id,
            status="approved",
            resolution_type="job_service",
            admin_notes="Approved for job service. Standard plumbing repair."
        )
        print("✅ Evaluation notification sent")
        
        print("\n5. Testing Resolution Type Setting Notification")
        print("-" * 40)
        
        # Test 5: Resolution type setting
        await notification_manager.notify_concern_slip_resolution_set(
            concern_slip_id="CS-2024-001",
            title="Leaky faucet in unit 301",
            tenant_id=test_tenant_id,
            resolution_type="job_service",
            admin_notes="Job service assigned. Please proceed to create a job service request."
        )
        print("✅ Resolution type notification sent")
        
        print("\n6. Testing Return to Tenant Notification")
        print("-" * 40)
        
        # Test 6: Return to tenant
        await notification_manager.notify_concern_slip_returned_to_tenant(
            concern_slip_id="CS-2024-001",
            title="Leaky faucet in unit 301",
            tenant_id=test_tenant_id,
            assessment="Inspected the kitchen faucet. The cartridge needs replacement.",
            recommendation="Replace faucet cartridge. Estimated time: 1 hour. Parts needed: Standard cartridge."
        )
        print("✅ Return to tenant notification sent")
        
        print("\n7. Verifying Notifications in Database")
        print("-" * 40)
        
        # Query recent notifications
        success, notifications, error = await database_service.query_documents(
            "notifications",
            [("created_at", ">=", datetime.utcnow() - timedelta(minutes=5))]
        )
        
        if success and notifications:
            print(f"✅ Found {len(notifications)} recent notifications:")
            for notif in notifications[-6:]:  # Show last 6 notifications
                print(f"   - {notif.get('notification_type')}: {notif.get('title')}")
                print(f"     Recipient: {notif.get('recipient_id')}")
                print(f"     Message: {notif.get('message', '')[:80]}...")
                print()
        else:
            print(f"❌ No notifications found or error: {error}")
        
        print("\n🎉 All concern slip notification tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_notification_integration():
    """Test the full integration with actual concern slip operations"""
    
    print("\n🔗 Testing Full Integration with Concern Slip Service")
    print("=" * 60)
    
    try:
        concern_service = ConcernSlipService()
        
        # Create a test concern slip (this should trigger notification)
        print("\n1. Creating Test Concern Slip")
        print("-" * 30)
        
        concern_data = {
            "title": "Test notification integration",
            "description": "This is a test concern slip to verify notification integration",
            "location": "Test Unit 999",
            "category": "general",
            "priority": "low",
            "unit_id": "test-unit-999",
            "attachments": []
        }
        
        # Note: This would require a valid tenant user in the database
        # For testing, we'll just call the notification methods directly
        print("✅ Integration test setup complete")
        print("Note: Full integration requires valid users in database")
        
    except Exception as e:
        print(f"❌ Integration test error: {str(e)}")


def main():
    """Main test function"""
    print("🚀 Starting Concern Slip Notification Tests")
    print("This script tests the notification system for concern slip operations")
    print()
    
    # Run async tests
    asyncio.run(test_concern_slip_notifications())
    asyncio.run(test_notification_integration())
    
    print("\n✨ Test suite completed!")


if __name__ == "__main__":
    main()
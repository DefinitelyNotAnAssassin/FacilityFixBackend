"""
Notification Integration Helper

This script demonstrates how to integrate the new notification manager
into existing services and provides examples for testing the notification system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from app.services.notification_manager import notification_manager
from app.models.notification_models import NotificationType, NotificationPriority, NotificationChannel

logger = logging.getLogger(__name__)


class NotificationIntegrationHelper:
    """Helper class for integrating notifications into existing services"""
    
    def __init__(self):
        self.manager = notification_manager
    
    # ═══════════════════════════════════════════════════════════════════════════
    # INTEGRATION EXAMPLES FOR EXISTING SERVICES
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def integrate_concern_slip_service(self):
        """Example integration for concern slip service"""
        print("=== Concern Slip Service Integration Examples ===")
        
        # Replace existing notification calls with new manager calls
        concern_slip_examples = [
            {
                "method": "create_concern_slip",
                "old_code": """
                await self._send_admin_notification(
                    concern_slip_id, 
                    "New concern slip submitted"
                )
                """,
                "new_code": """
                await notification_manager.create_notification(
                    notification_type=NotificationType.CONCERN_SLIP_SUBMITTED,
                    recipient_id="admin",  # Will send to all admins
                    title="New Concern Slip Submitted",
                    message=f"New concern slip: {title} at {location}",
                    related_entity_type="concern_slip",
                    related_entity_id=concern_slip_id,
                    building_id=building_id,
                    priority=NotificationPriority.HIGH,
                    requires_action=True
                )
                """
            },
            {
                "method": "assign_staff_to_concern_slip",
                "old_code": """
                await self._send_staff_notification(
                    staff_id,
                    concern_slip_id,
                    "You have been assigned a concern slip"
                )
                """,
                "new_code": """
                await notification_manager.create_notification(
                    notification_type=NotificationType.CONCERN_SLIP_ASSIGNED,
                    recipient_id=staff_id,
                    title="Concern Slip Assigned",
                    message=f"You have been assigned to assess: {title}",
                    sender_id=assigned_by,
                    related_entity_type="concern_slip",
                    related_entity_id=concern_slip_id,
                    priority=NotificationPriority.HIGH,
                    requires_action=True
                )
                """
            }
        ]
        
        for example in concern_slip_examples:
            print(f"\n{example['method']}:")
            print("OLD CODE:", example['old_code'])
            print("NEW CODE:", example['new_code'])
    
    async def integrate_job_service_service(self):
        """Example integration for job service service"""
        print("\n=== Job Service Service Integration Examples ===")
        
        job_service_examples = [
            {
                "method": "assign_job_service",
                "new_code": """
                await notification_manager.notify_job_service_received(
                    job_service_id=job_service_id,
                    staff_id=assigned_to,
                    tenant_id=requester_id,
                    title=job_title,
                    location=location
                )
                """
            },
            {
                "method": "complete_job_service",
                "new_code": """
                await notification_manager.notify_job_service_completed(
                    job_service_id=job_service_id,
                    staff_id=completed_by,
                    tenant_id=requester_id,
                    title=job_title,
                    completion_notes=completion_notes
                )
                """
            }
        ]
        
        for example in job_service_examples:
            print(f"\n{example['method']}:")
            print("NEW CODE:", example['new_code'])
    
    async def integrate_maintenance_service(self):
        """Example integration for maintenance service"""
        print("\n=== Maintenance Service Integration Examples ===")
        
        maintenance_examples = [
            {
                "method": "assign_maintenance_task",
                "new_code": """
                await notification_manager.notify_maintenance_task_assigned(
                    task_id=task_id,
                    staff_id=assigned_to,
                    task_title=task_title,
                    location=location,
                    scheduled_date=scheduled_date,
                    assigned_by=assigned_by
                )
                """
            },
            {
                "method": "check_overdue_tasks",
                "new_code": """
                for overdue_task in overdue_tasks:
                    days_overdue = (datetime.utcnow() - overdue_task['scheduled_date']).days
                    await notification_manager.notify_maintenance_overdue(
                        task_id=overdue_task['id'],
                        staff_id=overdue_task['assigned_to'],
                        manager_id=overdue_task.get('manager_id'),
                        task_title=overdue_task['title'],
                        location=overdue_task['location'],
                        days_overdue=days_overdue
                    )
                """
            }
        ]
        
        for example in maintenance_examples:
            print(f"\n{example['method']}:")
            print("NEW CODE:", example['new_code'])
    
    async def integrate_inventory_service(self):
        """Example integration for inventory service"""
        print("\n=== Inventory Service Integration Examples ===")
        
        inventory_examples = [
            {
                "method": "check_stock_levels",
                "new_code": """
                for item in low_stock_items:
                    await notification_manager.notify_inventory_low_stock(
                        inventory_id=item['id'],
                        item_name=item['name'],
                        current_stock=item['current_stock'],
                        reorder_level=item['reorder_level'],
                        building_id=item['building_id'],
                        department=item['department'],
                        is_critical=(item['current_stock'] <= item['critical_level'])
                    )
                """
            },
            {
                "method": "restock_item",
                "new_code": """
                await notification_manager.notify_inventory_restocked(
                    inventory_id=inventory_id,
                    item_name=item_name,
                    new_stock_level=new_stock_level,
                    restocked_by=restocked_by,
                    building_id=building_id,
                    waiting_requesters=waiting_requesters
                )
                """
            }
        ]
        
        for example in inventory_examples:
            print(f"\n{example['method']}:")
            print("NEW CODE:", example['new_code'])
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEST NOTIFICATION SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def test_work_order_workflow(self, work_order_id: str, tenant_id: str, staff_id: str, admin_id: str):
        """Test complete work order notification workflow"""
        print("\n=== Testing Work Order Workflow ===")
        
        try:
            # 1. Work order submitted
            print("1. Sending work order submitted notifications...")
            await self.manager.notify_work_order_submitted(
                work_order_id=work_order_id,
                requester_id=tenant_id,
                building_id="building_001",
                location="Unit 101 - Kitchen"
            )
            
            # 2. Work order assigned
            print("2. Sending work order assigned notifications...")
            await self.manager.notify_work_order_assigned(
                work_order_id=work_order_id,
                assignee_id=staff_id,
                requester_id=tenant_id,
                assigned_by=admin_id,
                location="Unit 101 - Kitchen",
                scheduled_date=datetime.utcnow() + timedelta(days=1)
            )
            
            # 3. Schedule updated
            print("3. Sending schedule update notifications...")
            await self.manager.notify_work_order_schedule_updated(
                work_order_id=work_order_id,
                assignee_id=staff_id,
                requester_id=tenant_id,
                new_schedule=datetime.utcnow() + timedelta(days=2),
                location="Unit 101 - Kitchen",
                reason="Technician availability changed"
            )
            
            print("✅ Work order workflow notifications sent successfully!")
            
        except Exception as e:
            print(f"❌ Error in work order workflow: {str(e)}")
    
    async def test_permit_workflow(self, permit_id: str, tenant_id: str, admin_id: str):
        """Test complete permit notification workflow"""
        print("\n=== Testing Permit Workflow ===")
        
        try:
            # 1. Permit created
            print("1. Sending permit created notification...")
            await self.manager.notify_permit_created(
                permit_id=permit_id,
                requester_id=tenant_id,
                contractor_name="ABC Plumbing Co.",
                work_description="Replace bathroom fixtures"
            )
            
            # 2. Permit approved
            print("2. Sending permit approved notification...")
            await self.manager.notify_permit_approved(
                permit_id=permit_id,
                requester_id=tenant_id,
                assignee_id=None,
                approved_by=admin_id,
                contractor_name="ABC Plumbing Co.",
                conditions="Work must be completed between 9 AM and 5 PM"
            )
            
            # 3. Permit expiring
            print("3. Sending permit expiring notification...")
            await self.manager.notify_permit_expiring(
                permit_id=permit_id,
                requester_id=tenant_id,
                contractor_name="ABC Plumbing Co.",
                expires_at=datetime.utcnow() + timedelta(days=3),
                days_until_expiry=3
            )
            
            print("✅ Permit workflow notifications sent successfully!")
            
        except Exception as e:
            print(f"❌ Error in permit workflow: {str(e)}")
    
    async def test_maintenance_workflow(self, task_id: str, staff_id: str, admin_id: str):
        """Test maintenance task notification workflow"""
        print("\n=== Testing Maintenance Workflow ===")
        
        try:
            # 1. Task assigned
            print("1. Sending maintenance task assigned notification...")
            await self.manager.notify_maintenance_task_assigned(
                task_id=task_id,
                staff_id=staff_id,
                task_title="HVAC Filter Replacement",
                location="Building A - Roof",
                scheduled_date=datetime.utcnow() + timedelta(days=1),
                assigned_by=admin_id
            )
            
            # 2. Task overdue
            print("2. Sending maintenance overdue notification...")
            await self.manager.notify_maintenance_overdue(
                task_id=task_id,
                staff_id=staff_id,
                manager_id=admin_id,
                task_title="HVAC Filter Replacement",
                location="Building A - Roof",
                days_overdue=2
            )
            
            # 3. Task completed
            print("3. Sending maintenance completed notification...")
            await self.manager.notify_maintenance_completed(
                task_id=task_id,
                completed_by=staff_id,
                task_title="HVAC Filter Replacement",
                location="Building A - Roof",
                completion_notes="Filter replaced successfully. System running normally."
            )
            
            print("✅ Maintenance workflow notifications sent successfully!")
            
        except Exception as e:
            print(f"❌ Error in maintenance workflow: {str(e)}")
    
    async def test_inventory_workflow(self, inventory_id: str, admin_id: str, requester_id: str):
        """Test inventory notification workflow"""
        print("\n=== Testing Inventory Workflow ===")
        
        try:
            # 1. Low stock alert
            print("1. Sending low stock notification...")
            await self.manager.notify_inventory_low_stock(
                inventory_id=inventory_id,
                item_name="Toilet Paper - Industrial",
                current_stock=5,
                reorder_level=20,
                building_id="building_001",
                department="maintenance",
                is_critical=True
            )
            
            # 2. Inventory request submitted
            print("2. Sending inventory request notification...")
            await self.manager.notify_inventory_request_submitted(
                request_id="req_001",
                requester_id=requester_id,
                item_name="Toilet Paper - Industrial",
                quantity=50,
                purpose="Restock common area restrooms"
            )
            
            # 3. Item restocked
            print("3. Sending restocked notification...")
            await self.manager.notify_inventory_restocked(
                inventory_id=inventory_id,
                item_name="Toilet Paper - Industrial",
                new_stock_level=100,
                restocked_by=admin_id,
                building_id="building_001",
                waiting_requesters=[requester_id]
            )
            
            print("✅ Inventory workflow notifications sent successfully!")
            
        except Exception as e:
            print(f"❌ Error in inventory workflow: {str(e)}")
    
    async def test_announcement_workflow(self, announcement_id: str, building_id: str):
        """Test announcement notification workflow"""
        print("\n=== Testing Announcement Workflow ===")
        
        try:
            # 1. New announcement
            print("1. Sending announcement published notification...")
            await self.manager.notify_announcement_published(
                announcement_id=announcement_id,
                title="Scheduled Maintenance - Water System",
                content="The water system will be temporarily shut off tomorrow from 9 AM to 2 PM for routine maintenance. Please plan accordingly.",
                target_audience="all",
                target_roles=["tenant", "staff"],
                building_id=building_id,
                priority="high",
                announcement_type="maintenance"
            )
            
            # 2. Reminder
            print("2. Sending announcement reminder...")
            await self.manager.notify_announcement_reminder(
                announcement_id=announcement_id,
                title="Water System Maintenance",
                event_time=datetime.utcnow() + timedelta(hours=2),
                target_recipients=["tenant_001", "tenant_002", "staff_001"],
                hours_before=2
            )
            
            print("✅ Announcement workflow notifications sent successfully!")
            
        except Exception as e:
            print(f"❌ Error in announcement workflow: {str(e)}")
    
    async def test_user_management_workflow(self, new_user_id: str, admin_id: str):
        """Test user management notification workflow"""
        print("\n=== Testing User Management Workflow ===")
        
        try:
            # 1. User invited
            print("1. Sending user invited notification...")
            await self.manager.notify_user_invited(
                user_id=new_user_id,
                invited_by=admin_id,
                role="tenant",
                building_name="Sunset Apartments"
            )
            
            # 2. User approved
            print("2. Sending user approved notification...")
            await self.manager.notify_user_approved(
                user_id=new_user_id,
                approved_by=admin_id,
                role="tenant"
            )
            
            print("✅ User management workflow notifications sent successfully!")
            
        except Exception as e:
            print(f"❌ Error in user management workflow: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def run_all_tests(self):
        """Run all test workflows"""
        print("🚀 Starting Notification Manager Integration Tests")
        print("=" * 60)
        
        # Show integration examples
        await self.integrate_concern_slip_service()
        await self.integrate_job_service_service()
        await self.integrate_maintenance_service()
        await self.integrate_inventory_service()
        
        # Test sample IDs (replace with actual IDs in production)
        sample_ids = {
            "work_order_id": "wo_001",
            "permit_id": "permit_001",
            "task_id": "task_001",
            "inventory_id": "inv_001",
            "announcement_id": "ann_001",
            "tenant_id": "tenant_001",
            "staff_id": "staff_001",
            "admin_id": "admin_001",
            "building_id": "building_001"
        }
        
        # Run test workflows
        await self.test_work_order_workflow(
            sample_ids["work_order_id"], 
            sample_ids["tenant_id"], 
            sample_ids["staff_id"], 
            sample_ids["admin_id"]
        )
        
        await self.test_permit_workflow(
            sample_ids["permit_id"], 
            sample_ids["tenant_id"], 
            sample_ids["admin_id"]
        )
        
        await self.test_maintenance_workflow(
            sample_ids["task_id"], 
            sample_ids["staff_id"], 
            sample_ids["admin_id"]
        )
        
        await self.test_inventory_workflow(
            sample_ids["inventory_id"], 
            sample_ids["admin_id"], 
            sample_ids["staff_id"]
        )
        
        await self.test_announcement_workflow(
            sample_ids["announcement_id"], 
            sample_ids["building_id"]
        )
        
        await self.test_user_management_workflow(
            "new_user_001", 
            sample_ids["admin_id"]
        )
        
        print("\n" + "=" * 60)
        print("✅ All notification tests completed!")
        print("Check the notifications collection in your database to see the results.")


async def main():
    """Main function to run the integration helper"""
    helper = NotificationIntegrationHelper()
    await helper.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
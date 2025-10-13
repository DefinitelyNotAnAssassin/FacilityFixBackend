"""
Setup instructions for integrating the comprehensive notification system
into the FacilityFix application.

This file contains the necessary steps and code changes to fully integrate
the notification manager into your existing application.
"""

# ═══════════════════════════════════════════════════════════════════════════
# 1. UPDATE MAIN APPLICATION FILE (main.py)
# ═══════════════════════════════════════════════════════════════════════════

MAIN_PY_UPDATES = """
# Add to your imports in main.py:
from app.routers import notifications

# Add to your router includes:
app.include_router(notifications.router)

# Or if you're already including it, make sure it's using the updated version
"""

# ═══════════════════════════════════════════════════════════════════════════
# 2. UPDATE DATABASE MODELS (database_models.py)
# ═══════════════════════════════════════════════════════════════════════════

DATABASE_MODELS_UPDATES = """
# Add the enhanced notification models to your database_models.py:

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enhanced Notification Model (replace existing Notification model)
class Notification(BaseModel):
    id: Optional[str] = None
    notification_type: str  # Use NotificationType enum values
    
    # Recipients and targeting
    recipient_id: str  # Primary recipient user ID
    recipient_ids: Optional[List[str]] = []  # Multiple recipients for group notifications
    sender_id: Optional[str] = None  # User ID of sender, or "system" for automated
    
    # Content
    title: str
    message: str
    description: Optional[str] = None  # Longer description if needed
    
    # Metadata
    related_entity_type: Optional[str] = None  # e.g., "work_order", "concern_slip", "inventory_item"
    related_entity_id: Optional[str] = None   # ID of the related entity
    building_id: Optional[str] = None         # Building context if applicable
    department: Optional[str] = None          # Department context if applicable
    
    # Priority and urgency
    priority: str = "normal"  # low, normal, high, urgent, critical
    is_urgent: bool = Field(default=False)
    expires_at: Optional[datetime] = None     # Auto-expire notification
    
    # Delivery settings
    channels: List[str] = Field(default=["in_app"])  # in_app, push, email, sms, websocket
    delivery_status: str = "pending"  # pending, sent, delivered, read, failed, expired
    
    # Tracking
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_reason: Optional[str] = None
    
    # Action tracking
    action_url: Optional[str] = None          # Deep link to relevant page
    action_label: Optional[str] = None        # CTA button text
    requires_action: bool = Field(default=False)  # Requires user action
    action_taken: bool = Field(default=False)
    action_taken_at: Optional[datetime] = None
    
    # Additional metadata
    custom_data: Optional[Dict[str, Any]] = {}  # Flexible additional data
    tags: Optional[List[str]] = []              # Searchable tags
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Grouping (for batching similar notifications)
    group_key: Optional[str] = None           # Group related notifications
    batch_id: Optional[str] = None            # Batch processing ID
"""

# ═══════════════════════════════════════════════════════════════════════════
# 3. UPDATE EXISTING SERVICES
# ═══════════════════════════════════════════════════════════════════════════

SERVICE_INTEGRATION_EXAMPLES = {
    "concern_slip_service.py": """
# Add import at the top:
from app.services.notification_manager import notification_manager
from app.models.notification_models import NotificationType

# Replace existing notification calls in create_concern_slip method:
# OLD:
# await self._send_admin_notification(concern_slip_id, "New concern slip submitted")

# NEW:
await notification_manager.create_notification(
    notification_type=NotificationType.CONCERN_SLIP_SUBMITTED,
    recipient_id="admin",  # Will send to all admins
    title="New Concern Slip Submitted",
    message=f"New concern slip: {concern_data['title']} at {concern_data['location']}",
    related_entity_type="concern_slip",
    related_entity_id=concern_slip_id,
    building_id=concern_data.get('building_id'),
    priority=NotificationPriority.HIGH,
    requires_action=True
)

# Replace in assign_staff_to_concern_slip method:
# OLD:
# await self._send_staff_notification(staff_id, concern_slip_id, "You have been assigned")

# NEW:
await notification_manager.create_notification(
    notification_type=NotificationType.CONCERN_SLIP_ASSIGNED,
    recipient_id=assigned_to,
    title="Concern Slip Assigned",
    message=f"You have been assigned to assess: {concern_slip['title']}",
    sender_id=assigned_by,
    related_entity_type="concern_slip",
    related_entity_id=concern_slip_id,
    priority=NotificationPriority.HIGH,
    requires_action=True
)
""",

    "job_service_service.py": """
# Add import at the top:
from app.services.notification_manager import notification_manager

# In assign_job_service method:
await notification_manager.notify_job_service_received(
    job_service_id=job_service_id,
    staff_id=assigned_to,
    tenant_id=job_service.reported_by,
    title=job_service.title,
    location=job_service.location
)

# In complete_job_service method:
await notification_manager.notify_job_service_completed(
    job_service_id=job_service_id,
    staff_id=completed_by,
    tenant_id=job_service.reported_by,
    title=job_service.title,
    completion_notes=completion_notes
)
""",

    "maintenance_task_service.py": """
# Add import at the top:
from app.services.notification_manager import notification_manager

# In assign_task method:
await notification_manager.notify_maintenance_task_assigned(
    task_id=task_id,
    staff_id=assigned_to,
    task_title=task_data['task_title'],
    location=task_data['location'],
    scheduled_date=task_data.get('scheduled_date'),
    assigned_by=current_user_id
)

# In check_overdue_tasks method (create this as a scheduled task):
for task in overdue_tasks:
    days_overdue = (datetime.utcnow() - task['scheduled_date']).days
    await notification_manager.notify_maintenance_overdue(
        task_id=task['id'],
        staff_id=task['assigned_to'],
        manager_id=task.get('manager_id'),
        task_title=task['task_title'],
        location=task['location'],
        days_overdue=days_overdue
    )

# In complete_task method:
await notification_manager.notify_maintenance_completed(
    task_id=task_id,
    completed_by=completed_by,
    task_title=task['task_title'],
    location=task['location'],
    completion_notes=completion_notes
)
""",

    "inventory_service.py": """
# Add import at the top:
from app.services.notification_manager import notification_manager

# In check_stock_levels method (create as scheduled task):
for item in low_stock_items:
    await notification_manager.notify_inventory_low_stock(
        inventory_id=item['id'],
        item_name=item['item_name'],
        current_stock=item['current_stock'],
        reorder_level=item['reorder_level'],
        building_id=item['building_id'],
        department=item['department'],
        is_critical=(item['current_stock'] <= item.get('critical_level', 0))
    )

# In restock_item method:
await notification_manager.notify_inventory_restocked(
    inventory_id=inventory_id,
    item_name=item_name,
    new_stock_level=new_stock_level,
    restocked_by=restocked_by,
    building_id=building_id,
    waiting_requesters=pending_requesters
)

# In create_inventory_request method:
await notification_manager.notify_inventory_request_submitted(
    request_id=request_id,
    requester_id=requester_id,
    item_name=item_name,
    quantity=quantity,
    purpose=purpose
)
""",

    "announcement_service.py": """
# Add import at the top:
from app.services.notification_manager import notification_manager

# In create_announcement method:
if should_send_notifications:
    await notification_manager.notify_announcement_published(
        announcement_id=announcement_id,
        title=announcement_data['title'],
        content=announcement_data['content'],
        target_audience=announcement_data.get('audience', 'all'),
        target_roles=announcement_data.get('target_roles'),
        target_departments=announcement_data.get('target_departments'),
        target_user_ids=announcement_data.get('target_user_ids'),
        building_id=announcement_data.get('building_id'),
        priority=announcement_data.get('priority_level', 'normal'),
        announcement_type=announcement_data.get('type', 'general')
    )

# Create a scheduled task for event reminders:
# In a scheduled task runner:
for announcement in upcoming_events:
    hours_before = 2  # or 4 hours for maintenance
    if announcement['scheduled_publish_date'] - datetime.utcnow() <= timedelta(hours=hours_before):
        await notification_manager.notify_announcement_reminder(
            announcement_id=announcement['id'],
            title=announcement['title'],
            event_time=announcement['scheduled_publish_date'],
            target_recipients=announcement['target_recipients'],
            hours_before=hours_before
        )
"""
}

# ═══════════════════════════════════════════════════════════════════════════
# 4. CREATE SCHEDULED TASKS FOR AUTOMATED NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════

SCHEDULED_TASKS_EXAMPLE = """
# Create a new file: app/tasks/notification_tasks.py

import asyncio
from datetime import datetime, timedelta
from app.services.notification_manager import notification_manager
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS

async def check_overdue_maintenance_tasks():
    '''Check for overdue maintenance tasks and send notifications'''
    try:
        # Get all maintenance tasks
        success, tasks, error = await database_service.query_documents(
            COLLECTIONS['maintenance_tasks'],
            filters=[('status', 'in', ['assigned', 'in_progress'])]
        )
        
        if not success:
            return
        
        current_time = datetime.utcnow()
        
        for task in tasks:
            scheduled_date = task.get('scheduled_date')
            if scheduled_date and scheduled_date < current_time:
                days_overdue = (current_time - scheduled_date).days
                
                if days_overdue > 0:  # Only notify if actually overdue
                    await notification_manager.notify_maintenance_overdue(
                        task_id=task['id'],
                        staff_id=task['assigned_to'],
                        manager_id=task.get('manager_id'),
                        task_title=task['task_title'],
                        location=task['location'],
                        days_overdue=days_overdue
                    )
    except Exception as e:
        print(f"Error checking overdue tasks: {e}")

async def check_expiring_permits():
    '''Check for permits expiring soon and send notifications'''
    try:
        # Get all active permits
        success, permits, error = await database_service.query_documents(
            COLLECTIONS['work_order_permits'],
            filters=[('status', '==', 'approved')]
        )
        
        if not success:
            return
        
        current_time = datetime.utcnow()
        warning_threshold = timedelta(days=3)  # Warn 3 days before expiry
        
        for permit in permits:
            expires_at = permit.get('expires_at')
            if expires_at:
                time_until_expiry = expires_at - current_time
                
                if timedelta(0) < time_until_expiry <= warning_threshold:
                    days_until_expiry = time_until_expiry.days
                    await notification_manager.notify_permit_expiring(
                        permit_id=permit['id'],
                        requester_id=permit['requested_by'],
                        contractor_name=permit['contractor_name'],
                        expires_at=expires_at,
                        days_until_expiry=days_until_expiry
                    )
    except Exception as e:
        print(f"Error checking expiring permits: {e}")

async def check_low_stock_items():
    '''Check for low stock items and send notifications'''
    try:
        # Get all inventory items
        success, items, error = await database_service.query_documents(
            COLLECTIONS['inventory'],
            filters=[('is_active', '==', True)]
        )
        
        if not success:
            return
        
        for item in items:
            current_stock = item.get('current_stock', 0)
            reorder_level = item.get('reorder_level', 0)
            critical_level = item.get('critical_level', 0)
            
            if current_stock <= reorder_level:
                await notification_manager.notify_inventory_low_stock(
                    inventory_id=item['id'],
                    item_name=item['item_name'],
                    current_stock=current_stock,
                    reorder_level=reorder_level,
                    building_id=item['building_id'],
                    department=item['department'],
                    is_critical=(current_stock <= critical_level)
                )
    except Exception as e:
        print(f"Error checking low stock: {e}")

# Run these tasks periodically (e.g., using APScheduler or similar)
# Example using APScheduler:
'''
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Check overdue tasks every hour
scheduler.add_job(check_overdue_maintenance_tasks, 'interval', hours=1)

# Check expiring permits daily at 9 AM
scheduler.add_job(check_expiring_permits, 'cron', hour=9)

# Check low stock every 6 hours
scheduler.add_job(check_low_stock_items, 'interval', hours=6)

scheduler.start()
'''
"""

# ═══════════════════════════════════════════════════════════════════════════
# 5. FRONTEND INTEGRATION NOTES
# ═══════════════════════════════════════════════════════════════════════════

FRONTEND_INTEGRATION_NOTES = """
# Frontend Integration Notes

## 1. Update Notification API Calls
Replace existing notification API calls with the new enhanced endpoints:

// Get user notifications with filtering
GET /api/notifications?unread_only=true&limit=20&notification_type=work_order_assigned

// Get unread count for badge
GET /api/notifications/unread-count

// Mark notifications as read
PATCH /api/notifications/mark-read
{
  "notification_ids": ["notif_001", "notif_002"]
}

// Mark all as read
PATCH /api/notifications/mark-all-read

## 2. Enhanced Notification Display
The new notification model includes:
- action_url: Direct link to relevant page
- action_label: Button text (e.g., "View Work Order")
- priority: For styling (urgent = red, high = orange, etc.)
- expires_at: Auto-hide expired notifications
- requires_action: Show action button
- custom_data: Additional metadata for rendering

## 3. Real-time Updates
Consider implementing WebSocket connections for real-time notifications:
- Connect to /ws/notifications endpoint
- Listen for new notification events
- Update UI badges and notification panels in real-time

## 4. Notification Grouping
Use group_key to group related notifications:
- "maintenance_overdue_task_123" - Group all overdue reminders for same task
- "permit_expiring_permit_456" - Group permit expiration reminders

## 5. Rich Notification Content
Display notifications with:
- Proper icons based on notification_type
- Color coding based on priority
- Action buttons when requires_action is true
- Timestamp formatting with "time ago" display
"""

def print_setup_instructions():
    """Print comprehensive setup instructions"""
    print("🚀 FacilityFix Notification System Integration Guide")
    print("=" * 60)
    
    print("\n1. MAIN APPLICATION UPDATES:")
    print(MAIN_PY_UPDATES)
    
    print("\n2. DATABASE MODEL UPDATES:")
    print(DATABASE_MODELS_UPDATES)
    
    print("\n3. SERVICE INTEGRATION EXAMPLES:")
    for service_name, example_code in SERVICE_INTEGRATION_EXAMPLES.items():
        print(f"\n📝 {service_name}:")
        print(example_code)
    
    print("\n4. SCHEDULED TASKS:")
    print(SCHEDULED_TASKS_EXAMPLE)
    
    print("\n5. FRONTEND INTEGRATION:")
    print(FRONTEND_INTEGRATION_NOTES)
    
    print("\n" + "=" * 60)
    print("✅ Integration guide complete!")
    print("\nNext steps:")
    print("1. Update your main.py to include the notifications router")
    print("2. Update database models if needed")
    print("3. Replace notification calls in existing services")
    print("4. Set up scheduled tasks for automated notifications")
    print("5. Update frontend to use new notification endpoints")
    print("6. Test the notification workflows using the integration helper")

if __name__ == "__main__":
    print_setup_instructions()
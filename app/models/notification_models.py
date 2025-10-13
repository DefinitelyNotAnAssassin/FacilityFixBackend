"""
Enhanced notification models for the FacilityFix notification system.
Provides comprehensive notification types and metadata for tracking.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class NotificationType(str, Enum):
    """Enumeration of all possible notification types in the system"""
    
    # Work Orders
    WORK_ORDER_SUBMITTED = "work_order_submitted"
    WORK_ORDER_ASSIGNED = "work_order_assigned"
    WORK_ORDER_SCHEDULE_SET = "work_order_schedule_set"
    WORK_ORDER_SCHEDULE_UPDATED = "work_order_schedule_updated"
    WORK_ORDER_CANCELED = "work_order_canceled"
    
    # Job Service
    JOB_SERVICE_RECEIVED = "job_service_received"
    JOB_SERVICE_COMPLETED = "job_service_completed"
    
    # Work Order Permit
    PERMIT_CREATED = "permit_created"
    PERMIT_APPROVED = "permit_approved"
    PERMIT_REJECTED = "permit_rejected"
    PERMIT_CANCELED = "permit_canceled"
    PERMIT_EXPIRING = "permit_expiring"
    
    # Maintenance (Preventive)
    PM_PLAN_GENERATED = "pm_plan_generated"
    MAINTENANCE_TASK_ASSIGNED = "maintenance_task_assigned"
    MAINTENANCE_RESCHEDULED = "maintenance_rescheduled"
    MAINTENANCE_OVERDUE = "maintenance_overdue"
    MAINTENANCE_COMPLETED = "maintenance_completed"
    
    # Inventory Management - Items
    INVENTORY_LOW_STOCK = "inventory_low_stock"
    INVENTORY_CRITICAL_STOCK = "inventory_critical_stock"
    INVENTORY_RESTOCKED = "inventory_restocked"
    INVENTORY_ITEM_ADDED = "inventory_item_added"
    INVENTORY_ITEM_UPDATED = "inventory_item_updated"
    
    # Inventory Management - Requests
    INVENTORY_REQUEST_SUBMITTED = "inventory_request_submitted"
    INVENTORY_REQUEST_REJECTED = "inventory_request_rejected"
    INVENTORY_REQUEST_READY = "inventory_request_ready"
    
    # Announcements
    ANNOUNCEMENT_PUBLISHED = "announcement_published"
    ANNOUNCEMENT_UPDATED = "announcement_updated"
    ANNOUNCEMENT_REMINDER = "announcement_reminder"
    
    # Users
    USER_INVITED = "user_invited"
    USER_APPROVED = "user_approved"
    USER_REJECTED = "user_rejected"
    
    # Concern Slips
    CONCERN_SLIP_SUBMITTED = "concern_slip_submitted"
    CONCERN_SLIP_ASSIGNED = "concern_slip_assigned"
    CONCERN_SLIP_ASSESSED = "concern_slip_assessed"
    CONCERN_SLIP_EVALUATED = "concern_slip_evaluated"
    CONCERN_SLIP_APPROVED = "concern_slip_approved"
    CONCERN_SLIP_REJECTED = "concern_slip_rejected"
    CONCERN_SLIP_RESOLUTION_SET = "concern_slip_resolution_set"
    CONCERN_SLIP_RETURNED = "concern_slip_returned"
    
    # Chat/Communication
    CHAT_MESSAGE_RECEIVED = "chat_message_received"
    
    # System
    SYSTEM_MAINTENANCE = "system_maintenance"
    ESCALATION = "escalation"


class NotificationPriority(str, Enum):
    """Priority levels for notifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class NotificationChannel(str, Enum):
    """Delivery channels for notifications"""
    IN_APP = "in_app"           # Show in application notifications panel
    PUSH = "push"               # Push notification to mobile/browser
    EMAIL = "email"             # Email notification
    SMS = "sms"                 # SMS notification (future)
    WEBSOCKET = "websocket"     # Real-time websocket notification


class DeliveryStatus(str, Enum):
    """Status of notification delivery"""
    PENDING = "pending"         # Not yet sent
    SENT = "sent"              # Successfully sent
    DELIVERED = "delivered"     # Confirmed delivered
    READ = "read"              # User has read the notification
    FAILED = "failed"          # Failed to send
    EXPIRED = "expired"        # Notification expired


class EnhancedNotification(BaseModel):
    """Enhanced notification model with comprehensive tracking"""
    
    # Basic identification
    id: Optional[str] = None
    notification_type: NotificationType
    
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
    priority: NotificationPriority = NotificationPriority.NORMAL
    is_urgent: bool = Field(default=False)
    expires_at: Optional[datetime] = None     # Auto-expire notification
    
    # Delivery settings
    channels: List[NotificationChannel] = Field(default=[NotificationChannel.IN_APP])
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    
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


class NotificationTemplate(BaseModel):
    """Template for generating notifications with dynamic content"""
    
    id: Optional[str] = None
    name: str
    notification_type: NotificationType
    
    # Template content with placeholders
    title_template: str              # e.g., "Work Order #{work_order_id} has been assigned"
    message_template: str            # e.g., "Your work order for {location} has been assigned to {staff_name}"
    description_template: Optional[str] = None
    
    # Default settings
    default_priority: NotificationPriority = NotificationPriority.NORMAL
    default_channels: List[NotificationChannel] = Field(default=[NotificationChannel.IN_APP])
    default_expires_hours: Optional[int] = None  # Auto-expire after X hours
    requires_action: bool = Field(default=False)
    
    # Targeting rules
    target_roles: Optional[List[str]] = []       # Which user roles should receive this
    target_departments: Optional[List[str]] = [] # Which departments should receive this
    
    # Action configuration
    action_url_template: Optional[str] = None    # e.g., "/work-orders/{work_order_id}"
    action_label: Optional[str] = None           # e.g., "View Work Order"
    
    # Metadata
    is_active: bool = Field(default=True)
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationRule(BaseModel):
    """Rules for automatic notification generation"""
    
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    
    # Trigger conditions
    trigger_event: str               # e.g., "work_order_created", "inventory_low_stock"
    trigger_conditions: Dict[str, Any] = {}  # Additional conditions
    
    # Template to use
    template_id: str
    
    # Override settings
    priority_override: Optional[NotificationPriority] = None
    channels_override: Optional[List[NotificationChannel]] = None
    
    # Timing
    delay_minutes: int = Field(default=0)     # Delay before sending
    max_frequency_hours: Optional[int] = None # Prevent spam (don't send same type more than once per X hours)
    
    # Targeting
    recipient_rules: Dict[str, Any] = {}      # Rules for determining recipients
    
    # Control
    is_active: bool = Field(default=True)
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationPreference(BaseModel):
    """User preferences for notification delivery"""
    
    id: Optional[str] = None
    user_id: str
    
    # Channel preferences by notification type
    notification_preferences: Dict[str, List[NotificationChannel]] = {}
    
    # Global settings
    email_enabled: bool = Field(default=True)
    push_enabled: bool = Field(default=True)
    sms_enabled: bool = Field(default=False)
    
    # Quiet hours
    quiet_hours_enabled: bool = Field(default=False)
    quiet_hours_start: Optional[str] = None   # "22:00"
    quiet_hours_end: Optional[str] = None     # "08:00"
    quiet_hours_timezone: Optional[str] = None
    
    # Frequency limits
    max_notifications_per_hour: int = Field(default=10)
    digest_mode: bool = Field(default=False)  # Batch notifications into digest
    digest_frequency: str = Field(default="daily")  # hourly, daily, weekly
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationBatch(BaseModel):
    """Batch of notifications for digest delivery"""
    
    id: Optional[str] = None
    user_id: str
    batch_type: str  # daily_digest, urgent_batch, etc.
    
    # Content
    title: str
    summary: str
    notification_ids: List[str]
    
    # Status
    status: DeliveryStatus = DeliveryStatus.PENDING
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
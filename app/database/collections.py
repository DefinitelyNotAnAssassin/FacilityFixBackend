# Collection Names
COLLECTIONS = {
    'buildings': 'buildings',
    'units': 'units',
    'users': 'users',
    'user_profiles': 'user_profiles',
    'equipment': 'equipment',
    'inventory': 'inventory',
    'inventory_transactions': 'inventory_transactions',
    'inventory_requests': 'inventory_requests',
    'inventory_reservations': 'inventory_reservations',
    'low_stock_alerts': 'low_stock_alerts',
    'inventory_usage_analytics': 'inventory_usage_analytics',
    'concern_slips': 'concern_slips',
    'job_services': 'job_services',
    'work_order_permits': 'work_order_permits',
    'maintenance_tasks': 'maintenance_tasks',
    'announcements': 'announcements',
    'notifications': 'notifications',
    'status_history': 'status_history',
    'feedback': 'feedback',
    'maintenance_schedules': 'maintenance_schedules',
    'equipment_usage_logs': 'equipment_usage_logs',
    'maintenance_templates': 'maintenance_templates',
    'maintenance_reports': 'maintenance_reports',
    'user_fcm_tokens': 'user_fcm_tokens',
    'file_attachments': 'file_attachments',
    'counters': 'counters',
    'chat_rooms': 'chat_rooms',
    'chat_messages': 'chat_messages',
}

# Collection Structure Documentation
COLLECTION_SCHEMAS = {
    'buildings': {
        'fields': ['building_name', 'address', 'total_floors', 'total_units'],
        'required': ['building_name', 'address', 'total_floors', 'total_units'],
        'indexes': ['building_name']
    },
    'units': {
        'fields': ['building_id', 'unit_number', 'floor_number', 'occupancy_status'],
        'required': ['building_id', 'unit_number', 'floor_number'],
        'indexes': ['building_id', 'unit_number']
    },
    'users':{
        'fields': ['building_id', 'unit_id', 'first_name', 'last_name', 'phone_number', 'department', 'role', 'status'],
        'required': ['first_name', 'last_name', 'role'],
        'indexes': ['role', 'building_id', 'status']
    },
    'user_profiles': {
        'fields': ['building_id', 'unit_id', 'first_name', 'last_name', 'phone_number', 'department', 'role', 'status'],
        'required': ['first_name', 'last_name', 'role'],
        'indexes': ['role', 'building_id', 'status']
    },
    'equipment': {
        'fields': ['building_id', 'equipment_name', 'equipment_type', 'location', 'status', 'is_critical'],
        'required': ['building_id', 'equipment_name', 'equipment_type', 'location'],
        'indexes': ['building_id', 'equipment_type', 'status']
    },
    'inventory': {
        'fields': ['building_id', 'item_name', 'item_code', 'department', 'classification', 'category', 'current_stock', 'reorder_level', 'max_stock_level', 'unit_of_measure', 'unit_cost', 'supplier_name', 'storage_location', 'is_critical', 'is_active'],
        'required': ['building_id', 'item_name', 'department', 'classification', 'current_stock', 'reorder_level', 'unit_of_measure'],
        'indexes': ['building_id', 'department', 'classification', 'current_stock', 'is_critical', 'is_active']
    },
    'inventory_transactions': {
        'fields': ['inventory_id', 'transaction_type', 'quantity', 'previous_stock', 'new_stock', 'reference_type', 'reference_id', 'performed_by', 'reason', 'cost_per_unit', 'total_cost'],
        'required': ['inventory_id', 'transaction_type', 'quantity', 'previous_stock', 'new_stock', 'performed_by'],
        'indexes': ['inventory_id', 'transaction_type', 'reference_type', 'reference_id', 'performed_by', 'created_at']
    },
    'inventory_requests': {
        'fields': ['inventory_id', 'requested_by', 'approved_by', 'quantity_requested', 'quantity_approved', 'purpose', 'reference_id', 'priority', 'status', 'justification'],
        'required': ['inventory_id', 'requested_by', 'quantity_requested', 'purpose'],
        'indexes': ['inventory_id', 'requested_by', 'approved_by', 'status', 'priority', 'created_at']
    },
    'inventory_reservations': {
        'fields': ['inventory_id', 'created_by', 'maintenance_task_id', 'quantity', 'status', 'reserved_at', 'released_at', 'created_at', 'updated_at'],
        'required': ['inventory_id', 'created_by', 'maintenance_task_id', 'quantity', 'status'],
        'indexes': ['inventory_id', 'created_by', 'maintenance_task_id', 'status', 'reserved_at', 'created_at']
    },
    'low_stock_alerts': {
        'fields': ['inventory_id', 'building_id', 'item_name', 'current_stock', 'reorder_level', 'alert_level', 'status', 'acknowledged_by'],
        'required': ['inventory_id', 'building_id', 'item_name', 'current_stock', 'reorder_level', 'alert_level'],
        'indexes': ['inventory_id', 'building_id', 'alert_level', 'status', 'created_at']
    },
    'inventory_usage_analytics': {
        'fields': ['inventory_id', 'building_id', 'period_start', 'period_end', 'period_type', 'total_consumed', 'total_restocked', 'average_daily_usage', 'cost_consumed', 'cost_restocked'],
        'required': ['inventory_id', 'building_id', 'period_start', 'period_end', 'period_type', 'total_consumed', 'total_restocked', 'average_daily_usage'],
        'indexes': ['inventory_id', 'building_id', 'period_type', 'period_start', 'period_end']
    },
    'concern_slips': {
        'fields': ['reported_by', 'unit_id', 'title', 'description', 'location', 'category', 'priority', 'status', 'resolution_type', 'evaluated_by', 'formatted_id'],
        'required': ['reported_by', 'title', 'description', 'location', 'category', 'formatted_id'],
        'indexes': ['status', 'priority', 'reported_by', 'category', 'resolution_type', 'formatted_id']
    },
    'job_services': {
        'fields': ['concern_slip_id', 'created_by', 'assigned_to', 'title', 'description', 'location', 'category', 'priority', 'status', 'scheduled_date', 'completed_at'],
        'required': ['concern_slip_id', 'created_by', 'title', 'description', 'location', 'category'],
        'indexes': ['status', 'assigned_to', 'created_by', 'concern_slip_id', 'priority']
    },
    'work_order_permits': {
        'fields': ['concern_slip_id', 'requested_by', 'unit_id', 'contractor_name', 'contractor_contact', 'work_description', 'status', 'approved_by', 'proposed_start_date'],
        'required': ['concern_slip_id', 'requested_by', 'unit_id', 'contractor_name', 'contractor_contact', 'work_description'],
        'indexes': ['status', 'requested_by', 'unit_id', 'approved_by']
    },
    'maintenance_tasks': {
        'fields': ['equipment_id', 'assigned_to', 'location', 'task_description', 'status', 'scheduled_date', 'recurrence_type'],
        'required': ['assigned_to', 'location', 'task_description', 'scheduled_date'],
        'indexes': ['status', 'assigned_to', 'scheduled_date']
    },
    'announcements': {
        'fields': ['created_by', 'building_id', 'title', 'content', 'type', 'audience', 'is_active'],
        'required': ['created_by', 'building_id', 'title', 'content'],
        'indexes': ['building_id', 'type', 'is_active']
    },
    'notifications': {
        'fields': ['recipient_id', 'recipient_ids', 'sender_id', 'title', 'message', 'description', 'notification_type', 'related_entity_type', 'related_entity_id', 'building_id', 'department', 'priority', 'is_urgent', 'expires_at', 'channels', 'delivery_status', 'is_read', 'read_at', 'delivered_at', 'failed_reason', 'action_url', 'action_label', 'requires_action', 'action_taken', 'action_taken_at', 'custom_data', 'tags', 'group_key', 'batch_id'],
        'required': ['recipient_id', 'title', 'message', 'notification_type'],
        'indexes': ['recipient_id', 'is_read', 'notification_type', 'related_entity_type', 'related_entity_id', 'building_id', 'priority', 'delivery_status', 'expires_at', 'group_key', 'created_at']
    },
    'status_history': {
        'fields': ['work_order_id', 'previous_status', 'new_status', 'updated_by', 'remarks', 'timestamp'],
        'required': ['work_order_id', 'new_status', 'updated_by'],
        'indexes': ['work_order_id', 'timestamp']
    },
    'feedback': {
        'fields': ['work_order_id', 'request_id', 'submitted_by', 'rating', 'comments', 'service_quality', 'timeliness'],
        'required': ['work_order_id', 'request_id', 'submitted_by', 'rating'],
        'indexes': ['work_order_id', 'submitted_by', 'rating']
    },
    'maintenance_schedules': {
        'fields': ['equipment_id', 'building_id', 'schedule_name', 'description', 'schedule_type', 'recurrence_pattern', 'interval_value', 'usage_threshold', 'usage_unit', 'is_active', 'priority', 'created_by', 'next_due_date'],
        'required': ['equipment_id', 'building_id', 'schedule_name', 'description', 'schedule_type', 'created_by'],
        'indexes': ['equipment_id', 'building_id', 'schedule_type', 'is_active', 'next_due_date', 'priority']
    },
    'equipment_usage_logs': {
        'fields': ['equipment_id', 'building_id', 'usage_type', 'usage_value', 'usage_unit', 'recorded_by', 'recording_method', 'notes', 'recorded_at'],
        'required': ['equipment_id', 'building_id', 'usage_type', 'usage_value', 'usage_unit', 'recorded_at'],
        'indexes': ['equipment_id', 'building_id', 'usage_type', 'recorded_at', 'recorded_by']
    },
    'maintenance_templates': {
        'fields': ['template_name', 'equipment_type', 'category', 'description', 'checklist_items', 'estimated_duration', 'required_skills', 'required_tools', 'required_parts', 'safety_requirements', 'created_by', 'is_active', 'version'],
        'required': ['template_name', 'equipment_type', 'category', 'description', 'checklist_items', 'estimated_duration', 'created_by'],
        'indexes': ['equipment_type', 'category', 'is_active', 'created_by']
    },
    'maintenance_reports': {
        'fields': ['building_id', 'report_type', 'period_start', 'period_end', 'total_tasks_scheduled', 'total_tasks_completed', 'completion_rate', 'compliance_rate', 'generated_by', 'generated_at'],
        'required': ['building_id', 'report_type', 'period_start', 'period_end', 'total_tasks_scheduled', 'total_tasks_completed', 'completion_rate', 'compliance_rate', 'generated_by', 'generated_at'],
        'indexes': ['building_id', 'report_type', 'period_start', 'period_end', 'generated_at']
    },
    'user_fcm_tokens': {
        'fields': ['user_id', 'fcm_token', 'device_info', 'is_active', 'created_at', 'updated_at'],
        'required': ['user_id', 'fcm_token', 'is_active'],
        'indexes': ['user_id', 'fcm_token', 'is_active', 'created_at']
    },
    'file_attachments': {
        'fields': ['file_path', 'original_filename', 'file_size', 'content_type', 'entity_type', 'entity_id', 'uploaded_by', 'file_type', 'description', 'storage_url', 'is_active'],
        'required': ['file_path', 'original_filename', 'file_size', 'content_type', 'entity_type', 'entity_id', 'uploaded_by'],
        'indexes': ['entity_type', 'entity_id', 'uploaded_by', 'is_active', 'created_at']
    },
    'counters': {
        'fields': ['year', 'counter', 'last_updated'],
        'required': ['year', 'counter'],
        'indexes': ['year']
    },
    'chat_rooms': {
        'fields': ['concern_slip_id', 'job_service_id', 'work_permit_id', 'participants', 'participant_roles', 'created_by', 'last_message', 'last_message_at', 'is_active', 'room_type'],
        'required': ['participants', 'participant_roles', 'created_by', 'room_type'],
        'indexes': ['participants', 'concern_slip_id', 'job_service_id', 'work_permit_id', 'is_active', 'last_message_at']
    },
    'chat_messages': {
        'fields': ['room_id', 'sender_id', 'sender_name', 'sender_role', 'message_text', 'message_type', 'attachments', 'is_read', 'read_by', 'is_deleted'],
        'required': ['room_id', 'sender_id', 'sender_name', 'sender_role', 'message_text'],
        'indexes': ['room_id', 'sender_id', 'created_at', 'is_read']
    },
}

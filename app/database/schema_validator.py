from typing import Dict, Any, Optional, List
from pydantic import ValidationError
from app.models.database_models import (
    Building, Unit, UserProfile, Equipment, Inventory,
    ConcernSlip, JobService, WorkOrderPermit, MaintenanceTask, Announcement,
    StatusHistory, Feedback, Counter, Notification  # Added Notification model
)

class SchemaValidator:
    """Validates Firestore documents against defined schemas"""
    
    MODEL_MAPPING = {
        'buildings': Building,
        'units': Unit,
        'users': UserProfile,
        'equipment': Equipment,
        'inventory': Inventory,
        'concern_slips': ConcernSlip,
        'job_services': JobService,
        'work_order_permits': WorkOrderPermit,
        'maintenance_tasks': MaintenanceTask,
        'announcements': Announcement,
        'notifications': Notification,  # Added notifications collection mapping
        'status_history': StatusHistory,
        'feedback': Feedback,
        'counters': Counter  # Added counters collection mapping
    }
    
    @classmethod
    def validate_document(cls, collection: str, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate a document against its schema
        
        Args:
            collection: Collection name
            data: Document data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if collection not in cls.MODEL_MAPPING:
            return False, f"Unknown collection: {collection}"
        
        model_class = cls.MODEL_MAPPING[collection]
        
        try:
            # Validate the data using Pydantic model
            model_class(**data)
            return True, None
        except ValidationError as e:
            error_details = []
            for error in e.errors():
                field = " -> ".join(str(x) for x in error['loc'])
                message = error['msg']
                error_details.append(f"{field}: {message}")
            
            return False, "; ".join(error_details)
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @classmethod
    def validate_required_fields(cls, collection: str, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Check if all required fields are present
        
        Args:
            collection: Collection name
            data: Document data to check
            
        Returns:
            Tuple of (all_present, missing_fields)
        """
        if collection not in cls.MODEL_MAPPING:
            return False, [f"Unknown collection: {collection}"]
        
        model_class = cls.MODEL_MAPPING[collection]
        
        # Get required fields from the model
        required_fields = []
        for field_name, field_info in model_class.__fields__.items():
            if field_info.is_required() and field_name not in ['id', 'created_at', 'updated_at']:
                required_fields.append(field_name)
        
        # Check which required fields are missing
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)
        
        return len(missing_fields) == 0, missing_fields
    
    @classmethod
    def get_collection_schema(cls, collection: str) -> Optional[Dict[str, Any]]:
        """
        Get the schema definition for a collection
        
        Args:
            collection: Collection name
            
        Returns:
            Schema definition or None if collection not found
        """
        if collection not in cls.MODEL_MAPPING:
            return None
        
        model_class = cls.MODEL_MAPPING[collection]
        return model_class.schema()

# Create global validator instance
schema_validator = SchemaValidator()

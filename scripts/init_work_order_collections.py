import asyncio
from datetime import datetime
from app.database.firestore_client import get_firestore_client
from app.database.database_service import DatabaseService
from app.database.collections import COLLECTIONS

async def init_work_order_collections():
    """Initialize work order management collections"""
    
    # Get database service
    firestore_client = get_firestore_client()
    db_service = DatabaseService(firestore_client)
    
    print("Initializing Work Order Management Collections...")
    
    # Initialize work_orders collection with sample data
    sample_work_order = {
        "request_id": "sample_repair_request_id",
        "created_by": "admin_user_id",
        "assigned_to": None,
        "work_type": "job_service",
        "status": "unassigned",
        "scheduled_date": None,
        "completed_date": None,
        "estimated_hours": 2.0,
        "actual_hours": None,
        "materials_used": [],
        "cost": None,
        "notes": "Sample work order for testing",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    try:
        work_order_result = await db_service.create_document(
            COLLECTIONS['work_orders'], 
            sample_work_order
        )
        print(f"✓ Created sample work order: {work_order_result['id']}")
    except Exception as e:
        print(f"✗ Failed to create work order: {e}")
    
    # Initialize status_history collection with sample data
    sample_status_history = {
        "work_order_id": work_order_result['id'] if 'work_order_result' in locals() else "sample_work_order_id",
        "previous_status": None,
        "new_status": "unassigned",
        "updated_by": "admin_user_id",
        "remarks": "Work order created",
        "timestamp": datetime.utcnow()
    }
    
    try:
        status_result = await db_service.create_document(
            COLLECTIONS['status_history'], 
            sample_status_history
        )
        print(f"✓ Created sample status history: {status_result['id']}")
    except Exception as e:
        print(f"✗ Failed to create status history: {e}")
    
    # Initialize feedback collection with sample data
    sample_feedback = {
        "work_order_id": work_order_result['id'] if 'work_order_result' in locals() else "sample_work_order_id",
        "request_id": "sample_repair_request_id",
        "submitted_by": "tenant_user_id",
        "rating": 5,
        "comments": "Excellent service, very professional and timely",
        "service_quality": 5,
        "timeliness": 4,
        "communication": 5,
        "would_recommend": True,
        "submitted_at": datetime.utcnow()
    }
    
    try:
        feedback_result = await db_service.create_document(
            COLLECTIONS['feedback'], 
            sample_feedback
        )
        print(f"✓ Created sample feedback: {feedback_result['id']}")
    except Exception as e:
        print(f"✗ Failed to create feedback: {e}")
    
    print("\nWork Order Management Collections initialized successfully!")
    print("\nAvailable collections:")
    for collection_name in [COLLECTIONS['work_orders'], COLLECTIONS['status_history'], COLLECTIONS['feedback']]:
        print(f"  - {collection_name}")

if __name__ == "__main__":
    asyncio.run(init_work_order_collections())
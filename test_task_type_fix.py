"""
Quick test to verify task_type_id is properly saved
"""
import asyncio
from datetime import datetime
from app.models.database_models import MaintenanceTask

async def test_task_type_id():
    # Test MaintenanceTask model
    print("Testing MaintenanceTask model with task_type_id...")
    
    task_data = {
        "building_id": "test_building",
        "task_title": "Test Task", 
        "task_description": "Test Description",
        "location": "Test Location",
        "scheduled_date": datetime.now(),
        "task_type_id": "TT-2025-00001"  # This should be saved
    }
    
    # Create MaintenanceTask instance
    try:
        task = MaintenanceTask(**task_data)
        print(f"✅ MaintenanceTask created successfully")
        print(f"   task_type_id: {task.task_type_id}")
        print(f"   Model dict contains task_type_id: {'task_type_id' in task.dict()}")
        
        # Print the dict to see all fields
        task_dict = task.dict()
        if 'task_type_id' in task_dict:
            print(f"   task_type_id value in dict: {task_dict['task_type_id']}")
        else:
            print("   ❌ task_type_id not found in dict!")
            
    except Exception as e:
        print(f"❌ Error creating MaintenanceTask: {e}")

if __name__ == "__main__":
    asyncio.run(test_task_type_id())
#!/usr/bin/env python3
"""
Test script for inventory forecasting endpoint
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.firebase_init import initialize_firebase, is_firebase_available, get_firebase_status

# Initialize Firebase first
print("🔥 Initializing Firebase...")
firebase_status = get_firebase_status()

if not is_firebase_available():
    success = initialize_firebase()
    if not success:
        print("❌ Firebase initialization failed")
        sys.exit(1)
    else:
        print("✅ Firebase initialized successfully")
else:
    print("✅ Firebase already initialized")

from app.services.inventory_service import inventory_service

async def test_forecasting():
    """Test the forecasting functionality"""
    try:
        # Use a test building ID - you'll need to replace this with a real one
        building_id = "test_building_001"
        
        print(f"Testing forecasting for building: {building_id}")
        
        success, data, error = await inventory_service.get_inventory_forecasting_data(building_id)
        
        print(f"Success: {success}")
        print(f"Data length: {len(data) if data else 0}")
        print(f"Error: {error}")
        
        if success:
            print(f"✅ Successfully retrieved {len(data)} forecasting items")
            if data:
                print("Sample item:")
                print(data[0])
        else:
            print(f"❌ Error: {error}")
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_forecasting())
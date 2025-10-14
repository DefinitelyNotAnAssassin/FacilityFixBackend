"""
Initialize Inventory Collections in Firestore

This script creates the necessary inventory-related collections in Firestore
with proper structure and indexes.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.database_service import database_service
from app.database.collections import COLLECTIONS
from datetime import datetime
import asyncio


async def init_inventory_collections():
    """Initialize inventory-related collections with sample data"""
    
    print("=" * 60)
    print("Initializing Inventory Collections")
    print("=" * 60)
    
    try:
        # Initialize collections (this will create them if they don't exist)
        collections_to_init = [
            'inventory',
            'inventory_transactions',
            'inventory_requests',
            'low_stock_alerts',
            'inventory_usage_analytics'
        ]
        
        # No need to initialize with dummy docs - we'll create real sample data
        print("\n� Collections will be created automatically with sample data...")
        
        # Create sample inventory items
        print("\n📝 Creating sample inventory items...")
        
        sample_items = [
            {
                'building_id': 'default_building_id',
                'item_name': 'Wrench Set',
                'item_code': 'TOOL-001',
                'department': 'Maintenance',
                'classification': 'Tools',
                'category': 'Hand Tools',
                'current_stock': 10,
                'reorder_level': 5,
                'max_stock_level': 20,
                'unit_of_measure': 'pieces',
                'unit_cost': 25.00,
                'supplier_name': 'Hardware Supply Co',
                'storage_location': 'Storage Room A',
                'is_critical': False,
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'brand_name': 'ProTool',
                'description': 'Professional wrench set for maintenance'
            },
            {
                'building_id': 'default_building_id',
                'item_name': 'White Paint',
                'item_code': 'PAINT-001',
                'department': 'Maintenance',
                'classification': 'Consumables',
                'category': 'Paint',
                'current_stock': 8,
                'reorder_level': 3,
                'max_stock_level': 15,
                'unit_of_measure': 'gallons',
                'unit_cost': 35.50,
                'supplier_name': 'Paint Pros Inc',
                'storage_location': 'Storage Room B',
                'is_critical': False,
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'brand_name': 'Premium Paint',
                'description': 'High-quality white interior paint'
            },
            {
                'building_id': 'default_building_id',
                'item_name': 'Air Filter HVAC',
                'item_code': 'HVAC-FILTER-001',
                'department': 'Engineering',
                'classification': 'Equipment Parts',
                'category': 'HVAC',
                'current_stock': 4,
                'reorder_level': 10,
                'max_stock_level': 50,
                'unit_of_measure': 'pieces',
                'unit_cost': 15.75,
                'supplier_name': 'HVAC Solutions Ltd',
                'storage_location': 'HVAC Storage',
                'is_critical': True,
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'brand_name': 'FilterMax',
                'description': 'MERV 11 air filter for HVAC system'
            },
            {
                'building_id': 'default_building_id',
                'item_name': 'Cleaning Solution',
                'item_code': 'CLEAN-001',
                'department': 'Facilities',
                'classification': 'Consumables',
                'category': 'Cleaning',
                'current_stock': 20,
                'reorder_level': 10,
                'max_stock_level': 40,
                'unit_of_measure': 'bottles',
                'unit_cost': 8.50,
                'supplier_name': 'CleanSupply Co',
                'storage_location': 'Janitor Closet',
                'is_critical': False,
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'brand_name': 'EcoClean',
                'description': 'Multi-purpose cleaning solution'
            },
            {
                'building_id': 'default_building_id',
                'item_name': 'LED Light Bulb',
                'item_code': 'LIGHT-001',
                'department': 'Maintenance',
                'classification': 'Equipment Parts',
                'category': 'Lighting',
                'current_stock': 50,
                'reorder_level': 25,
                'max_stock_level': 100,
                'unit_of_measure': 'pieces',
                'unit_cost': 5.25,
                'supplier_name': 'Lighting World',
                'storage_location': 'Storage Room A',
                'is_critical': False,
                'is_active': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'brand_name': 'BrightLife',
                'description': '60W equivalent LED bulb, 800 lumens'
            }
        ]
        
        created_count = 0
        for item in sample_items:
            success, item_id, error = await database_service.create_document(
                COLLECTIONS['inventory'],
                item,
                validate=False
            )
            
            if success:
                print(f"✅ Created: {item['item_name']} (ID: {item_id})")
                created_count += 1
            else:
                print(f"❌ Failed to create {item['item_name']}: {error}")
        
        print(f"\n✅ Created {created_count}/{len(sample_items)} inventory items")
        
        # Create a sample inventory request
        print("\n📝 Creating sample inventory request...")
        sample_request = {
            'inventory_id': 'HVAC-FILTER-001',  # Reference one of the items
            'building_id': 'default_building_id',
            'requested_by': 'maintenance_staff',
            'quantity_requested': 5,
            'purpose': 'Monthly HVAC maintenance',
            'status': 'pending',
            'priority': 'high',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'requested_date': datetime.now()
        }
        
        success, req_id, error = await database_service.create_document(
            COLLECTIONS['inventory_requests'],
            sample_request,
            validate=False
        )
        
        if success:
            print(f"✅ Sample inventory request created with ID: {req_id}")
        else:
            print(f"❌ Failed to create sample request: {error}")
        
        print("\n" + "=" * 60)
        print("✅ Inventory data initialized successfully!")
        print("=" * 60)
        print("\n🎉 Setup complete! Check your Firestore console to see the data.")
        
    except Exception as e:
        print(f"\n❌ Error during initialization: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(init_inventory_collections())

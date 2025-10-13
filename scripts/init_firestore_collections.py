"""
Firestore Database Initialization Script
Creates collections with proper indexes and sample data for FacilityFix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.auth.firebase_auth import firebase_auth  # Initialize Firebase first
from app.database.firestore_client import FirestoreClient
from app.database.collections import COLLECTIONS, COLLECTION_SCHEMAS
from app.models.database_models import Building, Unit, UserProfile, Equipment, Inventory
from datetime import datetime
import json

def create_indexes():
    """Create composite indexes for Firestore collections"""
    print("Creating Firestore indexes...")
    
    # Note: Composite indexes need to be created via Firebase Console or gcloud CLI
    # This function documents the required indexes
    
    required_indexes = {
        'repair_requests': [
            ['status', 'priority'],
            ['assigned_to', 'status'],
            ['reported_by', 'created_at']
        ],
        'maintenance_tasks': [
            ['assigned_to', 'status'],
            ['scheduled_date', 'status'],
            ['equipment_id', 'status']
        ],
        'inventory': [
            ['building_id', 'current_stock'],
            ['department', 'current_stock']
        ],
        'equipment': [
            ['building_id', 'equipment_type'],
            ['building_id', 'status']
        ]
    }
    
    print("Required composite indexes:")
    for collection, indexes in required_indexes.items():
        print(f"\n{collection}:")
        for index in indexes:
            print(f"  - {' + '.join(index)}")
    
    print("\nNote: Create these indexes in Firebase Console under Firestore > Indexes")

def create_sample_building():
    """Create a sample building for testing"""
    client = FirestoreClient()
    
    # Sample building data
    building_data = {
        'building_name': 'Sunrise Condominium',
        'address': '123 Main Street, Manila, Philippines',
        'total_floors': 15,
        'total_units': 120,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow()
    }
    
    try:
        building_id = client.create_document(COLLECTIONS['buildings'], data=building_data)
        print(f"Created sample building: {building_id}")
        return building_id
    except Exception as e:
        print(f"Error creating sample building: {e}")
        return None

def create_sample_units(building_id: str):
    """Create sample units for the building"""
    if not building_id:
        return
    
    client = FirestoreClient()
    
    # Create sample units for floors 1-3
    units_created = 0
    for floor in range(1, 4):  # Floors 1, 2, 3
        for unit_num in range(1, 9):  # 8 units per floor
            unit_data = {
                'building_id': building_id,
                'unit_number': f"{floor:02d}{unit_num:02d}",
                'floor_number': floor,
                'occupancy_status': 'occupied' if unit_num <= 6 else 'vacant',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            try:
                unit_id = client.create_document(COLLECTIONS['units'], data=unit_data)
                units_created += 1
            except Exception as e:
                print(f"Error creating unit {unit_data['unit_number']}: {e}")
    
    print(f"Created {units_created} sample units")

def create_sample_equipment(building_id: str):
    """Create sample equipment for the building"""
    if not building_id:
        return
    
    client = FirestoreClient()
    
    sample_equipment = [
        {
            'building_id': building_id,
            'equipment_name': 'Main Elevator A',
            'equipment_type': 'elevator',
            'model_number': 'OTIS-2000X',
            'serial_number': 'ELV001',
            'location': 'Lobby',
            'department': 'Engineering',
            'status': 'active',
            'is_critical': True
        },
        {
            'building_id': building_id,
            'equipment_name': 'HVAC Unit - Floor 1-5',
            'equipment_type': 'hvac',
            'model_number': 'CARRIER-50TC',
            'serial_number': 'HVAC001',
            'location': 'Rooftop',
            'department': 'Engineering',
            'status': 'active',
            'is_critical': True
        },
        {
            'building_id': building_id,
            'equipment_name': 'Fire Alarm System',
            'equipment_type': 'fire_safety',
            'model_number': 'HONEYWELL-FA',
            'serial_number': 'FIRE001',
            'location': 'All Floors',
            'department': 'Engineering',
            'status': 'active',
            'is_critical': True
        },
        {
            'building_id': building_id,
            'equipment_name': 'Water Pump System',
            'equipment_type': 'plumbing',
            'model_number': 'GRUNDFOS-CR',
            'serial_number': 'PUMP001',
            'location': 'Basement',
            'department': 'Engineering',
            'status': 'active',
            'is_critical': True
        }
    ]
    
    equipment_created = 0
    for equipment in sample_equipment:
        equipment['created_at'] = datetime.utcnow()
        equipment['updated_at'] = datetime.utcnow()
        
        try:
            equipment_id = client.create_document(COLLECTIONS['equipment'], data=equipment)
            equipment_created += 1
        except Exception as e:
            print(f"Error creating equipment {equipment['equipment_name']}: {e}")
    
    print(f"Created {equipment_created} sample equipment items")

def create_sample_inventory(building_id: str):
    """Create sample inventory items"""
    if not building_id:
        return
    
    client = FirestoreClient()
    
    sample_inventory = [
        {
            'building_id': building_id,
            'item_name': 'LED Light Bulbs',
            'department': 'Engineering',
            'classification': 'consumable',
            'current_stock': 50,
            'reorder_level': 10,
            'unit_of_measure': 'pcs'
        },
        {
            'building_id': building_id,
            'item_name': 'Toilet Paper',
            'department': 'Housekeeping',
            'classification': 'consumable',
            'current_stock': 100,
            'reorder_level': 20,
            'unit_of_measure': 'rolls'
        },
        {
            'building_id': building_id,
            'item_name': 'Cleaning Chemicals',
            'department': 'Housekeeping',
            'classification': 'consumable',
            'current_stock': 25,
            'reorder_level': 5,
            'unit_of_measure': 'liters'
        },
        {
            'building_id': building_id,
            'item_name': 'Electrical Tools Set',
            'department': 'Engineering',
            'classification': 'equipment',
            'current_stock': 3,
            'reorder_level': 1,
            'unit_of_measure': 'sets'
        }
    ]
    
    inventory_created = 0
    for item in sample_inventory:
        item['created_at'] = datetime.utcnow()
        item['updated_at'] = datetime.utcnow()
        
        try:
            item_id = client.create_document(COLLECTIONS['inventory'], data=item)
            inventory_created += 1
        except Exception as e:
            print(f"Error creating inventory item {item['item_name']}: {e}")
    
    print(f"Created {inventory_created} sample inventory items")

def main():
    """Initialize Firestore database with collections and sample data"""
    print("=== FacilityFix Database Initialization ===")
    print(f"Project: {settings.FIREBASE_PROJECT_ID}")
    
    try:
        client = FirestoreClient()
        print("✓ Firestore client connected successfully")
    except Exception as e:
        print(f"Error: Cannot connect to Firestore: {e}")
        print("Please check your Firebase configuration in .env file")
        return
    
    # Create indexes documentation
    create_indexes()
    
    # Create sample data
    print("\nCreating sample data...")
    building_id = create_sample_building()
    
    if building_id:
        create_sample_units(building_id)
        create_sample_equipment(building_id)
        create_sample_inventory(building_id)
    
    print("\n=== Database initialization completed ===")
    print("Next steps:")
    print("1. Create the composite indexes in Firebase Console")
    print("2. Deploy the security rules: firebase deploy --only firestore:rules")
    print("3. Test the API endpoints with the sample data")

if __name__ == "__main__":
    main()

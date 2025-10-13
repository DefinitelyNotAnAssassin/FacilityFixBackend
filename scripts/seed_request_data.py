"""
Seed Data for Request Management System
Creates sample concern slips, job services, and work order permits for testing
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the parent directory to the path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Initialize Firebase FIRST ---
import firebase_admin
from firebase_admin import credentials
from app.core.config import settings

if not firebase_admin._apps:
    try:
        # Use the path from settings OR hardcode if needed
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        raise

# --- Import database AFTER Firebase init ---
from app.database.database_service import database_service
from app.database.collections import COLLECTIONS


class RequestDataSeeder:
    """Setup seed data for request management system"""
    
    def __init__(self):
        self.created_concern_slips = []
        self.created_job_services = []
        self.created_work_order_permits = []
    
    async def create_concern_slips(self):
        """Create sample concern slips"""
        print("🎫 Creating concern slips...")
        
        concern_slips = [
            {
                "id": "concern_001",
                "reported_by": "tenant1@facilityfix.test",  # Alice Johnson
                "unit_id": "unit_001",
                "title": "Kitchen Faucet Leaking",
                "description": "The kitchen faucet has been dripping constantly for the past 3 days. Water is pooling under the sink and may cause damage to the cabinet.",
                "location": "Unit 101 - Kitchen",
                "category": "plumbing",
                "priority": "medium",
                "status": "evaluated",
                "urgency_assessment": "Moderate priority - requires internal maintenance staff attention",
                "resolution_type": "job_service",
                "attachments": ["/uploads/faucet_leak_photo.jpg"],
                "admin_notes": "Assigned to maintenance team for repair",
                "evaluated_by": "admin@facilityfix.test",
                "evaluated_at": datetime.utcnow() - timedelta(hours=2),
                "created_at": datetime.utcnow() - timedelta(days=1),
                "updated_at": datetime.utcnow() - timedelta(hours=2)
            },
            {
                "id": "concern_002", 
                "reported_by": "tenant2@facilityfix.test",  # Bob Smith
                "unit_id": "unit_004",
                "title": "Air Conditioning Unit Installation",
                "description": "Need to install a new split-type air conditioning unit in the master bedroom. Have already purchased the unit and hired a certified technician.",
                "location": "Unit 301 - Master Bedroom",
                "category": "hvac",
                "priority": "low",
                "status": "approved",
                "urgency_assessment": "Non-urgent installation work requiring external contractor permit",
                "resolution_type": "work_permit",
                "attachments": ["/uploads/ac_unit_specs.pdf", "/uploads/contractor_license.jpg"],
                "admin_notes": "Approved for external contractor work - permit issued",
                "evaluated_by": "admin@facilityfix.test",
                "evaluated_at": datetime.utcnow() - timedelta(hours=6),
                "created_at": datetime.utcnow() - timedelta(days=2),
                "updated_at": datetime.utcnow() - timedelta(hours=6)
            }
        ]
        
        for concern_slip in concern_slips:
            try:
                success, slip_id, error = await database_service.create_document(
                    COLLECTIONS['concern_slips'],
                    concern_slip,
                    validate=True
                )
                
                if success:
                    self.created_concern_slips.append(slip_id)
                    print(f"✅ Created concern slip: {concern_slip['title']}")
                else:
                    print(f"❌ Failed to create concern slip {concern_slip['title']}: {error}")
                    
            except Exception as e:
                print(f"❌ Error creating concern slip {concern_slip['title']}: {str(e)}")
    
    async def create_job_services(self):
        """Create sample job services"""
        print("🔧 Creating job services...")
        
        job_services = [
            {
                "id": "job_001",
                "concern_slip_id": "concern_001",
                "created_by": "admin@facilityfix.test",
                "assigned_to": "maintenance@facilityfix.test",  # John Maintenance
                "title": "Repair Kitchen Faucet Leak",
                "description": "Replace faulty faucet cartridge and check for any additional plumbing issues under the sink. Clean up any water damage to cabinet.",
                "location": "Unit 101 - Kitchen",
                "category": "plumbing",
                "priority": "medium",
                "status": "in_progress",
                "scheduled_date": datetime.utcnow() + timedelta(hours=4),
                "started_at": datetime.utcnow() - timedelta(minutes=30),
                "completed_at": None,
                "estimated_hours": 2.0,
                "actual_hours": None,
                "materials_used": ["Faucet cartridge", "Plumber's tape", "Cleaning supplies"],
                "staff_notes": "Started work - found worn cartridge as expected. Replacement in progress.",
                "completion_notes": None,
                "created_at": datetime.utcnow() - timedelta(hours=1),
                "updated_at": datetime.utcnow() - timedelta(minutes=30)
            }
        ]
        
        for job_service in job_services:
            try:
                success, job_id, error = await database_service.create_document(
                    COLLECTIONS['job_services'],
                    job_service,
                    validate=True
                )
                
                if success:
                    self.created_job_services.append(job_id)
                    print(f"✅ Created job service: {job_service['title']}")
                else:
                    print(f"❌ Failed to create job service {job_service['title']}: {error}")
                    
            except Exception as e:
                print(f"❌ Error creating job service {job_service['title']}: {str(e)}")
    
    async def create_work_order_permits(self):
        """Create sample work order permits"""
        print("📋 Creating work order permits...")
        
        work_order_permits = [
            {
                "id": "permit_001",
                "concern_slip_id": "concern_002",
                "requested_by": "tenant2@facilityfix.test",  # Bob Smith
                "unit_id": "unit_004",
                "contractor_name": "Mike Rodriguez",
                "contractor_contact": "+1234567895",
                "contractor_company": "Cool Air HVAC Services",
                "work_description": "Installation of split-type air conditioning unit in master bedroom including electrical connections and mounting brackets.",
                "proposed_start_date": datetime.utcnow() + timedelta(days=2),
                "estimated_duration": "4 hours",
                "specific_instructions": "Unit access required from 9 AM to 1 PM. Contractor has all necessary tools and equipment. Please ensure power is available in the unit.",
                "entry_requirements": "Contractor must present ID and company credentials at front desk",
                "status": "approved",
                "approved_by": "admin@facilityfix.test",
                "approval_date": datetime.utcnow() - timedelta(hours=4),
                "denial_reason": None,
                "permit_conditions": "Work must be completed within scheduled timeframe. Any electrical work must be inspected by building engineer before completion.",
                "actual_start_date": None,
                "actual_completion_date": None,
                "admin_notes": "Contractor credentials verified. HVAC license valid until 2025.",
                "created_at": datetime.utcnow() - timedelta(hours=8),
                "updated_at": datetime.utcnow() - timedelta(hours=4)
            }
        ]
        
        for permit in work_order_permits:
            try:
                success, permit_id, error = await database_service.create_document(
                    COLLECTIONS['work_order_permits'],
                    permit,
                    validate=True
                )
                
                if success:
                    self.created_work_order_permits.append(permit_id)
                    print(f"✅ Created work order permit: {permit['work_description'][:50]}...")
                else:
                    print(f"❌ Failed to create work order permit: {error}")
                    
            except Exception as e:
                print(f"❌ Error creating work order permit: {str(e)}")
    
    async def seed_all_request_data(self):
        """Seed all request management data"""
        print("🚀 Setting up seed data for Request Management System")
        print("="*60)
        
        await self.create_concern_slips()
        await self.create_job_services()
        await self.create_work_order_permits()
        
        print(f"\n📊 SEED DATA SUMMARY")
        print(f"{'='*30}")
        print(f"Concern Slips created: {len(self.created_concern_slips)}")
        print(f"Job Services created: {len(self.created_job_services)}")
        print(f"Work Order Permits created: {len(self.created_work_order_permits)}")
        
        print(f"\n✅ Request seed data setup complete!")
        print(f"You can now test the three-request system with realistic sample data.")


async def main():
    """Main seeding function"""
    seeder = RequestDataSeeder()
    await seeder.seed_all_request_data()

if __name__ == "__main__":
    asyncio.run(main())

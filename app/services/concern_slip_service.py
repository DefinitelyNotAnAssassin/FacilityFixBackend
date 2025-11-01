from typing import List, Optional
from datetime import datetime
from app.models.database_models import ConcernSlip, Notification
from app.database.database_service import DatabaseService, database_service
from app.database.collections import COLLECTIONS
from app.services.ai_integration_service import AIIntegrationService
from app.services.concern_slip_id_service import concern_slip_id_service
from app.services.notification_manager import NotificationManager
import uuid
import logging
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

class ConcernSlipService:
    def __init__(self):
        self.db = DatabaseService()
        self.ai_service = AIIntegrationService()
        self.notification_manager = NotificationManager()

    async def create_concern_slip(self, reported_by: str, concern_data: dict) -> ConcernSlip:
        """Create a new concern slip - the entry point for repair/maintenance issues"""

        # Fetch reporter profile from Firestore
        success, user_profile, error = await database_service.get_document(
            COLLECTIONS['users'], reported_by
        )
        if not success or not user_profile:
            raise ValueError("Reporter profile not found")

        if user_profile.get("role") != "tenant":
            raise ValueError("Only tenants can submit concern slips")

        concern_slip_id = str(uuid.uuid4())
        formatted_id = await concern_slip_id_service.generate_concern_slip_id()

        concern_slip_data = {
            "id": concern_slip_id,
            "formatted_id": formatted_id,
            "reported_by": reported_by,
            "title": concern_data["title"],
            "description": concern_data["description"],
            "location": concern_data["location"],
            "category": "pending_ai_analysis",
            "priority": "pending_ai_analysis",
            "unit_id": concern_data.get("unit_id"),
            "attachments": concern_data.get("attachments", []),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "ai_processed": False,
            "original_description": concern_data["description"],
            "processed_description": None,
            "detected_language": None,
            "translation_applied": False
        }

        success, doc_id, error = await self.db.create_document("concern_slips", concern_slip_data, concern_slip_id)
        if not success:
            raise Exception(f"Failed to create concern slip: {error}")

        try:
            logger.info(f"Starting AI processing for concern slip {concern_slip_id}")
            ai_result = await self.ai_service.process_concern_description(
                concern_data["description"], 
                concern_slip_id
            )
            
            ai_updates = {
                "category": ai_result.category,
                "priority": ai_result.urgency,
                "ai_processed": True,
                "processed_description": ai_result.processed_text,
                "detected_language": ai_result.detected_language,
                "translation_applied": ai_result.translated,
                "ai_confidence_scores": ai_result.confidence_scores,
                "ai_processing_timestamp": ai_result.processing_timestamp.isoformat(),
                "updated_at": datetime.utcnow()
            }
            
            success, error = await self.db.update_document("concern_slips", concern_slip_id, ai_updates)
            if success:
                logger.info(f"AI processing completed for concern {concern_slip_id}: {ai_result.category}/{ai_result.urgency}")
                concern_slip_data.update(ai_updates)
            else:
                logger.error(f"Failed to update concern slip with AI results: {error}")
                
        except Exception as e:
            logger.error(f"AI processing failed for concern {concern_slip_id}: {str(e)}")
            await self.db.update_document("concern_slips", concern_slip_id, {
                "ai_processed": False,
                "ai_processing_error": str(e),
                "category": concern_data.get("category", "uncategorized"),
                "priority": concern_data.get("priority", "medium"),
                "updated_at": datetime.utcnow()
            })

        # Send notification to admins about new concern slip
        await self.notification_manager.notify_concern_slip_submitted(
            concern_slip_id=concern_slip_id,
            title=concern_slip_data['title'],
            reported_by=reported_by,
            category=concern_slip_data.get('category', 'uncategorized'),
            priority=concern_slip_data.get('priority', 'medium'),
            location=concern_slip_data['location']
        )

        return ConcernSlip(**concern_slip_data)

    async def get_concern_slip(self, concern_slip_id: str) -> Optional[ConcernSlip]:
        """Get concern slip by ID"""
        success, concern_data, error = await self.db.get_document("concern_slips", concern_slip_id)
        
        if not success or not concern_data:
            success, results, error = await self.db.query_documents("concern_slips", [("id", "==", concern_slip_id)])
            if not success or not results:
                return None
            concern_data = results[0]
        
        return ConcernSlip(**concern_data)




    async def get_concern_slip_by_formatted_id(self, concern_slip_id: str) -> Optional[ConcernSlip]:
        """Get concern slip by ID"""
        
        success, results, error = await self.db.query_documents("concern_slips", [("formatted_id", "==", concern_slip_id)])
        if not success or not results:
            return None
        concern_data = results[0]
        return ConcernSlip(**concern_data)





    async def get_all_concern_slips(self, isStaff = False, current_user = {}) -> Optional[ConcernSlip]:
        """Get all concern slips"""
        db = firestore.client()
        concern_data = db.collection("concern_slips")
        concern_data = concern_data.stream() 
        
        
        
        slips = [] 
        
        for slip in concern_data: 
            curr = slip._data  # transform DocumentSnapshot from class to dict 
            curr = ConcernSlip(**curr) # feed to the model
        
            if curr: 
                slips.append(curr)
                
            else: 
                continue
                

        slips.sort(key=lambda slip: slip.created_at, reverse=True)
        
        
        return slips


    async def get_ai_processing_history(self, concern_slip_id: str) -> Optional[dict]:
        """Get AI processing history for a concern slip"""
        try:
            return await self.ai_service.get_processing_history(concern_slip_id)
        except Exception as e:
            logger.error(f"Failed to get AI processing history: {str(e)}")
            return None

    async def reprocess_with_ai(self, concern_slip_id: str, force_translate: bool = False) -> bool:
        """Reprocess a concern slip with AI (admin function)"""
        try:
            concern = await self.get_concern_slip(concern_slip_id)
            if not concern:
                raise ValueError("Concern slip not found")
            
            ai_result = await self.ai_service.process_concern_description(
                concern.original_description or concern.description,
                concern_slip_id,
                force_translate=force_translate
            )
            
            ai_updates = {
                "category": ai_result.category,
                "priority": ai_result.urgency,
                "ai_processed": True,
                "processed_description": ai_result.processed_text,
                "detected_language": ai_result.detected_language,
                "translation_applied": ai_result.translated,
                "ai_confidence_scores": ai_result.confidence_scores,
                "ai_processing_timestamp": ai_result.processing_timestamp.isoformat(),
                "updated_at": datetime.utcnow(),
                "ai_reprocessed": True,
                "ai_reprocessed_at": datetime.utcnow().isoformat()
            }
            
            success, error = await self.db.update_document("concern_slips", concern_slip_id, ai_updates)
            if success:
                logger.info(f"AI reprocessing completed for concern {concern_slip_id}")
                return True
            else:
                logger.error(f"Failed to update concern slip after reprocessing: {error}")
                return False
                
        except Exception as e:
            logger.error(f"AI reprocessing failed for concern {concern_slip_id}: {str(e)}")
            return False

    async def get_concern_slips_by_tenant(self, tenant_id: str) -> List[ConcernSlip]:
        """Get all concern slips submitted by a tenant"""
        success, concerns, error = await self.db.query_documents("concern_slips", [("reported_by", "==", tenant_id)])
        
        if not success or not concerns:
            return []
        
        return [ConcernSlip(**concern) for concern in concerns]

    async def get_concern_slips_by_status(self, status: str) -> List[ConcernSlip]:
        """Get all concern slips with specific status"""
        success, concerns, error = await self.db.query_documents("concern_slips", [("status", "==", status)])
        
        if not success or not concerns:
            return []
        
        return [ConcernSlip(**concern) for concern in concerns]

    async def get_pending_concern_slips(self) -> List[ConcernSlip]:
        """Get all pending concern slips awaiting evaluation"""
        success, concerns, error = await self.db.query_documents("concern_slips", [("status", "==", "pending")])
        
        if not success or not concerns:
            return []
        
        return [ConcernSlip(**concern) for concern in concerns]

    async def get_approved_concern_slips(self) -> List[ConcernSlip]:
        """Get all approved concern slips ready for resolution"""
        success, concerns, error = await self.db.query_documents("concern_slips", [("status", "==", "approved")])
        
        if not success or not concerns:
            return []
        
        return [ConcernSlip(**concern) for concern in concerns]

  
    async def evaluate_concern_slip(
        self,
        concern_slip_id: str,
        evaluated_by: str,
        evaluation_data: dict
    ) -> ConcernSlip:
        """Evaluate concern slip (Admin only) - approve or reject"""
        concern = await self.get_concern_slip(concern_slip_id)
        if not concern:
            raise ValueError("Concern slip not found")
        
        if concern.status not in ["pending", "assessed"]:
            raise ValueError(f"Cannot evaluate concern slip with status: {concern.status}")
        
        # Verify evaluator is admin
        success, admin_profile, error = await self.db.get_document("user_profiles", evaluated_by)
        if not success or not admin_profile or admin_profile.get("role") != "admin":
            raise ValueError("Only admins can evaluate concern slips")
        
        update_data = {
            "status": evaluation_data.get("status"),  # approved or rejected
            "urgency_assessment": evaluation_data.get("urgency_assessment"),
            "resolution_type": evaluation_data.get("resolution_type"),  # job_service or work_permit
            "admin_notes": evaluation_data.get("admin_notes"),
            "evaluated_by": evaluated_by,
            "evaluated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        success, error = await self.db.update_document("concern_slips", concern_slip_id, update_data)
        if not success:
            raise Exception(f"Failed to evaluate concern slip: {error}")
        
        # Send notification to tenant about evaluation
        await self.notification_manager.notify_concern_slip_evaluated(
            concern_slip_id=concern_slip_id,
            title=concern.title,
            tenant_id=concern.reported_by,
            status=evaluation_data.get("status"),
            resolution_type=evaluation_data.get("resolution_type"),
            admin_notes=evaluation_data.get("admin_notes")
        )
        
        return await self.get_concern_slip(concern_slip_id)

    async def assign_staff_for_assessment(
        self, 
        concern_slip_id: str, 
        assigned_to: str,
        assigned_by: str
    ) -> ConcernSlip:
        """Assign a staff member to assess a concern slip"""
        logger.info(f"[v0] Starting staff assignment - concern_slip_id: {concern_slip_id}, assigned_to: {assigned_to}, assigned_by: {assigned_by}")
        
        concern = await self.get_concern_slip(concern_slip_id)
        if not concern:
            logger.error(f"[v0] Concern slip not found: {concern_slip_id}")
            raise ValueError("Concern slip not found")
        
        logger.info(f"[v0] Concern slip found - status: {concern.status}")
        
        if concern.status not in ["pending", "evaluated"]:
            logger.error(f"[v0] Invalid status for assignment: {concern.status}")
            raise ValueError(f"Cannot assign staff to concern slip with status: {concern.status}")
        
        logger.info(f"[v0] Checking staff member in 'users' collection: {assigned_to}")
        success, staff_profile, error = await self.db.query_documents("users", [("user_id", "==", assigned_to)])
        staff_profile = staff_profile[0] if success and staff_profile else None
        logger.info(f"[v0] Users collection query - success: {success}, profile found: {staff_profile is not None}, error: {error}")
        
        if staff_profile:
            logger.info(f"[v0] Staff profile from users: {staff_profile}")
        
        if not success or not staff_profile:
            # Try user_profiles collection as fallback
            logger.info(f"[v0] Trying 'user_profiles' collection as fallback")
            success, staff_profile, error = await self.db.get_document("user_profiles", assigned_to)
            logger.info(f"[v0] User_profiles collection query - success: {success}, profile found: {staff_profile is not None}, error: {error}")
            
            if staff_profile:
                logger.info(f"[v0] Staff profile from user_profiles: {staff_profile}")
        
        if not success or not staff_profile:
            logger.error(f"[v0] Staff member not found in either collection: {assigned_to}")
            raise ValueError(f"Staff member not found: {assigned_to}")
        
        staff_role = staff_profile.get("role")
        logger.info(f"[v0] Staff role from profile: {staff_role}")
        
        if staff_role != "staff":
            logger.error(f"[v0] User is not a staff member - role: {staff_role}")
            raise ValueError(f"Assigned user must be a staff member (current role: {staff_role})")
        
        logger.info(f"[v0] Staff verification successful - proceeding with assignment")
        
        update_data = {
            "assigned_to": assigned_to,
            "assigned_at": datetime.utcnow(),
            "status": "assigned",
            "updated_at": datetime.utcnow()
        }
        
        logger.info(f"[v0] Updating concern slip with data: {update_data}")
        success, error = await self.db.update_document("concern_slips", concern_slip_id, update_data)
        
        if not success:
            logger.error(f"[v0] Failed to update concern slip: {error}")
            raise Exception(f"Failed to assign staff: {error}")
        
        logger.info(f"[v0] Concern slip updated successfully")
        
        # Send notification to staff about assignment
        await self.notification_manager.notify_concern_slip_assigned(
            concern_slip_id=concern_slip_id,
            title=concern.title,
            staff_id=assigned_to,
            assigned_by=assigned_by,
            category=concern.category,
            priority=concern.priority,
            location=concern.location
        )
        
        logger.info(f"[v0] Staff assignment completed successfully")
        
        # Get updated concern slip
        return await self.get_concern_slip(concern_slip_id)

    async def submit_staff_assessment(
        self,
        concern_slip_id: str,
        assessed_by: str,
        assessment: str,
        resolution_type: str,
        attachments: List[str] = []
    ) -> ConcernSlip:
        """
        Staff submits assessment with resolution type.
        Status will be set to 'sent' and the concern slip will be ready for job service or work order creation.
        """
        concern = await self.get_concern_slip(concern_slip_id)
        (success, staff_id, error) = await database_service.get_document("users", assessed_by)
        
        if not concern:
            raise ValueError("Concern slip not found")
        
        if concern.status != "assigned":
            raise ValueError(f"Cannot submit assessment for concern slip with status: {concern.status}")
        
        if concern.assigned_to != staff_id.get('staff_id'):
            raise ValueError("Only the assigned staff member can submit assessment")
        
        # Validate resolution_type
        if resolution_type not in ["job_service", "work_order"]:
            raise ValueError(f"Invalid resolution type: {resolution_type}. Must be 'job_service' or 'work_order'")
        
        update_data = {
            "staff_assessment": assessment,
            "assessment_attachments": attachments,
            "assessed_by": staff_id.get('staff_id'),
            "assessed_at": datetime.utcnow(),
            "resolution_type": resolution_type,
            "resolution_set_by": staff_id.get('staff_id'),
            "resolution_set_at": datetime.utcnow(),
            "status": "sent",  # Always set to 'sent' since resolution type is always provided
            "updated_at": datetime.utcnow()
        }
        
        success, error = await self.db.update_document("concern_slips", concern_slip_id, update_data)
        if not success:
            raise Exception(f"Failed to submit assessment: {error}")
        
        # Send notification to admins about completed assessment
        await self.notification_manager.notify_concern_slip_assessed(
            concern_slip_id=concern_slip_id,
            title=concern.title,
            staff_id=staff_id.get('staff_id'),
            assessment=assessment,
            resolution_type=resolution_type
        )
        
        return await self.get_concern_slip(concern_slip_id)

    async def set_resolution_type(
        self,
        concern_slip_id: str,
        resolution_type: str,
        admin_user_id: str,
        admin_notes: Optional[str] = None
    ) -> ConcernSlip:
        """Admin sets resolution type  assessed concern slip (job_service or work_order)"""
        concern = await self.get_concern_slip_by_formatted_id(concern_slip_id)
        if not concern:
            raise ValueError("Concern slip not found")
        
        if concern.status != "assessed":
            raise ValueError(f"Cannot set resolution type for concern slip with status: {concern.status}")
        
        # Validate resolution type
        if resolution_type not in ["job_service", "work_order"]:
            raise ValueError(f"Invalid resolution type: {resolution_type}. Must be 'job_service' or 'work_order'")
        
        # Verify admin role
        success, admin_profile, error = await self.db.get_document("users", admin_user_id)
        if not success or not admin_profile or admin_profile.get("role") != "admin":
            raise ValueError("Only admins can set resolution type")
        
        update_data = {
            "resolution_type": resolution_type,
            "resolution_set_by": admin_user_id,
            "resolution_set_at": datetime.utcnow(),
            "status": "sent",
            "updated_at": datetime.utcnow()
        }
        
        if admin_notes:
            update_data["admin_notes"] = admin_notes
        
        success, error = await self.db.update_document("concern_slips", concern.id, update_data)
        if not success:
            raise Exception(f"Failed to set resolution type: {error}")
        
        # Send notification to tenant about resolution type
        await self.notification_manager.notify_concern_slip_resolution_set(
            concern_slip_id=concern_slip_id,
            title=concern.title,
            tenant_id=concern.reported_by,
            resolution_type=resolution_type,
            admin_notes=admin_notes
        )
        
        return await self.get_concern_slip_by_formatted_id(concern_slip_id)

    async def return_to_tenant(
        self,
        concern_slip_id: str,
        returned_by: str
    ) -> ConcernSlip:
        """Admin returns assessed concern slip to tenant"""
        concern = await self.get_concern_slip(concern_slip_id)
        if not concern:
            raise ValueError("Concern slip not found")
        
        if concern.status != "assessed":
            raise ValueError(f"Cannot return concern slip with status: {concern.status}")
        
        update_data = {
            "status": "returned_to_tenant",
            "returned_to_tenant_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        success, error = await self.db.update_document("concern_slips", concern_slip_id, update_data)
        if not success:
            raise Exception(f"Failed to return to tenant: {error}")
        
        # Send notification to tenant about return
        await self.notification_manager.notify_concern_slip_returned_to_tenant(
            concern_slip_id=concern_slip_id,
            title=concern.title,
            tenant_id=concern.reported_by,
            assessment=concern.staff_assessment,
            recommendation=concern.staff_recommendation
        )
        
        return await self.get_concern_slip(concern_slip_id)

    async def get_concern_slips_by_staff(self, user_id) -> List[ConcernSlip]:
        """Get all concern slips assigned to a staff member"""
        
        
        (success,current_user,error) = await database_service.get_document("users", user_id)
        print(current_user)
        
        
        
        
        
        
        staff_id = current_user.get('staff_id')
        
        success, concerns, error = await self.db.query_documents(
            "concern_slips", 
            [("assigned_to", "==", staff_id)]
        )
        
        if not success:
            logger.error(f"[v0] Failed to query concern slips for staff {staff_id}: {error}")
            return []
        
        if not concerns:
            logger.info(f"[v0] No concern slips found for staff {staff_id}")
            return []
        
        logger.info(f"[v0] Found {len(concerns)} concern slips for staff {staff_id}")
        concern_slip_objects = [ConcernSlip(**concern) for concern in concerns]
        
        # Sort by creation date (latest first)
        concern_slip_objects.sort(key=lambda slip: slip.created_at, reverse=True)
        
        return concern_slip_objects

    async def update_concern_slip_status(self, concern_slip_id: str, status: str, updated_by: str, notes: Optional[str] = None) -> ConcernSlip:
        """Update concern slip status"""
        
        # Verify concern slip exists
        success, concern_slip, error = await self.db.get_document("concern_slips", concern_slip_id)
        if not success or not concern_slip:
            raise ValueError("Concern slip not found")

        update_data = {
            "status": status,
            "updated_by": updated_by,
            "updated_at": datetime.utcnow()
        }
        
        if notes:
            update_data["notes"] = notes

        await self.db.update_document("concern_slips", concern_slip_id, update_data)

        # Get updated concern slip
        success, updated_concern, error = await self.db.get_document("concern_slips", concern_slip_id)
        if not success or not updated_concern:
            raise ValueError("Failed to retrieve updated concern slip")
        return ConcernSlip(**updated_concern)
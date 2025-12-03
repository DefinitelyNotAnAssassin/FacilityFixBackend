from typing import List, Optional
from datetime import datetime
from app.models.database_models import WorkOrderPermit, UserProfile, ConcernSlip, Notification
from app.database.database_service import DatabaseService
from app.services.user_id_service import UserIdService
from app.services.notification_manager import notification_manager
from app.services.concern_slip_service import ConcernSlipService
from app.models.notification_models import NotificationType
import uuid
from app.services.work_order_permit_id_service import work_order_permit_id_service


class WorkOrderPermitService:
    def __init__(self):
        self.db = DatabaseService()
        self.user_service = UserIdService()
        self.concern_slip_service = ConcernSlipService()

    async def create_work_order_permit(self, concern_slip_id: str, requested_by: str, permit_data: dict) -> WorkOrderPermit:
        """Create a new work order permit for external worker authorization"""
        
        success, concern_slip, error = await self.db.get_document("concern_slips", concern_slip_id)
        if not success or not concern_slip:
            raise ValueError("Concern slip not found")
        
        if concern_slip.get("status") != "approved":
            raise ValueError("Concern slip must be approved before creating work order permit")
        
        # Verify requester is tenant and owns the unit
        requester_profile = await self.user_service.get_user_profile(requested_by)
        if not requester_profile or requester_profile.role != "tenant":
            raise ValueError("Only tenants can request work order permits")

        # Format title similar to job service: "Work Order for: {concern_slip.title}"
        concern_slip_title = concern_slip.get("title", "Untitled Concern")
        
        # Verify concern slip has a priority (should always be set by AI analysis)
        priority = concern_slip.get("priority")
        if not priority:
            raise ValueError(f"Concern slip {concern_slip_id} has no priority - AI analysis may have failed")
        
        # Generate formatted work order permit ID (WOP-YYYY-NNNNN)
        formatted_id = await work_order_permit_id_service.generate_work_order_permit_id()

        permit_data_complete = {
            "id": formatted_id,
            "formatted_id": formatted_id,
            "concern_slip_id": concern_slip_id,
            "title": f"Work Order for: {concern_slip_title}",
            "requested_by": requested_by,
            "unit_id": permit_data["unit_id"],
            "work_order_type": permit_data["work_order_type"],
            "contractor_name": permit_data["contractor_name"],
            "contractor_contact": permit_data["contractor_contact"],
            "contractor_email": permit_data.get("contractor_email"),
            "tenant_additional_notes": permit_data["tenant_additional_notes"],
            "proposed_start_date": permit_data["proposed_start_date"],
            "proposed_end_date": permit_data["proposed_end_date"],
            "admin_notes": permit_data["admin_notes"],
            "priority": priority,  # From AI-classified concern slip
            "status": "pending",
            "request_type": "Work Order",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        create_success, doc_id, create_error = await self.db.create_document(
            "work_order_permits", 
            permit_data_complete, 
            permit_data_complete["id"]
        )
        if not create_success:
            raise Exception(f"Failed to create work order permit: {create_error}")
        
        # Update concern slip status to completed and set resolution type
        update_success, update_error = await self.db.update_document("concern_slips", concern_slip_id, {
            "status": "completed",
            "resolution_type": "work_permit",
            "updated_at": datetime.utcnow()
        })
        if not update_success:
            raise Exception(f"Failed to update concern slip: {update_error}")

        # Send notification to admin for approval
        # Notify admins about new permit request
        await notification_manager.notify_permit_created(
            permit_id=permit_data_complete["id"],
            requester_id=requested_by,
            contractor_name=permit_data["contractor_name"],
            work_description=permit_data["work_description"]
        )

        return WorkOrderPermit(**permit_data_complete)

    async def approve_permit(self, permit_id: str, approved_by: str, conditions: Optional[str] = None) -> WorkOrderPermit:
        """Approve work order permit (Admin only)"""
        
        # Verify approver is admin
        approver_profile = await self.user_service.get_user_profile(approved_by)
        if not approver_profile or approver_profile.role != "admin":
            raise ValueError("Only admins can approve work order permits")

        success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not permits_data or len(permits_data) == 0:
            raise ValueError("Work order permit not found")

        permit_data = permits_data[0]
        
        # Get the Firestore document ID from the query result
        doc_id = permit_data.get("_doc_id") or permit_id
        
        update_data = {
            "status": "approved",
            "approved_by": approved_by,
            "approval_date": datetime.utcnow(),
            "permit_conditions": conditions,
            "updated_at": datetime.utcnow()
        }

        success, error = await self._update_permit_by_doc_id(doc_id, update_data)
        if not success:
            raise Exception(f"Failed to update permit: {error}")
        
        # Notify requester about approval
        await notification_manager.notify_permit_approved(
            permit_id=permit_id,
            requester_id=permit_data.get("requested_by"),
            assignee_id=None,  # You can add assignee logic if needed
            approved_by=approved_by,
            contractor_name=permit_data.get("contractor_name", ""),
            conditions=conditions
        )

        # Get updated permit
        success, updated_permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not updated_permits_data or len(updated_permits_data) == 0:
            raise Exception("Failed to retrieve updated permit")
        
        return WorkOrderPermit(**updated_permits_data[0])

    async def deny_permit(self, permit_id: str, denied_by: str, reason: str) -> WorkOrderPermit:
        """Deny work order permit (Admin only)"""
        
        # Verify denier is admin
        denier_profile = await self.user_service.get_user_profile(denied_by)
        if not denier_profile or denier_profile.role != "admin":
            raise ValueError("Only admins can deny work order permits")

        success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not permits_data or len(permits_data) == 0:
            raise ValueError("Work order permit not found")

        permit_data = permits_data[0]
        
        # Get the Firestore document ID from the query result
        doc_id = permit_data.get("_doc_id") or permit_id
        
        update_data = {
            "status": "denied",
            "approved_by": denied_by,  # Track who made the decision
            "approval_date": datetime.utcnow(),
            "denial_reason": reason,
            "updated_at": datetime.utcnow()
        }

        success, error = await self._update_permit_by_doc_id(doc_id, update_data)
        if not success:
            raise Exception(f"Failed to update permit: {error}")
        
        # Notify requester about rejection
        await notification_manager.notify_permit_rejected(
            permit_id=permit_id,
            requester_id=permit_data.get("requested_by"),
            rejected_by=denied_by,
            reason=reason,
            contractor_name=permit_data.get("contractor_name", "")
        )

        # Get updated permit
        success, updated_permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not updated_permits_data or len(updated_permits_data) == 0:
            raise Exception("Failed to retrieve updated permit")
        
        return WorkOrderPermit(**updated_permits_data[0])

    async def update_permit_status(self, permit_id: str, status: str, updated_by: str, notes: Optional[str] = None) -> WorkOrderPermit:
        """Update work order permit status"""
        
        valid_statuses = ["pending", "approved", "denied", "completed"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

        success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not permits_data or len(permits_data) == 0:
            raise ValueError("Work order permit not found")

        permit_data = permits_data[0]
        
        # Get the Firestore document ID from the query result
        doc_id = permit_data.get("_doc_id") or permit_id
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }

        # Add timestamp for specific status changes
        if status == "completed":
            update_data["actual_completion_date"] = datetime.utcnow()

        # Add admin notes if provided
        if notes:
            update_data["admin_notes"] = notes

        success, error = await self._update_permit_by_doc_id(doc_id, update_data)
        if not success:
            raise Exception(f"Failed to update permit status: {error}")

        # Send notifications based on status
        permit_data = permits_data[0]
        if status == "completed":
            # Update concern slip status to completed if it exists
            concern_slip_id = permit_data.get("concern_slip_id")
            if concern_slip_id:
                success, concern_slip_data, error = await self.db.get_document("concern_slips", concern_slip_id)
                if success and concern_slip_data:
                    await self.db.update_document("concern_slips", concern_slip_id, {
                        "status": "completed",
                        "updated_at": datetime.utcnow()
                    })
            
            # Notify admin and tenant of completion
            from app.services.notification_manager import notification_manager
            contractor_name = permit_data.get("contractor_name") or permit_data.get("title") or permit_data.get("description") or "Work Order"
            await notification_manager.notify_permit_completed(
                permit_id=permit_id,
                contractor_name=contractor_name,
                completion_notes=notes
            )
            
            # Notify tenant of completion
            await self._send_tenant_notification(
                permit_data.get("requested_by"),
                permit_id,
                "Your external work has been marked as completed"
            )

        # Get updated permit
        success, updated_permits_data, error = await self.db.query_documents("work_order_permits", [("id", permit_id)])
        if not success or not updated_permits_data or len(updated_permits_data) == 0:
            raise Exception("Failed to retrieve updated permit")
        
        return WorkOrderPermit(**updated_permits_data[0])

    async def start_work(self, permit_id: str, started_by: str) -> WorkOrderPermit:
        """Mark work as started (updates actual start date)"""
        
        success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not permits_data or len(permits_data) == 0:
            raise ValueError("Work order permit not found")
        
        permit_data = permits_data[0]
        if permit_data.get("status") != "approved":
            raise ValueError("Work can only be started on approved permits")

        # Get the Firestore document ID from the query result
        doc_id = permit_data.get("_doc_id") or permit_id
        
        update_data = {
            "actual_start_date": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        success, error = await self._update_permit_by_doc_id(doc_id, update_data)
        if not success:
            raise Exception(f"Failed to start work: {error}")

        # Send notification to admin (using generic notification for now)
        await notification_manager.create_notification(
            notification_type=NotificationType.PERMIT_CREATED,  # Using this as generic permit status update
            recipient_id="admin",  # Will be handled by the manager to send to all admins
            title="Permit Work Started",
            message=f"External work has started for permit {permit_id}",
            related_entity_type="work_order_permit",
            related_entity_id=permit_id
        )

        # Get updated permit
        success, updated_permits_data, error = await self.db.query_documents("work_order_permits", [("id", permit_id)])
        if not success or not updated_permits_data or len(updated_permits_data) == 0:
            raise Exception("Failed to retrieve updated permit")
        
        permit = permits_data[0]
        await self._enrich_permit_with_user_info(permit)
        
        return WorkOrderPermit(**permit)
    
    async def _enrich_permit_with_user_info(self, permit: dict) -> None:
        """Helper method to enrich permit with user names"""
        # Enrich requested_by with tenant name
        if permit.get("requested_by"):
            requested_by_id = permit.get("requested_by")
            try:
                user_profile = await self.user_service.get_user_profile(requested_by_id)
                if user_profile:
                    permit['requested_by_name'] = f"{user_profile.first_name} {user_profile.last_name}".strip()
                else:
                    permit['requested_by_name'] = requested_by_id
            except Exception:
                permit['requested_by_name'] = requested_by_id
        
        # Enrich approved_by with admin name
        if permit.get("approved_by"):
            approved_by_id = permit.get("approved_by")
            try:
                user_profile = await self.user_service.get_user_profile(approved_by_id)
                if user_profile:
                    permit['approved_by_name'] = f"{user_profile.first_name} {user_profile.last_name}".strip()
                else:
                    permit['approved_by_name'] = approved_by_id
            except Exception:
                permit['approved_by_name'] = approved_by_id

    async def get_work_order_permit(self, permit_id: str) -> Optional[WorkOrderPermit]:
        """Get work order permit by ID"""
        success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
        if not success or not permits_data or len(permits_data) == 0:
            return None
        return WorkOrderPermit(**permits_data[0])

    async def get_permits_by_tenant(self, tenant_id: str) -> List[WorkOrderPermit]:
        """Get all work order permits requested by a tenant"""
        success, permits, error = await self.db.query_documents("work_order_permits", [("requested_by", "==", tenant_id)])
        if not success:
            raise Exception(f"Failed to query permits: {error}")
        return [WorkOrderPermit(**permit) for permit in permits]

    async def get_permits_by_status(self, status: str) -> List[WorkOrderPermit]:
        """Get all work order permits with specific status"""
        success, permits, error = await self.db.query_documents("work_order_permits", [("status", "==", status)])
        if not success:
            raise Exception(f"Failed to query permits: {error}")
        return [WorkOrderPermit(**permit) for permit in permits]

    async def get_pending_permits(self) -> List[WorkOrderPermit]:
        """Get all pending work order permits (Admin view)"""
        success, permits, error = await self.db.query_documents("work_order_permits", [("status", "==", "pending")])
        if not success:
            raise Exception(f"Failed to query pending permits: {error}")
        return [WorkOrderPermit(**permit) for permit in permits]

    async def get_all_permits(self) -> List[dict]:
        """Get all work order permits (Admin only)"""
        try:
            permits = await self.db.get_all_documents("work_order_permits")
            if not permits:
                return []
            
            # Return permits as-is without enrichment to avoid serialization errors
            # Enrichment logic can be added to the route if needed
            return permits
        except Exception as e:
            print(f"[WorkOrderPermitService] Error in get_all_permits: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
            
            print(f"[GET_ALL_PERMITS] Returning {len(normalized_permits)} normalized permits")
            
            # Return permits as-is without enrichment to avoid serialization errors
            # Enrichment logic can be added to the route if needed
            return normalized_permits
        except Exception as e:
            print(f"[WorkOrderPermitService] Error in get_all_permits: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    async def _update_permit_by_doc_id(self, document_id: str, update_data: dict) -> tuple[bool, str]:
        """Helper method to update work order permit by document ID"""
        try:
            # Update directly using the provided Firestore document ID
            success, error = await self.db.update_document("work_order_permits", document_id, update_data)
            if not success:
                return False, f"Failed to update work order permit: {error}"
            return True, ""

        except Exception as e:
            return False, str(e)

    async def _send_tenant_notification(self, tenant_id: str, permit_id: str, message: str):
        """Helper method to send notification to tenant"""
        await notification_manager.create_notification(
            notification_type=NotificationType.PERMIT_STATUS_UPDATE,
            recipient_id=tenant_id,
            title="Permit Status Update",
            message=message,
            related_entity_type="work_order_permit",
            related_entity_id=permit_id
        )

    async def bulk_approve_permits(self, permit_ids: List[str], approved_by: str, conditions: Optional[str] = None) -> dict:
        """Approve multiple work order permits in bulk (Admin only)"""
        
        # Verify approver is admin
        approver_profile = await self.user_service.get_user_profile(approved_by)
        if not approver_profile or approver_profile.role != "admin":
            raise ValueError("Only admins can approve work order permits")

        approved_count = 0
        failed_count = 0
        errors = []
        failed_permits = []

        for permit_id in permit_ids:
            try:
                # Get permit data
                success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
                if not success or not permits_data or len(permits_data) == 0:
                    failed_count += 1
                    errors.append(f"Permit {permit_id}: Not found")
                    failed_permits.append(permit_id)
                    continue

                permit_data = permits_data[0]
                
                # Get the Firestore document ID from the query result
                doc_id = permit_data.get("_doc_id") or permit_id
                
                # Check if permit is in a valid state to approve
                current_status = permit_data.get("status")
                if current_status not in ["pending", "returned_to_tenant"]:
                    failed_count += 1
                    errors.append(f"Permit {permit_id}: Cannot approve permit with status '{current_status}'")
                    failed_permits.append(permit_id)
                    continue
                
                update_data = {
                    "status": "approved",
                    "approved_by": approved_by,
                    "approval_date": datetime.utcnow(),
                    "permit_conditions": conditions,
                    "updated_at": datetime.utcnow()
                }

                success, error = await self._update_permit_by_doc_id(doc_id, update_data)
                if not success:
                    failed_count += 1
                    errors.append(f"Permit {permit_id}: {error}")
                    failed_permits.append(permit_id)
                    continue
                
                # Notify requester about approval
                await notification_manager.notify_permit_approved(
                    permit_id=permit_id,
                    requester_id=permit_data.get("requested_by"),
                    assignee_id=None,
                    approved_by=approved_by,
                    contractor_name=permit_data.get("contractor_name", ""),
                    conditions=conditions
                )

                approved_count += 1

            except Exception as e:
                failed_count += 1
                errors.append(f"Permit {permit_id}: {str(e)}")
                failed_permits.append(permit_id)

        return {
            "approved_count": approved_count,
            "failed_count": failed_count,
            "errors": errors,
            "failed_permits": failed_permits,
            "message": f"Bulk approval completed: {approved_count} approved, {failed_count} failed"
        }

    async def bulk_reject_permits(self, permit_ids: List[str], rejected_by: str, reason: str) -> dict:
        """Reject multiple work order permits in bulk (Admin only)"""
        
        # Verify rejector is admin
        rejector_profile = await self.user_service.get_user_profile(rejected_by)
        if not rejector_profile or rejector_profile.role != "admin":
            raise ValueError("Only admins can reject work order permits")

        rejected_count = 0
        failed_count = 0
        errors = []
        failed_permits = []

        for permit_id in permit_ids:
            try:
                # Get permit data
                success, permits_data, error = await self.db.query_documents("work_order_permits", [("id", "==", permit_id)])
                if not success or not permits_data or len(permits_data) == 0:
                    failed_count += 1
                    errors.append(f"Permit {permit_id}: Not found")
                    failed_permits.append(permit_id)
                    continue

                permit_data = permits_data[0]
                
                # Get the Firestore document ID from the query result
                doc_id = permit_data.get("_doc_id") or permit_id
                
                # Check if permit is in a valid state to reject
                current_status = permit_data.get("status")
                if current_status not in ["pending", "returned_to_tenant"]:
                    failed_count += 1
                    errors.append(f"Permit {permit_id}: Cannot reject permit with status '{current_status}'")
                    failed_permits.append(permit_id)
                    continue
                
                update_data = {
                    "status": "rejected",
                    "rejected_by": rejected_by,
                    "rejection_date": datetime.utcnow(),
                    "rejection_reason": reason,
                    "updated_at": datetime.utcnow()
                }

                success, error = await self._update_permit_by_doc_id(doc_id, update_data)
                if not success:
                    failed_count += 1
                    errors.append(f"Permit {permit_id}: {error}")
                    failed_permits.append(permit_id)
                    continue
                
                # Notify requester about rejection
                await notification_manager.notify_permit_rejected(
                    permit_id=permit_id,
                    requester_id=permit_data.get("requested_by"),
                    rejected_by=rejected_by,
                    reason=reason,
                    contractor_name=permit_data.get("contractor_name", "")
                )

                rejected_count += 1

            except Exception as e:
                failed_count += 1
                errors.append(f"Permit {permit_id}: {str(e)}")
                failed_permits.append(permit_id)

        return {
            "rejected_count": rejected_count,
            "failed_count": failed_count,
            "errors": errors,
            "failed_permits": failed_permits,
            "message": f"Bulk rejection completed: {rejected_count} rejected, {failed_count} failed"
        }

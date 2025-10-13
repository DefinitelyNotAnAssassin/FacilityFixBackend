from typing import List, Optional
from datetime import datetime
from app.models.database_models import JobService, UserProfile, ConcernSlip, Notification
from app.database.database_service import DatabaseService
from app.services.user_id_service import UserIdService
import uuid

class JobServiceService:
    def __init__(self):
        self.db = DatabaseService()
        self.user_service = UserIdService()

    async def create_job_service(self, concern_slip_id: str, created_by: str, job_data: dict) -> JobService:
        """Create a new job service from an approved concern slip"""
        
        # Verify concern slip exists and is approved
        success, concern_slip_data, error = await self.db.get_document("concern_slips", concern_slip_id)
        if not success or not concern_slip_data:
            raise ValueError("Concern slip not found")
        
        if concern_slip_data.get("status") != "approved":
            raise ValueError("Concern slip must be approved before creating job service")
        
        # Verify creator is admin
        creator_profile = await self.user_service.get_user_profile(created_by)
        if not creator_profile or creator_profile.role != "admin":
            raise ValueError("Only admins can create job services")

        job_service_id = f"job_{str(uuid.uuid4())[:8]}"

        job_service_data = {
            "id": job_service_id,
            "concern_slip_id": concern_slip_id,
            "created_by": created_by,
            "title": job_data.get("title") or concern_slip_data.get("title"),
            "description": job_data.get("description") or concern_slip_data.get("description"),
            "location": job_data.get("location") or concern_slip_data.get("location"),
            "category": job_data.get("category") or concern_slip_data.get("category"),
            "priority": job_data.get("priority") or concern_slip_data.get("priority"),
            "status": "assigned",
            "assigned_to": job_data.get("assigned_to"),
            "scheduled_date": job_data.get("scheduled_date"),
            "estimated_hours": job_data.get("estimated_hours"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Create job service
        success, doc_id, error = await self.db.create_document("job_services", job_service_data, job_service_id)
        if not success:
            raise ValueError(f"Failed to create job service: {error}")
        
        # Update concern slip status
        success, error = await self.db.update_document("concern_slips", concern_slip_id, {
            "resolution_type": "job_service",
            "updated_at": datetime.utcnow()
        })

        # Send notification to assigned staff
        if job_service_data.get("assigned_to"):
            await self._send_assignment_notification(
                job_service_data["assigned_to"], 
                job_service_data["id"],
                job_service_data["title"]
            )

        # Send notification to tenant
        await self._send_tenant_notification(
            concern_slip_data.get("reported_by"),
            job_service_data["id"],
            "Your concern has been assigned to our internal staff"
        )

        return JobService(**job_service_data)

    async def assign_job_service(self, job_service_id: str, assigned_to: str, assigned_by: str) -> JobService:
        """Assign job service to internal staff member"""
        
        # Verify assigner is admin
        assigner_profile = await self.user_service.get_user_profile(assigned_by)
        if not assigner_profile or assigner_profile.role != "admin":
            raise ValueError("Only admins can assign job services")

        if not assigned_to.startswith("S-"):
            raise ValueError("Job services can only be assigned to staff members")

        # Verify assignee is staff'
        db = DatabaseService() 
        print("ASSIGNED TO: ", assigned_to)
        success, assignee, error = await db.query_collection("users", [('staff_id', '==', assigned_to)])
        print("ASSIGNEE",assignee)
        if not assignee or assignee[0].get('role') != "staff":
            raise ValueError("Job services can only be assigned to staff members")

        # Try to find in job_services collection first
        success, jobs_data, error = await self.db.query_documents("job_services", [("id", job_service_id)])
        
        # If not found in job_services, try job_service_requests collection
        if not success or not jobs_data or len(jobs_data) == 0:
            success, jobs_data, error = await self.db.query_documents("job_service_requests", [("id", job_service_id)])
            collection_name = "job_service_requests"
        else:
            collection_name = "job_services"
        
        if not success or not jobs_data or len(jobs_data) == 0:
            raise ValueError("Job service not found")
        
        job_service_data = jobs_data[0]

        # Update job service using custom ID
        update_data = {
            "assigned_to": assigned_to,  # Use the staff_id directly (e.g., S-0001)
            "status": "assigned",
            "updated_at": datetime.utcnow()
        }

        success, error = await self._update_job_service_by_custom_id_in_collection(
            job_service_id, update_data, collection_name
        )
        if not success:
            raise ValueError(f"Failed to assign job service: {error}")
        
        # Send notification to assigned staff
        await self._send_assignment_notification(
            assigned_to, 
            job_service_id,
            job_service_data.get("title", "Job Service Assignment")
        )

        # Get updated job service
        success, updated_jobs_data, error = await self.db.query_documents(collection_name, [("id", job_service_id)])
        if not success or not updated_jobs_data or len(updated_jobs_data) == 0:
            raise ValueError("Failed to retrieve updated job service")
            
        return JobService(**updated_jobs_data[0])

    async def update_job_status(self, job_service_id: str, status: str, updated_by: str, notes: Optional[str] = None) -> JobService:
        """Update job service status"""
        
        valid_statuses = ["assigned", "in_progress", "completed", "closed"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

        # Try to find in job_services collection first
        success, jobs_data, error = await self.db.query_documents("job_services", [("id", job_service_id)])
        
        # If not found in job_services, try job_service_requests collection
        if not success or not jobs_data or len(jobs_data) == 0:
            success, jobs_data, error = await self.db.query_documents("job_service_requests", [("id", job_service_id)])
            collection_name = "job_service_requests"
        else:
            collection_name = "job_services"

        if not success or not jobs_data or len(jobs_data) == 0:
            raise ValueError("Job service not found")

        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }

        # Add timestamp for specific status changes
        if status == "in_progress":
            update_data["started_at"] = datetime.utcnow()
        elif status == "completed":
            update_data["completed_at"] = datetime.utcnow()

        # Add notes if provided
        if notes:
            if status == "completed":
                update_data["completion_notes"] = notes
            else:
                update_data["staff_notes"] = notes

        success, error = await self._update_job_service_by_custom_id_in_collection(job_service_id, update_data, collection_name)
        if not success:
            raise ValueError(f"Failed to update job status: {error}")

        # Send notifications based on status
        job_service_data = jobs_data[0]
        if status == "completed":
            concern_slip_id = job_service_data.get("concern_slip_id")
            if concern_slip_id:
                success, concern_slip_data, error = await self.db.get_document("concern_slips", concern_slip_id)
                
                if success and concern_slip_data:
                    # Update concern slip status to completed
                    await self.db.update_document("concern_slips", concern_slip_id, {
                        "status": "completed",
                        "updated_at": datetime.utcnow()
                    })
                    
                    # Notify tenant of completion
                    await self._send_tenant_notification(
                        concern_slip_data.get("reported_by"),
                        job_service_id,
                        f"Your repair request has been completed: {job_service_data.get('title')}"
                    )

        # Get updated job service
        success, updated_jobs_data, error = await self.db.query_documents(collection_name, [("id", job_service_id)])
        if not success or not updated_jobs_data or len(updated_jobs_data) == 0:
            raise ValueError("Failed to retrieve updated job service")
            
        return JobService(**updated_jobs_data[0])

    async def add_work_notes(self, job_service_id: str, notes: str, added_by: str) -> JobService:
        """Add work notes to job service"""
        
        # Try to find in job_services collection first
        success, jobs_data, error = await self.db.query_documents("job_services", [("id", job_service_id)])
        
        # If not found in job_services, try job_service_requests collection
        if not success or not jobs_data or len(jobs_data) == 0:
            success, jobs_data, error = await self.db.query_documents("job_service_requests", [("id", job_service_id)])
            collection_name = "job_service_requests"
        else:
            collection_name = "job_services"

        if not success or not jobs_data or len(jobs_data) == 0:
            raise ValueError("Job service not found")

        job_service_data = jobs_data[0]
        current_notes = job_service_data.get("staff_notes", "")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        user_profile = await self.user_service.get_user_profile(added_by)
        user_name = f"{user_profile.first_name} {user_profile.last_name}" if user_profile else "Unknown"
        
        new_note = f"\n[{timestamp}] {user_name}: {notes}"
        updated_notes = current_notes + new_note

        success, error = await self._update_job_service_by_custom_id_in_collection(job_service_id, {
            "staff_notes": updated_notes,
            "updated_at": datetime.utcnow()
        }, collection_name)
        
        if not success:
            raise ValueError(f"Failed to add work notes: {error}")

        # Get updated job service
        success, updated_jobs_data, error = await self.db.query_documents(collection_name, [("id", job_service_id)])
        if not success or not updated_jobs_data or len(updated_jobs_data) == 0:
            raise ValueError("Failed to retrieve updated job service")
            
        return JobService(**updated_jobs_data[0])

    async def get_job_service(self, job_service_id: str) -> Optional[JobService]:
        """Get job service by ID from either collection"""
        # Try job_services collection first
        success, jobs_data, error = await self.db.query_documents("job_services", [("id", job_service_id)])
        if success and jobs_data and len(jobs_data) > 0:
            return JobService(**jobs_data[0])
        
        # If not found, try job_service_requests collection
        success, jobs_data, error = await self.db.query_documents("job_service_requests", [("id", job_service_id)])
        if success and jobs_data and len(jobs_data) > 0:
            return JobService(**jobs_data[0])
        
        return None

    async def get_job_services_by_staff(self, staff_id: str) -> List[JobService]:
        """Get all job services assigned to a staff member"""
        success, jobs_data, error = await self.db.query_documents("job_services", [("assigned_to", staff_id)])
        if not success or not jobs_data:
            return []
        return [JobService(**job) for job in jobs_data]

    async def get_job_services_by_status(self, status: str) -> List[JobService]:
        """Get all job services with specific status"""
        success, jobs_data, error = await self.db.query_documents("job_services", [("status", status)])
        if not success or not jobs_data:
            return []
        return [JobService(**job) for job in jobs_data]

    async def get_all_job_services(self) -> List[JobService]:
        """Get all job services (admin only) - from both job_services and job_service_requests collections"""
        try:
            # Get from both collections
            jobs_data = await self.db.get_all_documents("job_services")
            job_requests_data = await self.db.get_all_documents("job_service_requests")
            
            all_jobs = []
            
            # Add regular job services
            if jobs_data:
                all_jobs.extend(jobs_data)
            
            # Add job service requests
            if job_requests_data:
                all_jobs.extend(job_requests_data)
         
            # Convert to JobService objects (but be flexible with missing fields)
            result = []
            for job in all_jobs:
                try:
                    # Ensure required fields have defaults
                    concern_slip_id = job.get("concern_slip_id")
                    if concern_slip_id is None:
                        # Skip documents that don't have a concern_slip_id
                        print(f"Warning: Skipping job service {job.get('id', 'unknown')} - missing concern_slip_id")
                        continue
                    
                    # Create a more flexible JobService object
                    job_service = JobService(
                        id=job.get("id", ""),
                        concern_slip_id=concern_slip_id,
                        created_by=job.get("created_by", "system"),
                        title=job.get("title", "Job Service"),
                        description=job.get("description", ""),
                        location=job.get("location", ""),
                        category=job.get("category", "general"),
                        priority=job.get("priority", "medium"),
                        status=job.get("status", "pending"),
                        created_at=job.get("created_at", datetime.utcnow()),
                        updated_at=job.get("updated_at", datetime.utcnow()),
                        # Optional fields
                        assigned_to=job.get("assigned_to"),
                        scheduled_date=job.get("scheduled_date"),
                        estimated_hours=job.get("estimated_hours"),
                        materials_used=job.get("materials_used", []),
                        staff_notes=job.get("staff_notes"),
                        completion_notes=job.get("completion_notes"),
                        started_at=job.get("started_at"),
                        completed_at=job.get("completed_at"),
                        actual_hours=job.get("actual_hours")
                    )
                    result.append(job_service)
                except Exception as e:
                    print(f"Warning: Could not create JobService object for {job.get('id', 'unknown')}: {e}")
                    # Continue with next job instead of failing completely
                    continue
                    
            return result
        except Exception as e:
            raise ValueError(f"Failed to get job services: {str(e)}")

    async def create_tenant_job_service(self, concern_slip_id: str, created_by: str, job_data: dict) -> JobService:
        """Create a new job service from a concern slip with tenant as creator"""
        
        # Verify concern slip exists
        success, concern_slip_data, error = await self.db.get_document("concern_slips", concern_slip_id)
        if not success or not concern_slip_data:
            raise ValueError("Concern slip not found")
        
        # Verify creator is the tenant who reported the concern slip
        if concern_slip_data.get("reported_by") != created_by:
            raise ValueError("You can only create job services for your own concern slips")
        
        # Verify concern slip has appropriate resolution type
        if concern_slip_data.get("resolution_type") != "job_service":
            raise ValueError("Concern slip is not designated for job service resolution")
        
        # Verify creator is a tenant
        try:
            creator_profile = await self.user_service.get_user_profile(created_by)
            if not creator_profile or creator_profile.role != "tenant":
                raise ValueError("Only tenants can create tenant job services")
        except Exception as e:
            # If there's an issue getting the profile, try to get user data directly
            success, user_data, error = await self.db.get_document("user_profiles", created_by)
            if not success or not user_data:
                raise ValueError("User profile not found")
            

            user_role = user_data.get("role")
            if user_role != "tenant":
                raise ValueError("Only tenants can create tenant job services")

        job_service_data = {
            "id": str(uuid.uuid4()),
            "concern_slip_id": concern_slip_id,
            "created_by": created_by,
            "title": job_data.get("title") or concern_slip_data.get("title"),
            "description": job_data.get("description") or concern_slip_data.get("description"),
            "location": job_data.get("location") or concern_slip_data.get("location"),
            "category": job_data.get("category") or concern_slip_data.get("category"),
            "priority": job_data.get("priority") or concern_slip_data.get("priority"),
            "status": "pending",  # Tenant-created job services start as pending
            "assigned_to": None,  # Will be assigned by admin later
            "scheduled_date": job_data.get("scheduled_date"),
            "estimated_hours": job_data.get("estimated_hours"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Create job service
        await self.db.create_document("job_services", job_service_data, job_service_data["id"], validate=False)
        
        # Update concern slip to link it to the job service
        await self.db.update_document("concern_slips", concern_slip_id, {
            "linked_job_service_id": job_service_data["id"],
            "status": "completed",  # Mark as complete since tenant submitted job service
            "updated_at": datetime.utcnow()
        }, validate=False)

        # Send notification to admins about new tenant job service request
        await self._send_admin_notification(
            job_service_data["id"],
            f"New job service request from tenant for: {job_service_data['title']}"
        )

        # Send notification to tenant confirming submission
        await self._send_tenant_notification(
            created_by,
            job_service_data["id"],
            "Your job service request has been submitted successfully and is pending admin review"
        )

        return JobService(**job_service_data)

    async def _send_admin_notification(self, job_service_id: str, message: str):
        """Send notification to all admins about new tenant job service"""
        # Get all admin users
        success, admin_users_data, error = await self.db.query_documents("user_profiles", [("role", "admin")])
        
        if success and admin_users_data:
            for admin in admin_users_data:
                notification_data = {
                    "id": str(uuid.uuid4()),
                    "recipient_id": admin.get("id"),
                    "title": "New Tenant Job Service Request",
                    "message": message,
                    "notification_type": "tenant_job_service",
                    "related_id": job_service_id,
                    "is_read": False,
                    "created_at": datetime.utcnow()
                }
                await self.db.create_document("notifications", notification_data, notification_data["id"])

    async def _send_assignment_notification(self, recipient_id: str, job_service_id: str, title: str):
        """Send notification when job is assigned"""
        notification_data = {
            "id": str(uuid.uuid4()),
            "recipient_id": recipient_id,
            "title": "New Job Assignment",
            "message": f"You have been assigned a new job: {title}",
            "notification_type": "job_assigned",
            "related_id": job_service_id,
            "is_read": False,
            "created_at": datetime.utcnow()
        }
        await self.db.create_document("notifications", notification_data, notification_data["id"])

    async def _send_tenant_notification(self, recipient_id: str, job_service_id: str, message: str):
        """Send notification to tenant about job service updates"""
        notification_data = {
            "id": str(uuid.uuid4()),
            "recipient_id": recipient_id,
            "title": "Job Service Update",
            "message": message,
            "notification_type": "job_update",
            "related_id": job_service_id,
            "is_read": False,
            "created_at": datetime.utcnow()
        }
        await self.db.create_document("notifications", notification_data, notification_data["id"])

    async def _update_job_service_by_custom_id(self, job_service_id: str, update_data: dict) -> tuple[bool, str]:
        """Helper method to update job service by custom ID"""
        return await self._update_job_service_by_custom_id_in_collection(job_service_id, update_data, "job_services")

    async def _update_job_service_by_custom_id_in_collection(self, job_service_id: str, update_data: dict, collection_name: str) -> tuple[bool, str]:
        """Helper method to update job service by custom ID in specified collection"""
        try:
            # Query to find the document with the custom ID
            success, jobs_data, error = await self.db.query_documents(collection_name, [("id", job_service_id)])
            if not success or not jobs_data or len(jobs_data) == 0:
                return False, "Job service not found"
            
            # Get the Firestore document ID from the first matching document
            job_doc = jobs_data[0]
            firestore_doc_id = job_doc.get("_doc_id")
            
            if not firestore_doc_id:
                return False, "Could not find Firestore document ID"
            
            # Update using the Firestore document ID
            success, error = await self.db.update_document(collection_name, firestore_doc_id, update_data)
            
            if not success:
                return False, f"Failed to update job service: {error}"
            
            return True, ""
            
        except Exception as e:
            return False, str(e)

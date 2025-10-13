from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.auth.dependencies import get_current_user, require_role
from app.services.concern_slip_service import ConcernSlipService
from app.services.job_service_service import JobServiceService
from app.services.work_order_permit_service import WorkOrderPermitService
from app.services.ai_integration_service import AIIntegrationService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get dashboard statistics for admin home page"""
    try:
        concern_service = ConcernSlipService()
        job_service = JobServiceService()
        permit_service = WorkOrderPermitService()
        
        # Get all requests
        concern_slips = await concern_service.get_all_concern_slips()
        job_services = await job_service.get_all_job_services()
        work_permits = await permit_service.get_all_permits()
        
        # Calculate active work orders (assigned or in progress)
        active_statuses = ['assigned', 'in_progress']
        active_concerns = [cs for cs in concern_slips if cs.status in active_statuses]
        active_jobs = [js for js in job_services if js.status in active_statuses]
        active_permits = [wp for wp in work_permits if wp.status in active_statuses]
        
        active_work_orders = len(active_concerns) + len(active_jobs) + len(active_permits)
        
        # Calculate maintenance due (scheduled or pending)
        maintenance_statuses = ['scheduled', 'pending']
        maintenance_due = len([js for js in job_services if js.status in maintenance_statuses])
        
        return {
            "active_work_orders": active_work_orders,
            "maintenance_due": maintenance_due,
            "total_concern_slips": len(concern_slips),
            "total_job_services": len(job_services),
            "total_work_permits": len(work_permits)
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")

@router.get("/requests/all")
async def get_all_tenant_requests(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all tenant requests (Concern Slips, Job Services, Work Order Permits) with AI categorization"""
    try:
        concern_service = ConcernSlipService()
        job_service = JobServiceService()
        permit_service = WorkOrderPermitService()
        ai_service = AIIntegrationService()
        
        # Get all requests
        concern_slips = await concern_service.get_all_concern_slips()
        job_services = await job_service.get_all_job_services()
        work_permits = await permit_service.get_all_permits()
        
        all_requests = []
        
        # Process Concern Slips
        for cs in concern_slips:
            # Get AI processing history if available
            ai_history = await ai_service.get_processing_history(cs.id)
            
            request_data = {
                "id": cs.id,
                "formatted_id": cs.formatted_id,
                "title": cs.title,
                "description": cs.description,
                "location": cs.location,
                "category": cs.category,  # AI-generated category
                "priority": cs.priority,  # AI-generated priority
                "status": cs.status,
                "request_type": "Concern Slip",
                "unit_id": getattr(cs, 'unit_id', None),
                "reported_by": cs.reported_by,
                "assigned_to": getattr(cs, 'assigned_to', None),
                "created_at": cs.created_at.isoformat() if cs.created_at else None,
                "updated_at": cs.updated_at.isoformat() if cs.updated_at else None,
                "ai_processing": {
                    "category_confidence": ai_history.get("categorization", {}).get("confidence_scores", {}).get("category_confidence", 0.0) if ai_history else 0.0,
                    "urgency_confidence": ai_history.get("categorization", {}).get("confidence_scores", {}).get("urgency_confidence", 0.0) if ai_history else 0.0,
                    "translated": ai_history.get("translation", {}).get("successful", False) if ai_history else False,
                    "detected_language": ai_history.get("language_detection", {}).get("detected_language", "en") if ai_history else "en"
                }
            }
            all_requests.append(request_data)
        
        # Process Job Services
        for js in job_services:
            request_data = {
                "id": js.id,
                "formatted_id": getattr(js, 'formatted_id', js.id),
                "title": js.title or "Job Service Request",
                "description": js.description or "",
                "location": js.location or "",
                "category": js.category or "maintenance",  # AI-generated category
                "priority": js.priority or "medium",  # AI-generated priority
                "status": js.status,
                "request_type": "Job Service",
                "unit_id": getattr(js, 'unit_id', None),
                "reported_by": getattr(js, 'created_by', None),
                "assigned_to": js.assigned_to,
                "created_at": js.created_at.isoformat() if js.created_at else None,
                "updated_at": js.updated_at.isoformat() if js.updated_at else None,
                "ai_processing": {
                    "category_confidence": 0.0,
                    "urgency_confidence": 0.0,
                    "translated": False,
                    "detected_language": "en"
                }
            }
            all_requests.append(request_data)
        
        # Process Work Order Permits
        for wp in work_permits:
            request_data = {
                "id": wp.id,
                "formatted_id": getattr(wp, 'formatted_id', wp.id),
                "title": f"Work Order Permit - {wp.contractor_name}",
                "description": wp.work_description,
                "location": wp.unit_id,
                "category": getattr(wp, 'category', 'general'),  # AI-generated category
                "priority": getattr(wp, 'priority', 'medium'),  # AI-generated priority
                "status": wp.status,
                "request_type": "Work Order Permit",
                "unit_id": wp.unit_id,
                "reported_by": wp.requested_by,
                "assigned_to": getattr(wp, 'assigned_to', None),
                "created_at": wp.created_at.isoformat() if wp.created_at else None,
                "updated_at": wp.updated_at.isoformat() if wp.updated_at else None,
                "contractor_info": {
                    "name": wp.contractor_name,
                    "contact": wp.contractor_contact,
                    "company": wp.contractor_company
                },
                "ai_processing": {
                    "category_confidence": 0.0,
                    "urgency_confidence": 0.0,
                    "translated": False,
                    "detected_language": "en"
                }
            }
            all_requests.append(request_data)
        
        # Sort by creation date (newest first)
        all_requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return all_requests
        
    except Exception as e:
        logger.error(f"Error getting all tenant requests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get tenant requests: {str(e)}")

@router.get("/maintenance/all")
async def get_all_maintenance_tasks(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all maintenance tasks"""
    try:
        # For now, we'll use job services as maintenance tasks
        # In a full implementation, you might have a separate maintenance service
        job_service = JobServiceService()
        job_services = await job_service.get_all_job_services()
        
        maintenance_tasks = []
        for js in job_services:
            task_data = {
                "id": js.id,
                "formatted_id": getattr(js, 'formatted_id', js.id),
                "task_title": js.title or "Maintenance Task",
                "title": js.title or "Maintenance Task",
                "description": js.description or "",
                "location": js.location or "",
                "category": js.category or "maintenance",
                "priority": js.priority or "medium",
                "status": js.status,
                "assigned_to": js.assigned_to,
                "assigned_staff": js.assigned_to,
                "scheduled_date": js.scheduled_date.isoformat() if getattr(js, 'scheduled_date', None) else None,
                "created_at": js.created_at.isoformat() if js.created_at else None,
                "updated_at": js.updated_at.isoformat() if js.updated_at else None,
                "estimated_hours": getattr(js, 'estimated_hours', None)
            }
            maintenance_tasks.append(task_data)
        
        # Sort by scheduled date or creation date
        maintenance_tasks.sort(key=lambda x: x.get("scheduled_date") or x.get("created_at", ""), reverse=True)
        
        return maintenance_tasks
        
    except Exception as e:
        logger.error(f"Error getting maintenance tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get maintenance tasks: {str(e)}")

@router.get("/requests/by-category/{category}")
async def get_requests_by_category(
    category: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all requests filtered by AI-generated category"""
    try:
        all_requests = await get_all_tenant_requests(current_user)
        filtered_requests = [req for req in all_requests if req.get("category", "").lower() == category.lower()]
        return filtered_requests
    except Exception as e:
        logger.error(f"Error getting requests by category: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get requests by category: {str(e)}")

@router.get("/requests/by-priority/{priority}")
async def get_requests_by_priority(
    priority: str,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get all requests filtered by AI-generated priority"""
    try:
        all_requests = await get_all_tenant_requests(current_user)
        filtered_requests = [req for req in all_requests if req.get("priority", "").lower() == priority.lower()]
        return filtered_requests
    except Exception as e:
        logger.error(f"Error getting requests by priority: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get requests by priority: {str(e)}")

@router.get("/ai-analytics")
async def get_ai_analytics(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get AI processing analytics and statistics"""
    try:
        ai_service = AIIntegrationService()
        stats = await ai_service.get_translation_statistics(days)
        return stats
    except Exception as e:
        logger.error(f"Error getting AI analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI analytics: {str(e)}")
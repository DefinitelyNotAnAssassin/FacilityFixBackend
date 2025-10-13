from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-dashboard"])

# Mock data for demonstration
MOCK_CONCERN_SLIPS = [
    {
        "id": "cs-001",
        "formatted_id": "CS-2025-001",
        "title": "Water leak in bathroom",
        "description": "There is a water leak under the sink in the master bathroom",
        "location": "Unit 12A - Master Bathroom",
        "category": "plumbing",
        "priority": "high",
        "status": "pending",
        "request_type": "Concern Slip",
        "unit_id": "12A",
        "reported_by": "tenant_001",
        "assigned_to": None,
        "created_at": "2025-01-07T10:00:00Z",
        "updated_at": "2025-01-07T10:00:00Z",
        "ai_processing": {
            "category_confidence": 0.95,
            "urgency_confidence": 0.88,
            "translated": False,
            "detected_language": "en"
        }
    },
    {
        "id": "cs-002",
        "formatted_id": "CS-2025-002",
        "title": "Electrical outlet not working",
        "description": "The electrical outlet in the living room stopped working",
        "location": "Unit 8B - Living Room",
        "category": "electrical",
        "priority": "medium",
        "status": "assigned",
        "request_type": "Concern Slip",
        "unit_id": "8B",
        "reported_by": "tenant_002",
        "assigned_to": "staff_001",
        "created_at": "2025-01-06T14:30:00Z",
        "updated_at": "2025-01-06T15:00:00Z",
        "ai_processing": {
            "category_confidence": 0.92,
            "urgency_confidence": 0.75,
            "translated": False,
            "detected_language": "en"
        }
    }
]

MOCK_JOB_SERVICES = [
    {
        "id": "js-001",
        "formatted_id": "JS-2025-031",
        "title": "Monthly HVAC maintenance",
        "description": "Regular monthly maintenance for HVAC system",
        "location": "Building A - Rooftop",
        "category": "hvac",
        "priority": "medium",
        "status": "scheduled",
        "request_type": "Job Service",
        "unit_id": None,
        "reported_by": None,
        "assigned_to": "staff_002",
        "created_at": "2025-01-05T09:00:00Z",
        "updated_at": "2025-01-05T09:00:00Z",
        "ai_processing": {
            "category_confidence": 0.0,
            "urgency_confidence": 0.0,
            "translated": False,
            "detected_language": "en"
        }
    }
]

MOCK_WORK_PERMITS = [
    {
        "id": "wp-001",
        "formatted_id": "WP-2025-011",
        "title": "Work Order Permit - ABC Contractors",
        "description": "Kitchen renovation work",
        "location": "Unit 15C",
        "category": "carpentry",
        "priority": "low",
        "status": "approved",
        "request_type": "Work Order Permit",
        "unit_id": "15C",
        "reported_by": "tenant_003",
        "assigned_to": None,
        "created_at": "2025-01-04T11:00:00Z",
        "updated_at": "2025-01-04T16:00:00Z",
        "contractor_info": {
            "name": "ABC Contractors",
            "contact": "555-0123",
            "company": "ABC Construction Co."
        },
        "ai_processing": {
            "category_confidence": 0.0,
            "urgency_confidence": 0.0,
            "translated": False,
            "detected_language": "en"
        }
    }
]

@router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics for admin home page"""
    try:
        # Calculate stats from mock data
        all_requests = MOCK_CONCERN_SLIPS + MOCK_JOB_SERVICES + MOCK_WORK_PERMITS
        
        active_statuses = ['assigned', 'in_progress', 'scheduled']
        active_work_orders = len([req for req in all_requests if req['status'] in active_statuses])
        
        maintenance_statuses = ['scheduled', 'pending']
        maintenance_due = len([req for req in MOCK_JOB_SERVICES if req['status'] in maintenance_statuses])
        
        return {
            "active_work_orders": active_work_orders,
            "maintenance_due": maintenance_due,
            "total_concern_slips": len(MOCK_CONCERN_SLIPS),
            "total_job_services": len(MOCK_JOB_SERVICES),
            "total_work_permits": len(MOCK_WORK_PERMITS)
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")

@router.get("/requests/all")
async def get_all_tenant_requests():
    """Get all tenant requests (Concern Slips, Job Services, Work Order Permits) with AI categorization"""
    try:
        all_requests = MOCK_CONCERN_SLIPS + MOCK_JOB_SERVICES + MOCK_WORK_PERMITS
        
        # Sort by creation date (newest first)
        all_requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return all_requests
        
    except Exception as e:
        logger.error(f"Error getting all tenant requests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get tenant requests: {str(e)}")

@router.get("/maintenance/all")
async def get_all_maintenance_tasks():
    """Get all maintenance tasks"""
    try:
        maintenance_tasks = []
        for js in MOCK_JOB_SERVICES:
            task_data = {
                "id": js["id"],
                "formatted_id": js["formatted_id"],
                "task_title": js["title"],
                "title": js["title"],
                "description": js["description"],
                "location": js["location"],
                "category": js["category"],
                "priority": js["priority"],
                "status": js["status"],
                "assigned_to": js["assigned_to"],
                "assigned_staff": js["assigned_to"],
                "scheduled_date": None,
                "created_at": js["created_at"],
                "updated_at": js["updated_at"],
                "estimated_hours": None
            }
            maintenance_tasks.append(task_data)
        
        return maintenance_tasks
        
    except Exception as e:
        logger.error(f"Error getting maintenance tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get maintenance tasks: {str(e)}")

@router.get("/requests/by-category/{category}")
async def get_requests_by_category(category: str):
    """Get all requests filtered by AI-generated category"""
    try:
        all_requests = MOCK_CONCERN_SLIPS + MOCK_JOB_SERVICES + MOCK_WORK_PERMITS
        filtered_requests = [req for req in all_requests if req.get("category", "").lower() == category.lower()]
        return filtered_requests
    except Exception as e:
        logger.error(f"Error getting requests by category: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get requests by category: {str(e)}")

@router.get("/requests/by-priority/{priority}")
async def get_requests_by_priority(priority: str):
    """Get all requests filtered by AI-generated priority"""
    try:
        all_requests = MOCK_CONCERN_SLIPS + MOCK_JOB_SERVICES + MOCK_WORK_PERMITS
        filtered_requests = [req for req in all_requests if req.get("priority", "").lower() == priority.lower()]
        return filtered_requests
    except Exception as e:
        logger.error(f"Error getting requests by priority: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get requests by priority: {str(e)}")

@router.get("/ai-analytics")
async def get_ai_analytics(days: int = 30):
    """Get AI processing analytics and statistics"""
    try:
        # Mock AI analytics data
        return {
            "period_days": days,
            "total_processed": 150,
            "translations_attempted": 45,
            "translations_successful": 42,
            "translation_success_rate": 93.3,
            "languages_detected": {
                "english": 105,
                "tagalog": 45
            },
            "average_processing_time_ms": 1250,
            "most_common_categories": {
                "plumbing": 35,
                "electrical": 28,
                "hvac": 22,
                "carpentry": 15,
                "masonry": 12
            }
        }
    except Exception as e:
        logger.error(f"Error getting AI analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get AI analytics: {str(e)}")
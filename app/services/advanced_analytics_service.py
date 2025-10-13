from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import logging

from app.database.firestore_client import FirestoreClient
from app.services.concern_slip_service import ConcernSlipService
from app.services.job_service_service import JobServiceService
from app.services.work_order_permit_service import WorkOrderPermitService
from app.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)

class AdvancedAnalyticsService:
    """
    Advanced Analytics Service for FacilityFix
    Provides heat maps, performance insights, predictive analytics, and comprehensive reporting
    """
    
    def __init__(self):
        self.db = FirestoreClient()
        self.concern_service = ConcernSlipService()
        self.job_service = JobServiceService()
        self.permit_service = WorkOrderPermitService()
        self.inventory_service = InventoryService()
    
    async def generate_heat_map_data(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate heat map data showing issue hotspots by location and category
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get all concern slips in the date range
            all_concerns = await self.concern_service.get_all_concern_slips()
            
            # Filter by date range
            filtered_concerns = []
            for concern in all_concerns:
                concern_date = concern.created_at
                if concern_date is None:
                    continue
                    
                # Ensure timezone consistency - use naive datetimes
                if concern_date.tzinfo is not None:
                    concern_date = concern_date.replace(tzinfo=None)
                
                if start_date <= concern_date <= end_date:
                    filtered_concerns.append(concern)
            
            # Generate location-based heat map
            location_heat_map = defaultdict(lambda: defaultdict(int))
            category_heat_map = defaultdict(int)
            urgency_heat_map = defaultdict(int)
            
            for concern in filtered_concerns:
                location = concern.location or "Unknown"
                category = concern.category or "Uncategorized"
                priority = concern.priority or "medium"
                
                # Location x Category heat map
                location_heat_map[location][category] += 1
                
                # Category frequency
                category_heat_map[category] += 1
                
                # Urgency distribution
                urgency_heat_map[priority] += 1
            
            # Convert to structured format for frontend
            heat_map_matrix = []
            locations = list(location_heat_map.keys())
            categories = ["plumbing", "electrical", "HVAC", "carpentry", "pest control", "masonry"]
            
            for location in locations:
                location_data = {
                    "location": location,
                    "categories": {}
                }
                for category in categories:
                    location_data["categories"][category] = location_heat_map[location][category]
                heat_map_matrix.append(location_data)
            
            # Calculate hotspots (locations with highest issue frequency)
            location_totals = {
                location: sum(categories.values()) 
                for location, categories in location_heat_map.items()
            }
            
            hotspots = sorted(
                location_totals.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            return {
                "period_days": days,
                "total_issues": len(filtered_concerns),
                "heat_map_matrix": heat_map_matrix,
                "category_distribution": dict(category_heat_map),
                "urgency_distribution": dict(urgency_heat_map),
                "top_hotspots": [
                    {"location": location, "issue_count": count} 
                    for location, count in hotspots
                ],
                "locations": locations,
                "categories": categories,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate heat map data: {str(e)}")
            raise Exception(f"Heat map generation failed: {str(e)}")
    
    async def get_staff_performance_insights(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate staff performance metrics and insights
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get all job services (work assignments) in date range
            all_jobs = await self.job_service.get_all_job_services()
            
            # Filter by date range
            filtered_jobs = []
            for job in all_jobs:
                job_date = job.created_at
                if job_date is None:
                    continue
                    
                # Ensure timezone consistency - use naive datetimes
                if job_date.tzinfo is not None:
                    job_date = job_date.replace(tzinfo=None)
                
                if start_date <= job_date <= end_date:
                    filtered_jobs.append(job)
            
            # Calculate staff metrics
            staff_metrics = defaultdict(lambda: {
                "assigned_tasks": 0,
                "completed_tasks": 0,
                "in_progress_tasks": 0,
                "average_completion_time": 0,
                "completion_times": [],
                "task_categories": defaultdict(int)
            })
            
            for job in filtered_jobs:
                staff_id = job.assigned_to
                if not staff_id:
                    continue
                
                staff_metrics[staff_id]["assigned_tasks"] += 1
                
                if job.status == "completed":
                    staff_metrics[staff_id]["completed_tasks"] += 1
                    
                    # Calculate completion time if available
                    if hasattr(job, 'completed_at') and job.completed_at:
                        completion_time = (job.completed_at - job.created_at).total_seconds() / 3600  # hours
                        staff_metrics[staff_id]["completion_times"].append(completion_time)
                
                elif job.status == "in_progress":
                    staff_metrics[staff_id]["in_progress_tasks"] += 1
                
                # Track task categories
                if hasattr(job, 'category') and job.category:
                    staff_metrics[staff_id]["task_categories"][job.category] += 1
            
            # Calculate averages and performance scores
            performance_summary = []
            for staff_id, metrics in staff_metrics.items():
                completion_rate = (
                    metrics["completed_tasks"] / metrics["assigned_tasks"] * 100
                    if metrics["assigned_tasks"] > 0 else 0
                )
                
                avg_completion_time = (
                    np.mean(metrics["completion_times"])
                    if metrics["completion_times"] else 0
                )
                
                # Performance score (weighted combination of completion rate and speed)
                performance_score = (completion_rate * 0.7) + (
                    max(0, 100 - avg_completion_time) * 0.3
                    if avg_completion_time > 0 else completion_rate * 0.7
                )
                
                performance_summary.append({
                    "staff_id": staff_id,
                    "assigned_tasks": metrics["assigned_tasks"],
                    "completed_tasks": metrics["completed_tasks"],
                    "in_progress_tasks": metrics["in_progress_tasks"],
                    "completion_rate": round(completion_rate, 2),
                    "average_completion_time_hours": round(avg_completion_time, 2),
                    "performance_score": round(performance_score, 2),
                    "specializations": dict(metrics["task_categories"])
                })
            
            # Sort by performance score
            performance_summary.sort(key=lambda x: x["performance_score"], reverse=True)
            
            # Calculate safe averages (handle empty lists)
            completion_rates = [s["completion_rate"] for s in performance_summary]
            completion_times = [s["average_completion_time_hours"] for s in performance_summary if s["average_completion_time_hours"] > 0]
            
            avg_completion_rate = float(np.mean(completion_rates)) if completion_rates else 0.0
            avg_completion_time = float(np.mean(completion_times)) if completion_times else 0.0
            
            # Ensure no NaN or Inf values
            if not np.isfinite(avg_completion_rate):
                avg_completion_rate = 0.0
            if not np.isfinite(avg_completion_time):
                avg_completion_time = 0.0
            
            return {
                "period_days": days,
                "total_staff_analyzed": len(performance_summary),
                "staff_performance": performance_summary,
                "top_performers": performance_summary[:3],
                "performance_insights": {
                    "average_completion_rate": round(avg_completion_rate, 2),
                    "average_completion_time": round(avg_completion_time, 2),
                    "total_tasks_completed": sum(s["completed_tasks"] for s in performance_summary),
                    "total_tasks_assigned": sum(s["assigned_tasks"] for s in performance_summary)
                },
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate staff performance insights: {str(e)}")
            raise Exception(f"Staff performance analysis failed: {str(e)}")
    
    async def get_equipment_insights(self, days: int = 90) -> Dict[str, Any]:
        """
        Generate equipment failure patterns and maintenance insights
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get all concern slips related to equipment
            all_concerns = await self.concern_service.get_all_concern_slips()
            
            # Filter equipment-related issues
            equipment_issues = []
            for concern in all_concerns:
                concern_date = concern.created_at
                if concern_date is None:
                    continue
                    
                # Ensure timezone consistency - use naive datetimes
                if concern_date.tzinfo is not None:
                    concern_date = concern_date.replace(tzinfo=None)
                
                if start_date <= concern_date <= end_date:
                    equipment_issues.append(concern)
            
            # Analyze equipment failure patterns
            equipment_failures = defaultdict(lambda: {
                "failure_count": 0,
                "categories": defaultdict(int),
                "locations": defaultdict(int),
                "urgency_levels": defaultdict(int),
                "failure_dates": []
            })
            
            # Extract equipment information from descriptions
            equipment_keywords = {
                "AC": ["ac", "aircon", "air conditioning", "hvac"],
                "Elevator": ["elevator", "lift"],
                "Generator": ["generator", "genset"],
                "Water Pump": ["pump", "water pump"],
                "Lighting": ["light", "bulb", "fluorescent", "led"],
                "Plumbing": ["pipe", "faucet", "toilet", "sink"],
                "Electrical": ["outlet", "switch", "breaker", "wiring"]
            }
            
            for concern in equipment_issues:
                description_lower = concern.description.lower()
                
                for equipment_type, keywords in equipment_keywords.items():
                    if any(keyword in description_lower for keyword in keywords):
                        equipment_failures[equipment_type]["failure_count"] += 1
                        equipment_failures[equipment_type]["categories"][concern.category] += 1
                        equipment_failures[equipment_type]["locations"][concern.location] += 1
                        equipment_failures[equipment_type]["urgency_levels"][concern.priority] += 1
                        equipment_failures[equipment_type]["failure_dates"].append(concern.created_at)
            
            # Calculate failure frequency and predict maintenance needs
            equipment_analysis = []
            for equipment_type, data in equipment_failures.items():
                if data["failure_count"] == 0:
                    continue
                
                # Calculate failure frequency (failures per month)
                failure_frequency = data["failure_count"] / (days / 30)
                
                # Predict next maintenance based on failure pattern
                if data["failure_dates"]:
                    dates = sorted(data["failure_dates"])
                    if len(dates) > 1:
                        # Calculate average time between failures
                        intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                        avg_interval = float(np.mean(intervals)) if intervals else 30.0
                        # Ensure finite value
                        if not np.isfinite(avg_interval) or avg_interval <= 0:
                            avg_interval = 30.0
                        next_maintenance = dates[-1] + timedelta(days=avg_interval * 0.8)  # 80% of average interval
                    else:
                        next_maintenance = datetime.now() + timedelta(days=30)
                else:
                    next_maintenance = datetime.now() + timedelta(days=30)
                
                # Risk assessment
                high_urgency_count = data["urgency_levels"].get("high", 0)
                high_urgency_ratio = high_urgency_count / data["failure_count"] if data["failure_count"] > 0 else 0.0
                risk_level = "High" if high_urgency_ratio > 0.3 else "Medium" if high_urgency_ratio > 0.1 else "Low"
                
                equipment_analysis.append({
                    "equipment_type": equipment_type,
                    "failure_count": data["failure_count"],
                    "failure_frequency_per_month": round(failure_frequency, 2),
                    "most_common_category": max(data["categories"], key=data["categories"].get) if data["categories"] else "Unknown",
                    "most_problematic_location": max(data["locations"], key=data["locations"].get) if data["locations"] else "Unknown",
                    "risk_level": risk_level,
                    "high_urgency_ratio": round(high_urgency_ratio, 2),
                    "predicted_next_maintenance": next_maintenance.isoformat(),
                    "category_breakdown": dict(data["categories"]),
                    "location_breakdown": dict(data["locations"])
                })
            
            # Sort by failure frequency
            equipment_analysis.sort(key=lambda x: x["failure_frequency_per_month"], reverse=True)
            
            return {
                "period_days": days,
                "equipment_analysis": equipment_analysis,
                "high_risk_equipment": [eq for eq in equipment_analysis if eq["risk_level"] == "High"],
                "maintenance_recommendations": [
                    {
                        "equipment": eq["equipment_type"],
                        "recommendation": f"Schedule preventive maintenance - {eq['failure_frequency_per_month']:.1f} failures/month",
                        "priority": eq["risk_level"],
                        "next_maintenance": eq["predicted_next_maintenance"]
                    }
                    for eq in equipment_analysis[:5]
                ],
                "total_equipment_issues": sum(eq["failure_count"] for eq in equipment_analysis),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate equipment insights: {str(e)}")
            raise Exception(f"Equipment analysis failed: {str(e)}")
    
    async def get_inventory_linkage_analysis(self, days: int = 60) -> Dict[str, Any]:
        """
        Analyze inventory usage patterns linked to repair types with real inventory data
        """
        try:
            # Get real inventory data if available
            try:
                # Attempt to get real inventory items
                inventory_items = await self.db.get_all_documents("inventory")
                inventory_transactions = await self.db.get_all_documents("inventory_transactions")
                inventory_requests = await self.db.get_all_documents("inventory_requests")
            except Exception as e:
                logger.warning(f"Could not retrieve inventory data: {e}")
                inventory_items = []
                inventory_transactions = []
                inventory_requests = []
            
            # Real inventory analysis if data exists
            if inventory_items:
                return await self._analyze_real_inventory_data(inventory_items, inventory_transactions, inventory_requests, days)
            
            # Fallback to estimated analysis based on concern slips
            return await self._analyze_estimated_inventory_usage(days)
            
        except Exception as e:
            logger.error(f"Failed to generate inventory linkage analysis: {str(e)}")
            raise Exception(f"Inventory analysis failed: {str(e)}")
    
    async def _analyze_real_inventory_data(self, inventory_items, transactions, requests, days):
        """Analyze real inventory data"""
        try:
            # Analyze real inventory items
            inventory_analysis = []
            low_stock_items = []
            high_usage_items = []
            
            for item in inventory_items:
                current_stock = item.get("current_stock", 0)
                reorder_level = item.get("reorder_level", 10)
                item_name = item.get("item_name", "Unknown Item")
                category = item.get("category", "general")
                unit_cost = item.get("unit_cost", 0)
                
                # Check if low stock
                if current_stock <= reorder_level:
                    low_stock_items.append({
                        "item_name": item_name,
                        "current_stock": current_stock,
                        "reorder_level": reorder_level,
                        "category": category,
                        "unit_cost": unit_cost,
                        "shortage": reorder_level - current_stock
                    })
                
                # Calculate usage from transactions
                usage_count = 0
                total_cost = 0
                
                for transaction in transactions:
                    if (transaction.get("inventory_id") == item.get("id") and 
                        transaction.get("transaction_type") == "out"):
                        usage_count += abs(transaction.get("quantity", 0))
                        total_cost += abs(transaction.get("total_cost", 0))
                
                if usage_count > 0:
                    high_usage_items.append({
                        "item_name": item_name,
                        "usage_count": usage_count,
                        "total_cost": total_cost,
                        "category": category,
                        "average_cost": total_cost / usage_count if usage_count > 0 else 0
                    })
            
            # Sort by usage and cost
            high_usage_items.sort(key=lambda x: x["usage_count"], reverse=True)
            low_stock_items.sort(key=lambda x: x["shortage"], reverse=True)
            
            return {
                "period_days": days,
                "total_inventory_items": len(inventory_items),
                "low_stock_alerts": low_stock_items[:10],
                "high_usage_items": high_usage_items[:10],
                "total_transactions": len(transactions),
                "total_requests": len(requests),
                "inventory_analysis": [
                    {
                        "repair_category": "Real Inventory Data",
                        "total_items": len(inventory_items),
                        "low_stock_count": len(low_stock_items),
                        "high_usage_count": len([item for item in high_usage_items if item["usage_count"] > 5]),
                        "total_value": sum(item.get("unit_cost", 0) * item.get("current_stock", 0) for item in inventory_items),
                        "reorder_priority": "High" if len(low_stock_items) > 5 else "Medium"
                    }
                ],
                "recommendations": [
                    f"Restock {len(low_stock_items)} low inventory items",
                    f"Monitor {len(high_usage_items)} high-usage items",
                    "Implement automated reorder system" if len(low_stock_items) > 10 else "Current stock levels manageable"
                ],
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing real inventory data: {e}")
            return await self._analyze_estimated_inventory_usage(days)
    
    async def _analyze_estimated_inventory_usage(self, days):
        """Fallback analysis based on concern slip patterns"""
        # Repair category to inventory mapping
        repair_inventory_mapping = {
            "plumbing": {
                "common_parts": ["pipes", "fittings", "sealants", "valves"],
                "average_cost_per_repair": 150.00,
                "usage_frequency": "high"
            },
            "electrical": {
                "common_parts": ["wires", "outlets", "switches", "breakers"],
                "average_cost_per_repair": 120.00,
                "usage_frequency": "medium"
            },
            "hvac": {
                "common_parts": ["filters", "refrigerant", "belts", "motors"],
                "average_cost_per_repair": 300.00,
                "usage_frequency": "high"
            },
            "carpentry": {
                "common_parts": ["wood", "screws", "hinges", "handles"],
                "average_cost_per_repair": 80.00,
                "usage_frequency": "low"
            },
            "pest control": {
                "common_parts": ["pesticides", "traps", "sealants"],
                "average_cost_per_repair": 60.00,
                "usage_frequency": "medium"
            },
            "masonry": {
                "common_parts": ["cement", "tiles", "grout", "tools"],
                "average_cost_per_repair": 200.00,
                "usage_frequency": "low"
            }
        }
        
        # Get recent concern slips to estimate inventory needs
        all_concerns = await self.concern_service.get_all_concern_slips()
        
        # Calculate inventory projections based on repair frequency
        category_counts = defaultdict(int)
        for concern in all_concerns[-100:]:  # Last 100 concerns
            category_counts[concern.category.lower()] += 1
        
        inventory_projections = []
        total_projected_cost = 0
        
        for category, count in category_counts.items():
            if category in repair_inventory_mapping:
                mapping = repair_inventory_mapping[category]
                projected_cost = count * mapping["average_cost_per_repair"]
                total_projected_cost += projected_cost
                
                inventory_projections.append({
                    "repair_category": category,
                    "repair_count": count,
                    "common_parts": mapping["common_parts"],
                    "average_cost_per_repair": mapping["average_cost_per_repair"],
                    "projected_total_cost": projected_cost,
                    "usage_frequency": mapping["usage_frequency"],
                    "reorder_priority": "High" if mapping["usage_frequency"] == "high" else "Medium"
                })
        
        # Sort by projected cost
        inventory_projections.sort(key=lambda x: x["projected_total_cost"], reverse=True)
        
        return {
            "period_days": days,
            "inventory_analysis": inventory_projections,
            "total_projected_cost": total_projected_cost,
            "high_priority_reorders": [
                item for item in inventory_projections 
                if item["reorder_priority"] == "High"
            ],
            "cost_breakdown": {
                category: sum(
                    item["projected_total_cost"] 
                    for item in inventory_projections 
                    if item["repair_category"] == category
                )
                for category in category_counts.keys()
            },
            "recommendations": [
                f"Stock up on {item['repair_category']} supplies - {item['repair_count']} recent repairs"
                for item in inventory_projections[:3]
            ],
            "generated_at": datetime.now().isoformat()
        }
    
    async def generate_comprehensive_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate a comprehensive analytics report combining all insights
        """
        try:
            # Gather all analytics data
            heat_map_data = await self.generate_heat_map_data(days)
            staff_performance = await self.get_staff_performance_insights(days)
            equipment_insights = await self.get_equipment_insights(days * 3)  # Longer period for equipment
            inventory_analysis = await self.get_inventory_linkage_analysis(days * 2)
            
            # Get recent concern slips for detailed analysis
            recent_concerns = await self.get_recent_concerns_data(days)
            
            # Create executive summary with safe value extraction
            top_issue_category = "N/A"
            if heat_map_data["category_distribution"]:
                top_issue_category = max(
                    heat_map_data["category_distribution"], 
                    key=heat_map_data["category_distribution"].get
                )
            
            executive_summary = {
                "report_period": f"{days} days",
                "total_issues_processed": heat_map_data["total_issues"],
                "top_issue_category": top_issue_category,
                "most_problematic_location": heat_map_data["top_hotspots"][0]["location"] if heat_map_data["top_hotspots"] else "N/A",
                "staff_performance_average": round(staff_performance["performance_insights"]["average_completion_rate"], 2),
                "high_risk_equipment_count": len(equipment_insights["high_risk_equipment"]),
                "projected_inventory_cost": round(inventory_analysis["total_projected_cost"], 2)
            }
            
            # Key recommendations
            recommendations = []
            
            # Location-based recommendations
            if heat_map_data["top_hotspots"]:
                top_hotspot = heat_map_data["top_hotspots"][0]
                recommendations.append({
                    "type": "location",
                    "priority": "high",
                    "recommendation": f"Focus maintenance efforts on {top_hotspot['location']} - {top_hotspot['issue_count']} issues reported"
                })
            
            # Staff performance recommendations
            if staff_performance["staff_performance"]:
                low_performers = [s for s in staff_performance["staff_performance"] if s["completion_rate"] < 70]
                if low_performers:
                    recommendations.append({
                        "type": "staff",
                        "priority": "medium",
                        "recommendation": f"Provide additional training for {len(low_performers)} staff members with completion rates below 70%"
                    })
            
            # Equipment recommendations
            for eq in equipment_insights["high_risk_equipment"][:2]:
                recommendations.append({
                    "type": "equipment",
                    "priority": "high",
                    "recommendation": f"Schedule immediate preventive maintenance for {eq['equipment_type']} - high failure risk"
                })
            
            return {
                "report_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "report_period_days": days,
                    "report_type": "comprehensive_analytics"
                },
                "executive_summary": executive_summary,
                "recommendations": recommendations,
                "detailed_analytics": {
                    "heat_map_analysis": heat_map_data,
                    "staff_performance": staff_performance,
                    "equipment_insights": equipment_insights,
                    "inventory_analysis": inventory_analysis,
                    "recent_concerns": recent_concerns
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate comprehensive report: {str(e)}")
            raise Exception(f"Comprehensive report generation failed: {str(e)}")

    async def get_recent_concerns_data(self, days: int = 30) -> Dict[str, Any]:
        """
        Get detailed recent concern slips data for CSV reporting
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get all concern slips in the date range
            all_concerns = await self.concern_service.get_all_concern_slips()
            
            # Filter by date range and extract detailed information
            recent_concerns = []
            for concern in all_concerns:
                concern_date = concern.created_at
                if concern_date is None:
                    continue
                    
                # Ensure timezone consistency - use naive datetimes
                if concern_date.tzinfo is not None:
                    concern_date = concern_date.replace(tzinfo=None)
                
                if start_date <= concern_date <= end_date:
                    # Calculate days open
                    days_open = (datetime.utcnow() - concern_date).days
                    
                    concern_detail = {
                        "id": getattr(concern, 'formatted_id', concern.id),
                        "title": concern.title,
                        "location": concern.location,
                        "category": concern.category,
                        "priority": concern.priority,
                        "status": concern.status,
                        "created_at": concern_date.strftime("%Y-%m-%d"),
                        "days_open": days_open,
                        "reported_by": concern.reported_by,
                        "description": concern.description[:100] + "..." if len(concern.description) > 100 else concern.description
                    }
                    recent_concerns.append(concern_detail)
            
            # Sort by creation date (newest first)
            recent_concerns.sort(key=lambda x: x["created_at"], reverse=True)
            
            # Calculate statistics
            status_counts = {}
            category_counts = {}
            priority_counts = {}
            
            for concern in recent_concerns:
                status = concern["status"]
                category = concern["category"]
                priority = concern["priority"]
                
                status_counts[status] = status_counts.get(status, 0) + 1
                category_counts[category] = category_counts.get(category, 0) + 1
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            return {
                "period_days": days,
                "total_concerns": len(recent_concerns),
                "concern_details": recent_concerns[:50],  # Limit to 50 most recent
                "status_breakdown": status_counts,
                "category_breakdown": category_counts,
                "priority_breakdown": priority_counts,
                "average_days_open": sum(c["days_open"] for c in recent_concerns) / len(recent_concerns) if recent_concerns else 0,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get recent concerns data: {str(e)}")
            raise Exception(f"Recent concerns data retrieval failed: {str(e)}")

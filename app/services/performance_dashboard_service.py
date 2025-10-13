from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
from collections import defaultdict
import logging

from app.database.firestore_client import FirestoreClient
from app.services.advanced_analytics_service import AdvancedAnalyticsService
from app.services.ai_integration_service import AIIntegrationService
from app.services.concern_slip_service import ConcernSlipService

logger = logging.getLogger(__name__)

class PerformanceDashboardService:
    """
    Performance Insights Dashboard Service
    Provides comprehensive performance metrics and KPIs for facility management
    """
    
    def __init__(self):
        self.db = FirestoreClient()
        self.advanced_analytics = AdvancedAnalyticsService()
        self.ai_service = AIIntegrationService()
        self.concern_service = ConcernSlipService()
    
    async def get_executive_dashboard(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate executive-level dashboard with high-level KPIs and insights
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            # Get all concern slips for the period
            all_concerns = await self.concern_service.get_all_concern_slips()
            period_concerns = [
                concern for concern in all_concerns
                if start_date <= (concern.created_at.replace(tzinfo=timezone.utc) if concern.created_at.tzinfo is None else concern.created_at) <= end_date
            ]
            
            # Calculate key metrics
            total_issues = len(period_concerns)
            resolved_issues = len([c for c in period_concerns if c.status == "completed"])
            pending_issues = len([c for c in period_concerns if c.status == "pending"])
            in_progress_issues = len([c for c in period_concerns if c.status in ["approved", "in_progress"]])
            
            # Resolution rate
            resolution_rate = (resolved_issues / total_issues * 100) if total_issues > 0 else 0
            
            # Average resolution time (mock calculation)
            avg_resolution_time = 2.5  # days (would be calculated from actual completion times)
            
            # AI processing metrics
            ai_processed = len([c for c in period_concerns if hasattr(c, 'ai_processed') and c.ai_processed])
            ai_success_rate = (ai_processed / total_issues * 100) if total_issues > 0 else 0
            
            # Category distribution
            category_distribution = defaultdict(int)
            urgency_distribution = defaultdict(int)
            
            for concern in period_concerns:
                category_distribution[concern.category] += 1
                urgency_distribution[concern.priority] += 1
            
            # Trend analysis (compare with previous period)
            prev_start = start_date - timedelta(days=days)
            prev_concerns = [
                concern for concern in all_concerns
                if prev_start <= (concern.created_at.replace(tzinfo=timezone.utc) if concern.created_at.tzinfo is None else concern.created_at) < start_date
            ]
            
            prev_total = len(prev_concerns)
            trend_percentage = ((total_issues - prev_total) / prev_total * 100) if prev_total > 0 else 0
            
            return {
                "period": {
                    "days": days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "key_metrics": {
                    "total_issues": total_issues,
                    "resolved_issues": resolved_issues,
                    "pending_issues": pending_issues,
                    "in_progress_issues": in_progress_issues,
                    "resolution_rate": round(resolution_rate, 2),
                    "average_resolution_time_days": avg_resolution_time,
                    "ai_processing_success_rate": round(ai_success_rate, 2)
                },
                "trends": {
                    "issue_volume_change": round(trend_percentage, 2),
                    "trend_direction": "up" if trend_percentage > 0 else "down" if trend_percentage < 0 else "stable"
                },
                "distributions": {
                    "by_category": dict(category_distribution),
                    "by_urgency": dict(urgency_distribution)
                },
                "alerts": await self._generate_performance_alerts(period_concerns),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate executive dashboard: {str(e)}")
            raise Exception(f"Executive dashboard generation failed: {str(e)}")
    
    async def get_operational_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get operational metrics for day-to-day facility management
        """
        try:
            # Get recent performance data
            staff_performance = await self.advanced_analytics.get_staff_performance_insights(days)
            equipment_insights = await self.advanced_analytics.get_equipment_insights(days * 4)  # Longer period for equipment
            
            # Calculate operational KPIs
            operational_kpis = {
                "response_time": {
                    "average_hours": 4.2,  # Mock data - would be calculated from actual response times
                    "target_hours": 4.0,
                    "status": "slightly_behind"
                },
                "first_call_resolution": {
                    "rate": 78.5,
                    "target": 80.0,
                    "status": "needs_improvement"
                },
                "customer_satisfaction": {
                    "score": 4.2,
                    "target": 4.5,
                    "status": "good"
                },
                "preventive_maintenance": {
                    "completion_rate": 92.0,
                    "target": 95.0,
                    "status": "good"
                }
            }
            
            # Resource utilization
            resource_utilization = {
                "staff_utilization": {
                    "average_workload": 85.0,
                    "optimal_range": [70, 90],
                    "status": "optimal"
                },
                "equipment_availability": {
                    "rate": 96.5,
                    "target": 98.0,
                    "status": "good"
                },
                "inventory_turnover": {
                    "rate": 12.0,  # times per year
                    "target": 10.0,
                    "status": "excellent"
                }
            }
            
            # Daily operational summary
            today = datetime.now().date()
            daily_summary = {
                "date": today.isoformat(),
                "new_issues": 8,
                "resolved_issues": 12,
                "active_technicians": 6,
                "scheduled_maintenance": 3,
                "emergency_calls": 1,
                "inventory_alerts": 2
            }
            
            return {
                "period_days": days,
                "operational_kpis": operational_kpis,
                "resource_utilization": resource_utilization,
                "daily_summary": daily_summary,
                "staff_performance_summary": {
                    "total_staff": len(staff_performance.get("staff_performance", [])),
                    "top_performer": staff_performance.get("top_performers", [{}])[0] if staff_performance.get("top_performers") else None,
                    "average_completion_rate": staff_performance.get("performance_insights", {}).get("average_completion_rate", 0)
                },
                "equipment_alerts": equipment_insights.get("high_risk_equipment", [])[:3],
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate operational metrics: {str(e)}")
            raise Exception(f"Operational metrics generation failed: {str(e)}")
    
    async def get_predictive_maintenance_insights(self) -> Dict[str, Any]:
        """
        Generate predictive maintenance insights and recommendations
        """
        try:
            # Get equipment insights for predictive analysis
            equipment_insights = await self.advanced_analytics.get_equipment_insights(120)  # 4 months of data
            
            # Predictive maintenance recommendations
            maintenance_predictions = []
            
            for equipment in equipment_insights.get("equipment_analysis", []):
                if equipment["risk_level"] in ["High", "Medium"]:
                    next_maintenance = datetime.fromisoformat(equipment["predicted_next_maintenance"].replace('Z', '+00:00'))
                    days_until_maintenance = (next_maintenance - datetime.now(timezone.utc)).days
                    
                    maintenance_predictions.append({
                        "equipment_type": equipment["equipment_type"],
                        "risk_level": equipment["risk_level"],
                        "predicted_failure_probability": min(equipment["failure_frequency_per_month"] * 10, 95),  # Convert to percentage
                        "days_until_recommended_maintenance": max(days_until_maintenance, 0),
                        "estimated_cost": self._estimate_maintenance_cost(equipment["equipment_type"]),
                        "impact_if_delayed": self._assess_delay_impact(equipment["equipment_type"], equipment["risk_level"]),
                        "recommended_actions": self._get_maintenance_actions(equipment["equipment_type"])
                    })
            
            # Sort by urgency (risk level and days until maintenance)
            maintenance_predictions.sort(key=lambda x: (
                0 if x["risk_level"] == "High" else 1,
                x["days_until_recommended_maintenance"]
            ))
            
            # Seasonal predictions
            seasonal_insights = {
                "current_season_risks": self._get_seasonal_risks(),
                "upcoming_season_preparation": self._get_seasonal_preparation(),
                "weather_related_alerts": [
                    "Rainy season approaching - check drainage systems",
                    "Summer heat expected - AC maintenance recommended",
                    "Typhoon season - secure outdoor equipment"
                ]
            }
            
            return {
                "maintenance_predictions": maintenance_predictions[:10],  # Top 10 priorities
                "seasonal_insights": seasonal_insights,
                "cost_projections": {
                    "next_30_days": sum(p["estimated_cost"] for p in maintenance_predictions if p["days_until_recommended_maintenance"] <= 30),
                    "next_90_days": sum(p["estimated_cost"] for p in maintenance_predictions if p["days_until_recommended_maintenance"] <= 90),
                    "annual_projection": sum(p["estimated_cost"] for p in maintenance_predictions) * 4  # Quarterly estimate
                },
                "risk_assessment": {
                    "high_risk_count": len([p for p in maintenance_predictions if p["risk_level"] == "High"]),
                    "medium_risk_count": len([p for p in maintenance_predictions if p["risk_level"] == "Medium"]),
                    "overall_facility_risk": "Medium"  # Would be calculated based on various factors
                },
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate predictive maintenance insights: {str(e)}")
            raise Exception(f"Predictive maintenance insights generation failed: {str(e)}")
    
    async def _generate_performance_alerts(self, concerns: List) -> List[Dict[str, Any]]:
        """Generate performance alerts based on concern data"""
        alerts = []
        
        # Check for high volume of issues
        if len(concerns) > 50:  # Threshold for high volume
            alerts.append({
                "type": "high_volume",
                "severity": "warning",
                "message": f"High volume of issues detected: {len(concerns)} in the current period",
                "recommendation": "Consider increasing staff allocation or investigating root causes"
            })
        
        # Check for high urgency issues
        high_urgency = [c for c in concerns if c.priority == "high"]
        if len(high_urgency) > len(concerns) * 0.3:  # More than 30% high urgency
            alerts.append({
                "type": "high_urgency_ratio",
                "severity": "critical",
                "message": f"{len(high_urgency)} high-urgency issues ({len(high_urgency)/len(concerns)*100:.1f}%)",
                "recommendation": "Review emergency response procedures and resource allocation"
            })
        
        # Check for location hotspots
        location_counts = defaultdict(int)
        for concern in concerns:
            location_counts[concern.location] += 1
        
        max_location = max(location_counts.items(), key=lambda x: x[1]) if location_counts else ("", 0)
        if max_location[1] > len(concerns) * 0.4:  # More than 40% from one location
            alerts.append({
                "type": "location_hotspot",
                "severity": "warning",
                "message": f"Location '{max_location[0]}' has {max_location[1]} issues ({max_location[1]/len(concerns)*100:.1f}%)",
                "recommendation": "Investigate systemic issues at this location"
            })
        
        return alerts
    
    def _estimate_maintenance_cost(self, equipment_type: str) -> float:
        """Estimate maintenance cost based on equipment type"""
        cost_estimates = {
            "AC": 2500.0,
            "Elevator": 5000.0,
            "Generator": 3500.0,
            "Water Pump": 1500.0,
            "Lighting": 500.0,
            "Plumbing": 800.0,
            "Electrical": 1200.0
        }
        return cost_estimates.get(equipment_type, 1000.0)
    
    def _assess_delay_impact(self, equipment_type: str, risk_level: str) -> str:
        """Assess impact of delaying maintenance"""
        if risk_level == "High":
            return f"Critical - {equipment_type} failure could cause significant disruption and safety issues"
        elif risk_level == "Medium":
            return f"Moderate - {equipment_type} issues may affect comfort and efficiency"
        else:
            return f"Low - {equipment_type} maintenance can be scheduled during regular intervals"
    
    def _get_maintenance_actions(self, equipment_type: str) -> List[str]:
        """Get recommended maintenance actions for equipment type"""
        actions = {
            "AC": ["Clean filters", "Check refrigerant levels", "Inspect electrical connections", "Test thermostat"],
            "Elevator": ["Inspect cables", "Test safety systems", "Lubricate moving parts", "Check control panel"],
            "Generator": ["Change oil", "Test battery", "Inspect fuel system", "Run load test"],
            "Water Pump": ["Check seals", "Inspect impeller", "Test pressure switch", "Clean strainer"],
            "Lighting": ["Replace bulbs", "Clean fixtures", "Check ballasts", "Test emergency lighting"],
            "Plumbing": ["Inspect pipes", "Check for leaks", "Test water pressure", "Clean drains"],
            "Electrical": ["Test circuits", "Inspect panels", "Check grounding", "Verify safety devices"]
        }
        return actions.get(equipment_type, ["Schedule inspection", "Check operation", "Review maintenance logs"])
    
    def _get_seasonal_risks(self) -> List[str]:
        """Get current seasonal risks"""
        current_month = datetime.now().month
        
        if current_month in [6, 7, 8, 9]:  # Rainy season in Philippines
            return [
                "Increased risk of water leaks and flooding",
                "Electrical system vulnerabilities due to moisture",
                "HVAC systems working harder due to humidity"
            ]
        elif current_month in [3, 4, 5]:  # Hot season
            return [
                "AC systems under maximum load",
                "Increased electrical consumption",
                "Water system stress due to higher usage"
            ]
        else:  # Cooler months
            return [
                "Reduced AC usage - good time for maintenance",
                "Optimal conditions for outdoor maintenance work",
                "Lower overall system stress"
            ]
    
    def _get_seasonal_preparation(self) -> List[str]:
        """Get seasonal preparation recommendations"""
        current_month = datetime.now().month
        
        if current_month in [4, 5]:  # Before rainy season
            return [
                "Inspect and clean drainage systems",
                "Check roof and window seals",
                "Test backup power systems",
                "Stock up on waterproofing materials"
            ]
        elif current_month in [1, 2]:  # Before hot season
            return [
                "Service all AC units",
                "Check electrical capacity for increased load",
                "Inspect cooling tower systems",
                "Prepare for higher water consumption"
            ]
        else:
            return [
                "Conduct routine inspections",
                "Plan preventive maintenance schedules",
                "Review emergency procedures",
                "Update equipment inventories"
            ]

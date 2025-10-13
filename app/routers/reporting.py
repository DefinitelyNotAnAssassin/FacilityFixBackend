from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.auth.dependencies import get_current_user, require_role
from app.services.reporting_service import reporting_service

router = APIRouter(prefix="/reports", tags=["reporting"])

@router.get("/repair-trends")
async def get_repair_trends_report(
    building_id: Optional[str] = Query(None, description="Building ID to filter by"),
    period: str = Query("monthly", description="Report period: weekly, monthly, quarterly"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Generate comprehensive repair trends report"""
    try:
        success, report, error = await reporting_service.generate_repair_trends_report(
            building_id=building_id,
            period=period
        )
        
        if success:
            return {
                "success": True,
                "data": report
            }
        else:
            raise HTTPException(status_code=500, detail=error)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate repair trends report: {str(e)}")

@router.get("/staff-performance")
async def get_staff_performance_report(
    staff_id: Optional[str] = Query(None, description="Staff ID to filter by"),
    building_id: Optional[str] = Query(None, description="Building ID to filter by"),
    days: int = Query(30, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Generate staff performance analytics report"""
    try:
        success, report, error = await reporting_service.generate_staff_performance_report(
            staff_id=staff_id,
            building_id=building_id,
            days=days
        )
        
        if success:
            return {
                "success": True,
                "data": report
            }
        else:
            raise HTTPException(status_code=500, detail=error)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate staff performance report: {str(e)}")

@router.get("/inventory-consumption")
async def get_inventory_consumption_report(
    building_id: str = Query(..., description="Building ID"),
    period: str = Query("monthly", description="Report period: weekly, monthly, quarterly"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Generate inventory consumption and trends report"""
    try:
        success, report, error = await reporting_service.generate_inventory_consumption_report(
            building_id=building_id,
            period=period
        )
        
        if success:
            return {
                "success": True,
                "data": report
            }
        else:
            raise HTTPException(status_code=500, detail=error)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate inventory consumption report: {str(e)}")

@router.get("/dashboard-metrics")
async def get_dashboard_metrics(
    building_id: Optional[str] = Query(None, description="Building ID to filter by"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Get comprehensive dashboard metrics for admin overview"""
    try:
        from app.services.analytics_service import AnalyticsService
        from app.services.inventory_service import inventory_service
        
        analytics = AnalyticsService()
        
        # Get basic dashboard stats
        dashboard_stats = await analytics.get_dashboard_stats()
        
        # Get work order trends (last 30 days)
        trends = await analytics.get_work_order_trends(30)
        
        # Get category breakdown
        category_breakdown = await analytics.get_category_breakdown()
        
        # Get inventory alerts if building_id provided
        inventory_alerts = []
        if building_id:
            success, alerts, error = inventory_service.get_low_stock_alerts(building_id)
            if success:
                inventory_alerts = alerts
        
        dashboard_data = {
            "summary": dashboard_stats,
            "trends": trends,
            "categories": category_breakdown,
            "inventory_alerts": inventory_alerts,
            "last_updated": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "data": dashboard_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard metrics: {str(e)}")

@router.get("/heat-map-data")
async def get_heat_map_data(
    building_id: str = Query(..., description="Building ID"),
    days: int = Query(90, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Generate heat map data for frequently reported problem areas"""
    try:
        from app.database.database_service import database_service
        from app.database.collections import COLLECTIONS
        import pandas as pd
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        success, concern_slips, error = database_service.query_documents(
            COLLECTIONS['concern_slips'],
            [
                ('building_id', '==', building_id),
                ('created_at', '>=', start_date)
            ]
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to get concern slips: {error}")
        
        concern_df = pd.DataFrame(concern_slips)
        
        heat_map_data = {
            "building_id": building_id,
            "period_days": days,
            "location_frequency": {},
            "category_distribution": {},
            "priority_hotspots": {},
            "time_patterns": {}
        }
        
        if not concern_df.empty:
            # Location frequency
            heat_map_data["location_frequency"] = concern_df['location'].value_counts().to_dict()
            
            # Category distribution by location
            category_location = concern_df.groupby(['location', 'category']).size().reset_index(name='count')
            heat_map_data["category_distribution"] = category_location.to_dict('records')
            
            # Priority hotspots
            priority_location = concern_df.groupby(['location', 'priority']).size().reset_index(name='count')
            heat_map_data["priority_hotspots"] = priority_location.to_dict('records')
            
            # Time patterns (hour of day)
            concern_df['created_at'] = pd.to_datetime(concern_df['created_at'])
            concern_df['hour'] = concern_df['created_at'].dt.hour
            heat_map_data["time_patterns"] = concern_df['hour'].value_counts().to_dict()
        
        return {
            "success": True,
            "data": heat_map_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate heat map data: {str(e)}")

@router.get("/predictive-insights")
async def get_predictive_insights(
    building_id: str = Query(..., description="Building ID"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Generate predictive insights and recommendations"""
    try:
        from app.database.database_service import database_service
        from app.database.collections import COLLECTIONS
        import pandas as pd
        
        success, concern_slips, error = database_service.query_documents(
            COLLECTIONS['concern_slips'],
            [('building_id', '==', building_id)]
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to get historical data: {error}")
        
        concern_df = pd.DataFrame(concern_slips)
        
        insights = {
            "building_id": building_id,
            "failure_predictions": [],
            "maintenance_recommendations": [],
            "cost_forecasts": {},
            "risk_assessments": [],
            "generated_at": datetime.now().isoformat()
        }
        
        if not concern_df.empty:
            concern_df['created_at'] = pd.to_datetime(concern_df['created_at'])
            
            # Equipment with recurring issues
            equipment_issues = concern_df['location'].value_counts()
            high_risk_equipment = equipment_issues[equipment_issues > equipment_issues.quantile(0.8)]
            
            for location, count in high_risk_equipment.items():
                insights["failure_predictions"].append({
                    "location": location,
                    "issue_count": int(count),
                    "risk_level": "high" if count > equipment_issues.quantile(0.9) else "medium",
                    "recommendation": f"Schedule preventive maintenance for {location}"
                })
            
            category_frequency = concern_df['category'].value_counts()
            for category, count in category_frequency.items():
                if count > category_frequency.quantile(0.7):
                    insights["maintenance_recommendations"].append({
                        "category": category,
                        "frequency": int(count),
                        "recommendation": f"Increase preventive maintenance focus on {category} systems"
                    })
            
            monthly_concerns = concern_df.groupby(concern_df['created_at'].dt.to_period('M')).size()
            if len(monthly_concerns) >= 3:
                avg_monthly_concerns = monthly_concerns.mean()
                estimated_monthly_cost = avg_monthly_concerns * 150  # Estimated cost per concern
                
                insights["cost_forecasts"] = {
                    "estimated_monthly_maintenance_cost": round(estimated_monthly_cost, 2),
                    "projected_annual_cost": round(estimated_monthly_cost * 12, 2),
                    "trend": "increasing" if monthly_concerns.iloc[-1] > monthly_concerns.mean() else "stable"
                }
        
        return {
            "success": True,
            "data": insights
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate predictive insights: {str(e)}")

@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    building_id: Optional[str] = Query(None),
    format: str = Query("json", description="Export format: json, csv"),
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_role(["admin"]))
):
    """Export reports in various formats"""
    try:
        if report_type == "repair-trends":
            success, report_data, error = await reporting_service.generate_repair_trends_report(building_id)
        elif report_type == "staff-performance":
            success, report_data, error = await reporting_service.generate_staff_performance_report(building_id=building_id)
        elif report_type == "inventory-consumption":
            success, report_data, error = await reporting_service.generate_inventory_consumption_report(building_id)
        else:
            raise HTTPException(status_code=400, detail="Invalid report type")
        
        if not success:
            raise HTTPException(status_code=500, detail=error)
        
        if format.lower() == "csv":
            # Convert to CSV format (simplified)
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers and data (simplified example)
            writer.writerow(["Report Type", "Generated At", "Building ID"])
            writer.writerow([report_type, report_data.get("generated_at", ""), building_id or "All"])
            
            csv_content = output.getvalue()
            output.close()
            
            return {
                "success": True,
                "format": "csv",
                "content": csv_content,
                "filename": f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        else:
            return {
                "success": True,
                "format": "json",
                "data": report_data
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export report: {str(e)}")

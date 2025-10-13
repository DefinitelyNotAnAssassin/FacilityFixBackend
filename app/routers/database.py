from fastapi import APIRouter, HTTPException, Depends
from ..database.firestore_client import get_firestore_client
from ..database.collections import COLLECTIONS
from ..auth.dependencies import require_admin
from ..models.database_models import Building, UserProfile

router = APIRouter(prefix="/database", tags=["database"])

@router.get("/test")
async def test_database_connection():
    """Test Firestore database connection"""
    try:
        client = get_firestore_client()
        if client is None:
            raise HTTPException(status_code=500, detail="Firestore client not initialized")
            
        result = client.get_collection(COLLECTIONS['buildings'], limit=1)
        return {
            "status": "success",
            "message": "Firestore connection successful",
            "collections_available": list(COLLECTIONS.keys()),
            "sample_query_result": len(result)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@router.post("/init-sample-data")
async def initialize_sample_data(current_user: dict = Depends(require_admin)):
    """Initialize sample data for testing (Admin only)"""
    try:
        client = get_firestore_client()
        if client is None:
            raise HTTPException(status_code=500, detail="Firestore client not initialized")
            
        # Create sample building
        building_data = {
            "building_name": "Sample Condominium",
            "address": "123 Main Street, Manila",
            "total_floors": 10,
            "total_units": 50
        }
        
        building_id = client.create_document(
            COLLECTIONS['buildings'], 
            data=building_data
        )
        
        # Create sample user profile
        user_profile_data = {
            "building_id": building_id,
            "first_name": "Admin",
            "last_name": "User",
            "role": "admin",
            "status": "active"
        }
        
        client.create_document(
            COLLECTIONS['users'],
            document_id=current_user['uid'],
            data=user_profile_data
        )
        
        return {
            "status": "success",
            "message": "Sample data initialized",
            "building_id": building_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize data: {str(e)}")

"""
Check what's in the database for the specific request
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database.database_service import DatabaseService
from app.database.collections import COLLECTIONS
import firebase_admin
from firebase_admin import credentials

# Initialize Firebase
cred = credentials.Certificate("firebase-service-account.json")
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(cred)

db_service = DatabaseService()

async def check_request():
    request_id = "iv3OO0wwODNUEbXcp87S"
    
    success, request_data, error = await db_service.get_document(
        COLLECTIONS['inventory_requests'],
        request_id
    )
    
    if success and request_data:
        print(f"Request ID: {request_id}")
        print(f"formatted_id in DB: {request_data.get('formatted_id')}")
        print(f"id field in DB: {request_data.get('id')}")
        print(f"_doc_id in DB: {request_data.get('_doc_id')}")
    else:
        print(f"Failed: {error}")

if __name__ == "__main__":
    asyncio.run(check_request())

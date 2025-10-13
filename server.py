from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime

# Import all notification routers
from app.routers.notifications import router as notifications_router
from app.routers.websocket import router as websocket_router
from app.routers.announcements import router as announcements_router

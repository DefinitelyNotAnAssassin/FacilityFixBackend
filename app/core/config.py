# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "facilityfix-6d27a")
    # Use the same default bucket name format used in the app's Firebase client
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "facilityfix-6d27a.firebasestorage.app")
    FIREBASE_WEB_API_KEY: str = os.getenv(
        "FIREBASE_WEB_API_KEY",
        "AIzaSyBe1P1076wLTs6C6RHAAo-pEernmDxUdWM",
    )
    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "firebase-service-account.json",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # GROQ-related
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    USE_GROQ: bool = os.getenv("USE_GROQ", "false").lower() == "true"

    # Auto-escalation settings
    # TEMPORARILY DISABLED - Will re-enable at 11 PM (Dec 7, 2025)
    ENABLE_AUTO_ESCALATION: bool = os.getenv("ENABLE_AUTO_ESCALATION", "true").lower() == "true"
    ## PRODUCTION: Age in days
    #ESCALATION_TIME_UNIT: str = os.getenv("ESCALATION_TIME_UNIT", "days")
    #ESCALATE_LOW_TO_MED_DAYS: int = int(os.getenv("ESCALATE_LOW_TO_MED_DAYS", "3"))
    #ESCALATE_LOW_TO_HIGH_DAYS: int = int(os.getenv("ESCALATE_LOW_TO_HIGH_DAYS", "5"))
    #ESCALATE_MED_TO_HIGH_DAYS: int = int(os.getenv("ESCALATE_MED_TO_HIGH_DAYS", "5"))
    #DEMO: Uncomment below and comment above to test with minutes instead of days
    ESCALATION_TIME_UNIT: str = "minutes"
    ESCALATE_LOW_TO_MED_DAYS: int = 3    # 5 minutes
    ESCALATE_LOW_TO_HIGH_DAYS: int = 6   # 10 minutes
    ESCALATE_MED_TO_HIGH_DAYS: int = 6   # 10 minutes

    # Frontend URL for notification action links
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3748")
    
    # Maintenance reminder settings
    ## PRODUCTION: Reminders in days (7 days, 3 days, 1 day before, and day itself)
    #MAINTENANCE_REMINDER_DAYS: list = [7, 3, 1, 0]
    ## DEMO: Uncomment below and comment above to test with minutes instead of days
    MAINTENANCE_REMINDER_DAYS: list = [10/60, 5/60, 3/60, 0]  # 10 minutes, 5 minutes, 3 minutes before, and day itself (for demo)
    
    # Timezone for date conversion (default to UTC+8 for Philippines/Asia)
    # Set via environment variable: TZ_OFFSET=8 for UTC+8, etc.
    TZ_OFFSET: int = int(os.getenv("TZ_OFFSET", "8"))


settings = Settings()


def assert_groq_ready():
    """Call this only if you actually plan to use GROQ."""
    if settings.USE_GROQ and not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ is enabled but GROQ_API_KEY is missing. "
            "Set it in .env or disable USE_GROQ."
        )

# ===== Back-compat aliases (export names used by other modules) =====
# These make imports like `from app.core.config import GROQ_API_KEY` work.
USE_GROQ = settings.USE_GROQ
GROQ_MODEL = settings.GROQ_MODEL
GROQ_API_KEY = settings.GROQ_API_KEY
SECRET_KEY = settings.SECRET_KEY  # optional, kept for consistency
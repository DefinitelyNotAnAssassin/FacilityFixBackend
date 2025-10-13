# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "facilityfix-6d27a")
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

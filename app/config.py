# app/config.py
from dotenv import load_dotenv
import os
from typing import List

load_dotenv()

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "FastAPI App")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))

settings = Settings()

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'procurement.db'}")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
JWT_SECRET = "replace-this-with-a-managed-secret-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 480
POLICY_VERSION = "2.4"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

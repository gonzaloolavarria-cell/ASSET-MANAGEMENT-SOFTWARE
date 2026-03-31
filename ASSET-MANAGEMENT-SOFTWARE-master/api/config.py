"""Application configuration — loads settings from .env file."""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ocp_maintenance.db")
    SAP_MOCK_DIR: str = os.getenv("SAP_MOCK_DIR", "sap_mock/data")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "whisper-1")
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "OCP Maintenance AI MVP"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ALLOWED_ORIGINS: list[str] = os.getenv(
        "AMS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    ADMIN_API_KEY: str = os.getenv("AMS_ADMIN_API_KEY", "")

    def validate(self) -> list[str]:
        """Check required env vars and return list of warnings."""
        warnings: list[str] = []
        if not self.ANTHROPIC_API_KEY:
            warnings.append(
                "ANTHROPIC_API_KEY is not set. Agent workflow (M1-M4) will fail. "
                "Set it in .env or environment. See .env.example for details."
            )
        if not self.ADMIN_API_KEY:
            warnings.append(
                "AMS_ADMIN_API_KEY is not set. Admin endpoints (seed, reset) will return 503."
            )
        return warnings


settings = Settings()

# Log warnings at import time so they appear on startup
for _warning in settings.validate():
    logger.warning(_warning)

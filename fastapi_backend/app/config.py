import os
from typing import List

class Settings:
    PROJECT_NAME: str = "Remote Desktop Support Server"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./remote_support.db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # TTL & Timing (in seconds)
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "2592000")) # 30 days
    HEARTBEAT_INTERVAL_SECONDS: int = 20
    HEARTBEAT_TIMEOUT_SECONDS: int = 45
    CONNECTION_REQUEST_TTL_SECONDS: int = 60

    # CORS
    CORS_ALLOWED_ORIGINS_RAW: str = os.getenv("CORS_ALLOWED_ORIGINS", "*")

    @property
    def cors_origins(self) -> List[str]:
        raw = self.CORS_ALLOWED_ORIGINS_RAW.strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]

    # STUN & TURN defaults
    STUN_SERVERS: str = os.getenv("STUN_SERVERS", "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302")
    TURN_SERVER: str = os.getenv("TURN_SERVER", "")
    TURN_USERNAME: str = os.getenv("TURN_USERNAME", "remote")
    TURN_PASSWORD: str = os.getenv("TURN_PASSWORD", "support@2026")
    TURN_REALM: str = os.getenv("TURN_REALM", "remote-support.local")

settings = Settings()

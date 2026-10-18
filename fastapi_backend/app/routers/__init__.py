from app.routers.devices import router as devices_router
from app.routers.sessions import router as sessions_router
from app.routers.signaling_ws import router as signaling_router
from app.routers.health import router as health_router

__all__ = [
    "devices_router",
    "sessions_router",
    "signaling_router",
    "health_router",
]

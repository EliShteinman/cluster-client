from fastapi import APIRouter

from app.logger import log_debug
from app.models import HealthStatus

health_router: APIRouter = APIRouter(prefix="/health")


@health_router.get(path="/live")
@log_debug
def report_alive() -> HealthStatus:
    return HealthStatus()


@health_router.get(path="/ready")
@log_debug
def report_ready() -> HealthStatus:
    return HealthStatus()

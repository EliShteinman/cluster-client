from fastapi import APIRouter

cluster_router: APIRouter = APIRouter()
health_router: APIRouter = APIRouter(prefix="/health")

from app.routes import cluster_routes, health_routes  # noqa: E402, F401 - registers the routes on the routers above

__all__: list[str] = ["cluster_router", "health_router"]

from app.routes.cluster_routes import cluster_router
from app.routes.health_routes import health_router

__all__: list[str] = ["cluster_router", "health_router"]

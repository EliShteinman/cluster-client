from app.models import ClusterRequest

CLUSTER_URL: str = "https://cluster:9443/v1/bdbs/1"
CLUSTER_HEADERS: dict[str, str] = {
    "x-cluster-method": "GET",
    "x-cluster-url": CLUSTER_URL,
    "x-cluster-authorization": "Basic abc",
}
CLUSTER_REQUEST: ClusterRequest = ClusterRequest(method="GET", url=CLUSTER_URL, authorization="Basic abc")

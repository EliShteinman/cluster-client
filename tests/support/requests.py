from app.models import TargetRequest

TARGET_URL: str = "https://cluster:9443/v1/bdbs/1"
TARGET_HEADERS: dict[str, str] = {
    "x-edge-method": "GET",
    "x-edge-url": TARGET_URL,
    "x-target-authorization": "Basic abc",
}
TARGET_REQUEST: TargetRequest = TargetRequest(
    method="GET", url=TARGET_URL, headers={"authorization": "Basic abc"}
)

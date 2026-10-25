import json
from pathlib import Path

from pydantic import JsonValue

from app.config import TEXT_ENCODING
from app.models import ClusterResponse

SAMPLES_FOLDER: Path = Path(__file__).parent / "cluster_samples"
EXAMPLES_FOLDER: Path = Path(__file__).parents[2] / "config" / "examples"


def sample_paths() -> list[Path]:
    return sorted(SAMPLES_FOLDER.glob(pattern="*.json"))


def sample_response(*, path: Path) -> ClusterResponse:
    sample: dict[str, JsonValue] = json.loads(s=path.read_text(encoding=TEXT_ENCODING))
    body: JsonValue = sample["body"]
    content: bytes = b"" if body is None else json.dumps(obj=body).encode(encoding=TEXT_ENCODING)
    status_code: JsonValue = sample["status"]
    assert isinstance(status_code, int)
    return ClusterResponse(status_code=status_code, content=content)

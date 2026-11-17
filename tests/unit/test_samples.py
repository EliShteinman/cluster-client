import json
from pathlib import Path

import pytest

from app.config.failures import FailureSettings
from app.models import Answer
from app.response_builder import build_response
from tests.support.rules import RULES, SAMPLES

SAMPLE_FILES: list[Path] = sorted(SAMPLES.glob(pattern="*.json"))


def content_of(*, sample: Path) -> bytes:
    body: object = json.loads(s=sample.read_text(encoding="utf-8"))["body"]
    return b"" if body is None else json.dumps(obj=body).encode(encoding="utf-8")


@pytest.mark.parametrize("sample", SAMPLE_FILES, ids=[sample.stem for sample in SAMPLE_FILES])
def test_every_real_answer_passes_the_real_files(sample: Path) -> None:
    build_response(
        target_response=Answer(status_code=200, content=content_of(sample=sample)),
        rules=RULES,
        settings=FailureSettings(),
    )

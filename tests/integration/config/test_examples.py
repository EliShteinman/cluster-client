import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.errors import ResponseRejectedError
from app.field_paths import FieldPath, load_field_paths
from app.models import ClusterResponse
from app.response_builder import build_response
from app.schema import load_schema
from tests.support.cluster_samples import EXAMPLES_FOLDER, sample_paths, sample_response

SCHEMA: Draft202012Validator = load_schema(path=EXAMPLES_FOLDER / "response-schema.json")
IGNORED_FIELDS: tuple[FieldPath, ...] = load_field_paths(path=EXAMPLES_FOLDER / "ignored-fields.json")
SAMPLES: list[Path] = sample_paths()
SAMPLES_WITH_FORBIDDEN_FIELDS: list[Path] = [path for path in SAMPLES if b"sample" in path.read_bytes()]


def build(*, path: Path, ignored_fields: tuple[FieldPath, ...] = IGNORED_FIELDS) -> ClusterResponse:
    return build_response(
        cluster_response=sample_response(path=path), schema=SCHEMA, ignored_fields=ignored_fields
    )


@pytest.mark.parametrize("path", SAMPLES, ids=[path.stem for path in SAMPLES])
def test_every_cluster_answer_passes(path: Path) -> None:
    assert build(path=path).status_code == sample_response(path=path).status_code


@pytest.mark.parametrize(
    "path", SAMPLES_WITH_FORBIDDEN_FIELDS, ids=[path.stem for path in SAMPLES_WITH_FORBIDDEN_FIELDS]
)
def test_forbidden_fields_are_left_out(path: Path) -> None:
    assert b"sample" not in build(path=path).content


@pytest.mark.parametrize(
    "path", SAMPLES_WITH_FORBIDDEN_FIELDS, ids=[path.stem for path in SAMPLES_WITH_FORBIDDEN_FIELDS]
)
def test_forbidden_fields_are_rejected_when_not_ignored(path: Path) -> None:
    with pytest.raises(ResponseRejectedError):
        build(path=path, ignored_fields=())


def test_unknown_answer_is_rejected() -> None:
    unknown: ClusterResponse = ClusterResponse(
        status_code=200, content=json.dumps(obj={"surprise": 1}).encode()
    )

    with pytest.raises(ResponseRejectedError):
        build_response(cluster_response=unknown, schema=SCHEMA, ignored_fields=IGNORED_FIELDS)

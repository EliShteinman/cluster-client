from pathlib import PurePosixPath

from jsonschema import Draft7Validator
from pydantic import JsonValue

from tests.support.helm_chart import (
    NOT_SET_BY_HELM,
    chart_values,
    dockerfile_env,
    settings_env_names,
    values_schema,
)

VALUES: dict[str, JsonValue] = chart_values()
SCHEMA: dict[str, JsonValue] = values_schema()
IMAGE_ENV: dict[str, str] = dockerfile_env()


def test_default_values_match_the_schema() -> None:
    assert list(Draft7Validator(schema=SCHEMA).iter_errors(instance=VALUES)) == []


def test_schema_allows_exactly_the_settings_helm_may_set() -> None:
    assert set(SCHEMA["$defs"]["environment"]["properties"]) == settings_env_names() - NOT_SET_BY_HELM


def test_container_port_is_the_image_port() -> None:
    assert str(VALUES["containerPort"]) == IMAGE_ENV["CLUSTER_CLIENT_SERVER__PORT"]


def test_every_image_path_is_under_a_mount() -> None:
    mounts: list[PurePosixPath] = [PurePosixPath(path) for path in VALUES["mounts"].values()]
    image_paths: list[PurePosixPath] = [
        PurePosixPath(value) for name, value in IMAGE_ENV.items() if name.endswith("_PATH")
    ]

    assert all(any(mount in path.parents for mount in mounts) for path in image_paths)


def test_files_are_the_ones_the_image_reads() -> None:
    files_mount: PurePosixPath = PurePosixPath(VALUES["mounts"]["files"])
    image_files: set[str] = {
        PurePosixPath(value).name
        for value in IMAGE_ENV.values()
        if PurePosixPath(value).parent == files_mount
    }

    assert set(VALUES["files"]) == image_files

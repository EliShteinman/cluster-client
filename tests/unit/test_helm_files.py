from pathlib import Path

import pytest

ROOT: Path = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ["redacted-fields.json", "ignored-fields.json"])
def test_helm_copy_matches_the_local_file(name: str) -> None:
    assert (ROOT / "helm" / "files" / name).read_bytes() == (ROOT / "config" / name).read_bytes()

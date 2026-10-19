from app.errors import ClusterUnreachableError


def test_unreachable_reason_names_the_url() -> None:
    assert ClusterUnreachableError(url="https://cluster:9443", reason="refused").reason == (
        "cannot reach https://cluster:9443: refused"
    )

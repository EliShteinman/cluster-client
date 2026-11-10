from io import BytesIO

import requests
from requests.structures import CaseInsensitiveDict
from urllib3 import HTTPConnectionPool
from urllib3.exceptions import MaxRetryError

CONNECT_FAILURE: MaxRetryError = MaxRetryError(
    pool=HTTPConnectionPool(host="cluster"), url="/", reason=ConnectionRefusedError("refused")
)


class SentRequest:
    def __init__(self, *, method: str, url: str, data: bytes, allow_redirects: bool) -> None:
        self.method: str = method
        self.url: str = url
        self.content: bytes = data
        self.allow_redirects: bool = allow_redirects


class FakeClusterApi:
    def __init__(self) -> None:
        self.requests: list[SentRequest] = []
        self._error: requests.RequestException | None = None

    def fail_with(self, *, error: requests.RequestException) -> None:
        self._error = error

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        data: bytes,
        timeout: tuple[float, float],
        allow_redirects: bool,
        verify: bool,
    ) -> requests.Response:
        self.requests.append(SentRequest(method=method, url=url, data=data, allow_redirects=allow_redirects))
        if self._error is not None:
            raise self._error
        response: requests.Response = requests.Response()
        response.status_code = 200
        response.headers = CaseInsensitiveDict()
        response.raw = BytesIO(initial_bytes=b'{"uid":1}')
        return response

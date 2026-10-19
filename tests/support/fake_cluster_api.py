import json

import requests
from pydantic import JsonValue
from requests.structures import CaseInsensitiveDict

from app.config import TEXT_ENCODING


class SentRequest:
    def __init__(self, *, method: str, url: str, headers: dict[str, str], data: bytes) -> None:
        self.method: str = method
        self.url: str = url
        self.headers: CaseInsensitiveDict[str] = CaseInsensitiveDict(data=headers)
        self.content: bytes = data


class FakeClusterApi:
    def __init__(self) -> None:
        self.requests: list[SentRequest] = []
        self._status_code: int = 200
        self._headers: dict[str, str] = {}
        self._content: bytes = b'{"uid":1}'
        self._offline: bool = False

    def respond_with_json(
        self, *, status_code: int, body: JsonValue, headers: dict[str, str] | None = None
    ) -> None:
        self.respond_with_content(
            status_code=status_code,
            content=json.dumps(obj=body, separators=(",", ":")).encode(encoding=TEXT_ENCODING),
            headers=headers,
        )

    def respond_with_content(
        self, *, status_code: int, content: bytes, headers: dict[str, str] | None = None
    ) -> None:
        self._status_code = status_code
        self._content = content
        self._headers = headers or {}

    def go_offline(self) -> None:
        self._offline = True

    def request(
        self, *, method: str, url: str, headers: dict[str, str], data: bytes, timeout: float, verify: bool
    ) -> requests.Response:
        self.requests.append(SentRequest(method=method, url=url, headers=headers, data=data))
        if self._offline:
            raise requests.ConnectionError("connection refused")
        response: requests.Response = requests.Response()
        response.status_code = self._status_code
        response.headers = CaseInsensitiveDict(data=self._headers)
        response._content = self._content
        return response

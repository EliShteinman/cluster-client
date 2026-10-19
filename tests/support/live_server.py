import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI

LOOPBACK_HOST: str = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS: float = 10.0
POLL_INTERVAL_SECONDS: float = 0.05
SHUTDOWN_TIMEOUT_SECONDS: float = 10.0


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((LOOPBACK_HOST, 0))
        port: int = probe.getsockname()[1]
        return port


@contextmanager
def live_server(*, app: FastAPI, port: int) -> Iterator[str]:
    server: uvicorn.Server = uvicorn.Server(
        uvicorn.Config(app, host=LOOPBACK_HOST, port=port, log_config=None)
    )
    thread: threading.Thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline: float = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline:
            raise TimeoutError(f"server on port {port} did not start")
        time.sleep(POLL_INTERVAL_SECONDS)
    try:
        yield f"http://{LOOPBACK_HOST}:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)

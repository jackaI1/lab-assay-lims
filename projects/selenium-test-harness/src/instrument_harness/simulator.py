"""Serve only the packaged simulator page on loopback, never a working directory."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from threading import Thread

from .resources import audit, process_start


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        content = files("instrument_harness").joinpath("web/index.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def simulator() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, name="instrument-simulator", daemon=True)
    metadata = {
        "owner": "instrument-harness",
        "pid": os.getpid(),
        "start": process_start(os.getpid()),
        "port": server.server_port,
        "cleanup": "server.shutdown(); server.server_close(); thread.join() on context exit",
    }
    thread.start()
    try:
        audit("simulator-start", **metadata)
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        audit("simulator-stop", **metadata, exited=not thread.is_alive())

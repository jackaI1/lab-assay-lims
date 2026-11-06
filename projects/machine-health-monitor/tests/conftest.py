import socket

import pytest


@pytest.fixture
def endpoint():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"opc.tcp://127.0.0.1:{port}/filling-line/"

import socket
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from instrument_harness import simulator


def test_server_serves_packaged_page_only_and_releases_port_on_failure():
    port = None
    with pytest.raises(RuntimeError, match="test failure"):
        with simulator() as url:
            with urlopen(url) as response:
                assert b"Bench supply simulator" in response.read()
            with pytest.raises(HTTPError) as error:
                urlopen(url + "pyproject.toml")
            assert error.value.code == 404
            port = int(url.split(":")[-1].rstrip("/"))
            raise RuntimeError("test failure")
    with socket.socket() as connection:
        connection.settimeout(1)
        assert connection.connect_ex(("127.0.0.1", port)) != 0

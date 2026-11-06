from pathlib import Path

import pytest

from drone_identity.simulator import verify_loopback_listener


@pytest.mark.parametrize('address,allowed', [('0100007F', True), ('00000000', False), ('020011AC', False)])
def test_actual_listener_metadata_must_show_loopback(monkeypatch, address, allowed):
    # Linux /proc/net/udp uses native-endian IPv4 addresses; 14580 = 0x38F4.
    contents = ('   sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n'
                f'  141: {address}:38F4 00000000:0000 07 00000000:00000000 00:00000000 00000000 0 0 456 2\n')
    monkeypatch.setattr(Path, 'read_text', lambda self: contents)
    if allowed:
        assert verify_loopback_listener(14580) == '127.0.0.1:14580'
    else:
        with pytest.raises(RuntimeError, match='loopback'):
            verify_loopback_listener(14580)

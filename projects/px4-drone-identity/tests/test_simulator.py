import json
import os
import sys

import pytest

from drone_identity.simulator import Simulator


def test_owned_fixture_is_stopped_even_when_experiment_fails(tmp_path):
    pid = None
    with pytest.raises(RuntimeError, match='experiment failed'):
        with Simulator(tmp_path, command=[sys.executable, '-c', 'import time; time.sleep(60)'], cwd=tmp_path) as sim:
            pid = sim.process.pid
            assert json.loads((tmp_path / 'resource.json').read_text())['pid'] == pid
            raise RuntimeError('experiment failed')
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert json.loads((tmp_path / 'cleanup.json').read_text())['process_group_alive'] is False


def test_noninteractive_fixture_keeps_owned_input_open(tmp_path):
    import time
    ready = tmp_path / 'ready'
    command = [sys.executable, '-c',
               'import pathlib,sys; pathlib.Path("ready").write_text("ready"); sys.stdin.buffer.read(1)']
    with Simulator(tmp_path, command=command, cwd=tmp_path) as sim:
        deadline = time.monotonic() + 2
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists()
        time.sleep(0.1)
        assert sim.process.poll() is None, 'unattended input reached EOF'


def test_fixture_output_is_drained_without_unbounded_log_growth(tmp_path):
    command = [sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"x" * 1200000); sys.stdout.flush()']
    with Simulator(tmp_path, command=command, cwd=tmp_path, log_limit=4096) as sim:
        assert sim.process.wait(timeout=3) == 0
    assert (tmp_path / 'px4.log').stat().st_size == 4096
    report = json.loads((tmp_path / 'cleanup.json').read_text())
    assert report['log_bytes_received'] == 1200000
    assert report['log_truncated'] is True

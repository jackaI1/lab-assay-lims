import json
import os
import sys
import pytest
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('lab_experiment', Path(__file__).resolve().parents[1]/'scripts/run_experiment.py')
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
process = experiment.process


def test_failed_phase_stops_its_owned_process_group(tmp_path):
    log = tmp_path/'fixture.log'
    with pytest.raises(ValueError, match='scenario failed'):
        with process([sys.executable, '-c', 'import time; time.sleep(60)'], log) as child:
            pid = child.pid
            raise ValueError('scenario failed')
    audit = json.loads((tmp_path/'fixture.log.owner.json').read_text())
    assert audit['pid'] == pid
    assert audit['live_descendants_after_cleanup'] == []
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)

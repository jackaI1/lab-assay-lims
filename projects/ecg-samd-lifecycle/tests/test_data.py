import hashlib
from io import BytesIO
from pathlib import Path

import pytest

from ecg_lifecycle.data import ensure_record, verify_file, load_manifest


def test_checksum_rejects_corruption(tmp_path):
    path = tmp_path / '100.dat'
    path.write_bytes(b'original')
    digest = hashlib.sha256(b'original').hexdigest()
    verify_file(path, digest)
    path.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        verify_file(path, digest)


def test_only_public_allowlisted_records(tmp_path):
    for record in ['../../secret', '999', '/tmp/100', '100.atr']:
        with pytest.raises(ValueError, match='record'):
            ensure_record(record, tmp_path)
    assert set(load_manifest()['records']) == {'100', '201', '203'}


def test_download_failure_never_leaves_valid_cache(tmp_path, monkeypatch):
    monkeypatch.setattr('ecg_lifecycle.data.urlopen', lambda *a, **kw: BytesIO(b'wrong content'))
    with pytest.raises(ValueError, match='checksum'):
        ensure_record('100', tmp_path)
    assert not list(tmp_path.glob('*.part'))
    assert not (tmp_path / '100.dat').exists()

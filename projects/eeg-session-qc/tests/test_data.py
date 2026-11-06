import hashlib
from pathlib import Path

import pytest

from eeg_session_qc.data import download_demo, read_edf


def test_download_reuses_pinned_file_and_rejects_tampering(tmp_path):
    payload = b"public-test-fixture"
    manifest = [
        {
            "file": "S001R01.edf",
            "url": "https://example.invalid/test",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ]
    (tmp_path / "S001R01.edf").write_bytes(payload)
    assert download_demo(tmp_path, manifest)[0] == tmp_path / "S001R01.edf"
    (tmp_path / "S001R01.edf").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        download_demo(tmp_path, manifest)


def test_unreadable_edf_raises(tmp_path):
    path = tmp_path / "broken.edf"
    path.write_text("bad")
    with (
        pytest.warns(RuntimeWarning, match="measurement date"),
        pytest.raises((ValueError, OSError)),
    ):
        read_edf(path)


def test_demo_edf_integration():
    files = sorted(Path("data").glob("*.edf"))
    if not files:
        pytest.skip("Run eeg-qc demo to download public integration data")
    raw = read_edf(files[0])
    assert len(raw.ch_names) == 64
    assert raw.info["sfreq"] == 160


def test_download_installs_verified_file_and_cleans_failed_transfer(tmp_path):
    payload = tmp_path / "public-fixture"
    payload.write_bytes(b"public fixture data")
    manifest = [
        {
            "file": "fixture.edf",
            "url": payload.as_uri(),
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        }
    ]
    destination = tmp_path / "downloads"
    paths = download_demo(destination, manifest)
    assert paths[0].read_bytes() == payload.read_bytes()
    assert not list(destination.glob("*.download"))
    paths[0].unlink()
    manifest[0]["sha256"] = "invalid"
    with pytest.raises(ValueError, match="checksum"):
        download_demo(destination, manifest)
    assert not list(destination.iterdir())


def test_typed_edf_keeps_auxiliary_sensors_out_and_normalizes_eeg_names(tmp_path):
    import mne
    import numpy as np

    t = np.arange(1280) / 160
    data = np.array(
        [
            10e-6 * np.sin(2 * np.pi * 10 * t),
            12e-6 * np.sin(2 * np.pi * 11 * t),
            500e-6 * np.sin(2 * np.pi * 3 * t),
            400e-6 * np.sin(2 * np.pi * 37 * t),
        ]
    )
    raw = mne.io.RawArray(
        data,
        mne.create_info(["Fp1", "Fp2", "Eye", "Jaw"], 160, ["eeg", "eeg", "eog", "emg"]),
        verbose=False,
    )
    path = tmp_path / "typed.edf"
    mne.export.export_raw(path, raw, add_ch_type=True, verbose=False)
    loaded = read_edf(path)
    assert loaded.ch_names == ["Fp1", "Fp2"]
    assert loaded.get_channel_types() == ["eeg", "eeg"]

import mne
import numpy as np
import pytest

from eeg_session_qc.quality import analyze


def raw_signal(seconds=8, sfreq=160):
    rng = np.random.default_rng(22)
    t = np.arange(int(seconds * sfreq)) / sfreq
    data = 10 * np.sin(2 * np.pi * 10 * t)[None, :] + rng.normal(0, 2, (8, len(t)))
    return mne.io.RawArray(
        data * 1e-6,
        mne.create_info(["Fp1", "Fp2", "F3", "F4", "C3", "C4", "T7", "T8"], sfreq, "eeg"),
        verbose=False,
    )


def test_clean_signal_usable_and_input_unchanged():
    raw = raw_signal()
    before = raw.get_data().copy()
    result = analyze(raw, "clean")
    assert result["status"] == "usable"
    assert result["score"] == 100
    assert not any(result["counts"].values())
    np.testing.assert_array_equal(raw.get_data(), before)


@pytest.mark.parametrize("kind", ["flat", "noisy", "line", "blink", "muscle"])
def test_known_artifact_has_type_channel_and_time(kind):
    raw = raw_signal()
    t = np.arange(320) / 160
    if kind == "flat":
        raw._data[0, :320] = 0
    elif kind == "noisy":
        raw._data[0, :320] += np.random.default_rng(1).normal(0, 150e-6, 320)
    elif kind == "line":
        raw._data[0, :320] += 45e-6 * np.sin(2 * np.pi * 60 * t)
    elif kind == "blink":
        raw._data[:2, :320] += 220e-6 * np.exp(-(((t - 1) / 0.12) ** 2))
    else:
        raw._data[6:, :320] += 35e-6 * np.sin(2 * np.pi * 37 * t)
    result = analyze(raw, kind)
    hits = [w for w in result["windows"] if w["flags"][kind]]
    assert hits and hits[0]["start"] == 0
    assert result["status"] == "usable with caveats"
    assert result["reasons"]


def test_flat_session_not_usable_and_score_zero():
    raw = raw_signal()
    raw._data[:] = 0
    result = analyze(raw, "dead")
    assert result["status"] == "not usable"
    assert result["score"] == 0


@pytest.mark.parametrize("sfreq,seconds", [(80, 8), (160, 1)])
def test_unsupported_input_rejected(sfreq, seconds):
    with pytest.raises(ValueError):
        analyze(raw_signal(seconds, sfreq), "invalid")


def test_nan_rejected():
    raw = raw_signal()
    raw._data[0, 2] = np.nan
    with pytest.raises(ValueError, match="finite"):
        analyze(raw, "invalid")


def test_missing_frontal_is_caveat_not_silent_negative():
    result = analyze(raw_signal().drop_channels(["Fp1", "Fp2"]), "no front")
    assert result["status"] == "usable with caveats"
    assert "not assessed" in " ".join(result["reasons"])


def test_tail_is_scored_and_bad_channels_are_not_ignored():
    raw = raw_signal(seconds=9)
    raw.info["bads"] = ["Fp1"]
    raw._data[0, -160:] = 0
    result = analyze(raw, "tail")
    assert result["windows"][-1]["stop"] == 9
    assert result["counts"]["flat"] > 0
    assert result["preexisting_bads"] == ["Fp1"]


def test_single_dead_sensor_is_a_caveat_and_scales_by_sensor_time():
    raw = raw_signal()
    raw._data[0] = 0
    result = analyze(raw)
    assert result["bad_channel_time_fraction"] == 0.125
    assert result["artifact_time_fraction"] == 0
    assert result["score"] == 87.5
    assert result["status"] == "usable with caveats"


def test_line_frequency_50_is_supported():
    raw = raw_signal()
    t = np.arange(raw.n_times) / raw.info["sfreq"]
    raw._data[2] += 40e-6 * np.sin(2 * np.pi * 50 * t)
    result = analyze(raw, line_hz=50)
    assert result["counts"]["line"] == len(result["windows"])
    assert result["status"] == "not usable"


def test_reported_thresholds_are_the_thresholds_actually_applied(monkeypatch):
    from eeg_session_qc.quality import THRESHOLDS

    raw = raw_signal()
    raw._data[2] += np.random.default_rng(5).normal(0, 55e-6, raw.n_times)
    assert analyze(raw)["counts"]["noisy"] == 0
    monkeypatch.setitem(THRESHOLDS, "noisy_sd_uv", 30)
    result = analyze(raw)
    assert result["counts"]["noisy"] > 0
    assert result["thresholds"]["noisy_sd_uv"] == 30
    assert result["windows"][0]["metrics"]["F3"]["sd_uv"] > 30

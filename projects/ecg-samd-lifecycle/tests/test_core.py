"""Hand-derived expectations catch algorithm and evaluation mistakes."""
import numpy as np
import pytest

from ecg_lifecycle.core import (
    detect_peaks, screen_windows, match_beats, rates, rhythm_label, beat_samples,
)


def test_signal_rejection():
    for signal, fs in [(np.zeros(3600), 360), (np.ones(3600), 360),
                       ([0, 1, float('nan')], 360), ([0, 1, float('inf')], 360),
                       (np.ones((20, 2)), 360), ([0, 1], 0), ([0, 1], float('nan')),
                       ([0, 1], 360)]:
        with pytest.raises(ValueError):
            detect_peaks(signal, fs)


def test_regular_and_irregular_windows():
    regular = screen_windows(np.arange(0, 10800, 360), 360, 10800)[0]
    assert regular['status'] == 'regular'
    assert regular['mean_rr_s'] == 1
    assert regular['cv'] == 0
    assert regular['rmssd_s'] == 0
    irregular = screen_windows(np.cumsum([0] + [180, 540] * 14), 360, 10800)[0]
    assert irregular['status'] == 'irregular'
    assert irregular['cv'] == pytest.approx(0.5)
    assert irregular['rmssd_s'] == 1


def test_insufficient_is_not_regular():
    assert screen_windows([0, 360], 360, 10800)[0]['status'] == 'insufficient_data'
    peaks = np.cumsum([0] + [360] * 12 + [1000])
    assert screen_windows(peaks, 360, 10800)[0]['status'] == 'insufficient_data'


def test_window_boundaries_and_peak_validation():
    # A peak at 30 s belongs only to window two; partial final window is omitted.
    windows = screen_windows(np.arange(0, 21601, 360), 360, 21700)
    assert len(windows) == 2
    assert [w['beat_count'] for w in windows] == [30, 30]
    for peaks in [[1, 1], [2, 1], [-1, 3], [0, 21600], [0, 1.5]]:
        with pytest.raises(ValueError):
            screen_windows(peaks, 360, 21600)


def test_one_to_one_metrics_and_tolerance():
    result = match_beats([100, 200, 300], [90, 105, 210, 500], 10)
    assert result == {'tp': 2, 'fp': 2, 'fn': 1}
    assert rates(result) == {'sensitivity': 2 / 3, 'ppv': 0.5}
    assert match_beats([100], [111], 10) == {'tp': 0, 'fp': 1, 'fn': 1}
    assert rates({'tp': 0, 'fp': 0, 'fn': 0}) == {'sensitivity': None, 'ppv': None}


def test_nonbeat_events_excluded():
    assert beat_samples([0, 100, 200, 300, 400, 500], ['+', 'N', 'V', '~', '|', '/']).tolist() == [100, 200, 500]


def test_rhythm_duration_and_unknown_labels():
    events = [(0, '(N'), (20, '(AFIB'), (95, '(N')]
    assert rhythm_label(0, 100, events) is None  # 75%, mixed
    assert rhythm_label(20, 95, events) is True
    assert rhythm_label(0, 20, events) is False
    assert rhythm_label(0, 100, [(80, '(AFIB')]) is None  # unknown early segment
    assert rhythm_label(100, 200, [(0, '(AFIB')]) is True  # carry state forward
    assert rhythm_label(0, 100, [(0, '(N'), (20, '(AFIB')]) is True  # 80% inclusive
    assert rhythm_label(0, 100, [(0, '(AFIB'), (20, '(N')]) is False


def test_unrecognized_rhythm_is_unknown():
    assert rhythm_label(0, 100, [(0, '(UNRECOGNIZED')]) is None


def test_both_irregularity_conditions_are_required():
    # A slow change in interval length has high spread but small successive changes.
    smooth = np.cumsum([0] + list(range(180, 541, 18)))
    row = screen_windows(smooth, 360, 10800)[0]
    assert row['cv'] > 0.12
    assert row['normalized_rmssd'] == pytest.approx(0.05)
    assert row['status'] == 'regular'
    # Alternating small changes have low spread despite large successive changes.
    alternating = np.cumsum([0] + [338, 382] * 14)
    row = screen_windows(alternating, 360, 10800)[0]
    assert row['cv'] < 0.12
    assert row['normalized_rmssd'] > 0.08
    assert row['status'] == 'regular'


def test_nonfinite_beat_indices_are_rejected():
    for reference, predicted in [([float('nan')], [100]), ([100], [float('inf')]),
                                  ([100.5], [100]), ([-1], [100]), ([[100]], [100])]:
        with pytest.raises(ValueError):
            match_beats(reference, predicted, 54)

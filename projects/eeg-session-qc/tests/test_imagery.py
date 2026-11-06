import numpy as np

from eeg_session_qc.imagery import bandpower_features, evaluate


def test_bandpower_distinguishes_frequency():
    t = np.arange(640) / 160
    x = np.array([[np.sin(2 * np.pi * 10 * t)], [np.sin(2 * np.pi * 20 * t)]])
    features = bandpower_features(x, 160)
    assert features[0, 0] > features[0, 1]
    assert features[1, 1] > features[1, 0]


def test_evaluation_keeps_subjects_separate_and_bootstraps_people():
    rng = np.random.default_rng(2)
    subjects = np.repeat(np.arange(6), 12)
    y = np.tile(np.repeat([0, 1], 6), 6)
    x = (y + rng.normal(0, 0.3, len(y)))[:, None]
    result = evaluate(x, y, subjects, n_boot=100)
    assert len(result["held_out"]["subject_accuracy"]) == 6
    assert len(result["within_subject"]["subject_accuracy"]) == 6
    assert result["held_out"]["ci"][0] <= result["held_out"]["mean"] <= result["held_out"]["ci"][1]

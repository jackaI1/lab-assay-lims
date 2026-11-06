from ecg_lifecycle.evaluate import score_windows


def test_window_scoring_includes_abstentions():
    statuses = ['irregular', 'regular', 'irregular', 'regular',
                'insufficient_data', 'insufficient_data', 'regular']
    windows = [dict(start_s=i * 30, end_s=(i + 1) * 30, status=status)
               for i, status in enumerate(statuses)]
    # TP, FN, FP, TN, positive abstention, negative abstention, unknown.
    events = [(0, '(AFIB'), (60, '(N'), (120, '(AFIB'), (150, '(N'), (180, '(UNKNOWN')]
    scores = score_windows(windows, 360, [(s * 360, label) for s, label in events])
    assert scores['tp'] == scores['fn'] == scores['fp'] == scores['tn'] == 1
    assert scores['sensitivity'] == scores['ppv'] == 0.5
    assert scores['abstained_positive'] == scores['abstained_negative'] == 1
    assert scores['conservative_sensitivity'] == 1 / 3
    assert scores['excluded_mixed_or_unknown'] == 1

"""Independent annotations are used here, never by the detector."""
import json
from pathlib import Path
import wfdb

from .core import detect_peaks, screen_windows, beat_samples, match_beats, rates, rhythm_label
from .data import ensure_record, load_manifest

WARNING = ('Learning exercise, not a cleared device. Do not use for diagnosis, triage or treatment. '
           'Only public de-identified historical recordings are used; no private patient data is used '
           'and no new patient data is collected.')


def evaluate_record(record_id, cache=None):
    path = ensure_record(record_id, cache)
    record = wfdb.rdrecord(str(path), channels=[0])
    annotation = wfdb.rdann(str(path), 'atr')
    signal = record.p_signal[:, 0]
    peaks = detect_peaks(signal, record.fs)
    windows = screen_windows(peaks, record.fs, len(signal))
    qrs = match_beats(beat_samples(annotation.sample, annotation.symbol), peaks, int(0.15 * record.fs))
    events = [(int(sample), note.strip().rstrip('\x00'))
              for sample, symbol, note in zip(annotation.sample, annotation.symbol,
                                              annotation.aux_note, strict=True)
              if symbol == '+' and note.strip().startswith('(')]
    proxy = score_windows(windows, record.fs, events)
    return dict(duration_s=len(signal) / record.fs, sample_rate_hz=record.fs,
                channel=0, lead=record.sig_name[0], qrs=dict(qrs, **rates(qrs)),
                window_counts={key: sum(w['status'] == key for w in windows)
                               for key in ('regular', 'irregular', 'insufficient_data')} | {'total': len(windows)},
                omitted_tail_s=len(signal) / record.fs - 30 * len(windows),
                afib_proxy=proxy,
                windows=windows)


def evaluate(records=('100', '201', '203'), cache=None):
    return dict(learning_only=True, warning=WARNING, dataset=load_manifest(),
                method=dict(qrs='WFDB XQRS, channel 0', tolerance_s=0.15,
                            window_s=30, min_rr=10, rr_range_s=[0.25, 2.5], cv_threshold=0.12,
                            normalized_rmssd_threshold=0.08, afib_positive_fraction=0.8,
                            afib_negative_fraction=0.2),
                records={record: evaluate_record(record, cache) for record in records})


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def score_windows(windows, fs, events):
    confusion = dict(tp=0, fp=0, fn=0, tn=0)
    excluded = abstained_positive = abstained_negative = 0
    for window in windows:
        reference = rhythm_label(round(window['start_s'] * fs),
                                 round(window['end_s'] * fs), events)
        window['afib_reference'] = reference
        if reference is None:
            excluded += 1
        elif window['status'] == 'insufficient_data':
            if reference:
                abstained_positive += 1
            else:
                abstained_negative += 1
        else:
            flag = window['status'] == 'irregular'
            confusion['tp' if reference and flag else 'fn' if reference else 'fp' if flag else 'tn'] += 1
    conservative = dict(confusion, fn=confusion['fn'] + abstained_positive)
    return dict(confusion, **rates(confusion), excluded_mixed_or_unknown=excluded,
                abstained_positive=abstained_positive, abstained_negative=abstained_negative,
                conservative_sensitivity=rates(conservative)['sensitivity'])

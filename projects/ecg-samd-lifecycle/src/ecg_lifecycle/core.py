"""Transparent timing features. An irregular flag is not a diagnosis."""
import numpy as np
from wfdb import processing

BEAT_SYMBOLS = frozenset('NLRBAaJSVrFejEn/fQ')
WINDOW_SECONDS = 30
KNOWN_RHYTHMS = frozenset(['(N', '(AFIB', '(AFL', '(AB', '(B', '(BII', '(IVR',
                           '(NOD', '(P', '(PREX', '(SBR', '(SVTA', '(T', '(VFL', '(VT'])


def _rate(fs):
    if not np.isfinite(fs) or not 100 <= fs <= 1000:
        raise ValueError('sample rate must be finite and between 100 and 1000 Hz')


def detect_peaks(signal, fs):
    _rate(fs)
    signal = np.asarray(signal, dtype=float)
    if (signal.ndim != 1 or len(signal) < 10 * fs
            or not np.isfinite(signal).all() or np.ptp(signal) < 1e-6):
        raise ValueError('signal must be finite, nonflat, one-dimensional and at least 10 seconds')
    return processing.xqrs_detect(sig=signal, fs=fs, verbose=False)


def screen_windows(peaks, fs, n_samples):
    _rate(fs)
    peaks = np.asarray(peaks)
    if (peaks.ndim != 1 or not np.isfinite(peaks).all()
            or np.any(peaks != np.floor(peaks)) or np.any(np.diff(peaks) <= 0)
            or np.any(peaks < 0) or np.any(peaks >= n_samples)):
        raise ValueError('peaks must be unique increasing sample indices within the signal')
    if not isinstance(n_samples, (int, np.integer)) or n_samples < 0:
        raise ValueError('n_samples must be a nonnegative integer')
    width = int(WINDOW_SECONDS * fs)
    windows = []
    for start in range(0, n_samples - width + 1, width):
        end = start + width
        selected = peaks[(peaks >= start) & (peaks < end)]
        rr = np.diff(selected) / fs
        row = dict(start_s=start / fs, end_s=end / fs, beat_count=len(selected),
                   status='insufficient_data', mean_rr_s=None, cv=None, rmssd_s=None,
                   normalized_rmssd=None)
        if len(rr) >= 10 and np.all((rr >= 0.25) & (rr <= 2.5)):
            mean = float(np.mean(rr))
            cv = float(np.std(rr) / mean)
            rmssd = float(np.sqrt(np.mean(np.diff(rr) ** 2)))
            row.update(mean_rr_s=mean, cv=cv, rmssd_s=rmssd,
                       normalized_rmssd=rmssd / mean,
                       status='irregular' if cv >= 0.12 and rmssd / mean >= 0.08 else 'regular')
        windows.append(row)
    return windows


def beat_samples(samples, symbols):
    return np.asarray([int(sample) for sample, symbol in zip(samples, symbols, strict=True)
                       if symbol in BEAT_SYMBOLS], dtype=int)


def match_beats(reference, predicted, tolerance):
    """Chronological one-to-one matching, inclusive tolerance, maximum cardinality."""
    reference, predicted = np.asarray(reference), np.asarray(predicted)
    if (not np.isfinite(tolerance) or tolerance < 0
            or any(x.ndim != 1 or not np.isfinite(x).all() or np.any(x < 0)
                   or np.any(x != np.floor(x)) or np.any(np.diff(x) <= 0)
                   for x in (reference, predicted))):
        raise ValueError('finite ordered unique sample indices and nonnegative tolerance required')
    i = j = tp = 0
    while i < len(reference) and j < len(predicted):
        if predicted[j] < reference[i] - tolerance:
            j += 1
        elif predicted[j] > reference[i] + tolerance:
            i += 1
        else:
            tp += 1
            i += 1
            j += 1
    return dict(tp=tp, fp=len(predicted) - tp, fn=len(reference) - tp)


def rates(counts):
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    return dict(sensitivity=tp / (tp + fn) if tp + fn else None,
                ppv=tp / (tp + fp) if tp + fp else None)


def rhythm_label(start, end, events):
    """AFIB duration proxy, with unknown and mixed windows excluded."""
    state = None
    cursor, afib, known = start, 0, 0
    for sample, label in sorted(events):
        label = label if label in KNOWN_RHYTHMS else None
        if sample <= start:
            state = label
            continue
        if sample >= end:
            break
        if state is not None:
            known += sample - cursor
            if state == '(AFIB':
                afib += sample - cursor
        cursor, state = sample, label
    if state is not None:
        known += end - cursor
        if state == '(AFIB':
            afib += end - cursor
    if known != end - start:
        return None
    fraction = afib / (end - start)
    return True if fraction >= 0.8 else False if fraction <= 0.2 else None

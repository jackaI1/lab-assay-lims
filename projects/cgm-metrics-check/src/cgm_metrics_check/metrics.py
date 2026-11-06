"""Fixed-cadence consensus metrics, with explicit missing-data denominators."""
from collections import defaultdict
from datetime import datetime, timedelta
import math
from statistics import fmean, pstdev
from typing import Iterable

from .model import Reading, utc

MIN_COVERAGE = 0.70
MIN_DAYS = 14


def analyze(readings: Iterable[Reading], *, start: datetime, end: datetime,
            cadence_minutes: float, allow_short_window: bool = False) -> dict:
    """Analyze one series on [start, end). Refuse metrics below 70% coverage.

    Every in-window reading must lie on the grid anchored at start. Duplicate
    instants cannot increase coverage; conflicting values invalidate the slot.
    Short-window mode labels results exploratory; it never bypasses coverage.
    """
    start, end = utc(start), utc(end)
    if isinstance(cadence_minutes, bool) or not math.isfinite(cadence_minutes) or cadence_minutes <= 0:
        raise ValueError('cadence_minutes must be finite and positive')
    step = timedelta(minutes=cadence_minutes)
    if step <= timedelta(0) or end <= start:
        raise ValueError('window and cadence must have positive duration')
    slots = (end - start) / step
    if not slots.is_integer() or not 1 <= slots <= 1_000_000:
        raise ValueError('window must contain a whole number of cadence intervals, at most 1000000')
    expected = int(slots)
    groups = defaultdict(list)
    units = set()
    outside = 0
    for reading in readings:
        stamp = utc(reading.timestamp)
        if not start <= stamp < end:
            outside += 1
            continue
        units.add(reading.unit)
        index = (stamp - start) / step
        if not index.is_integer():
            raise ValueError(f'reading at {stamp.isoformat()} is off the declared sampling grid')
        groups[int(index)].append(reading.mg_dl)

    accepted = {}
    conflicts = 0
    for index, values in groups.items():
        if all(math.isclose(values[0], value, rel_tol=1e-9, abs_tol=1e-9) for value in values):
            accepted[index] = values[0]
        else:
            conflicts += 1
    n = len(accepted)
    fraction = n / expected
    gaps = []
    gap_start = None
    daily = {}
    for index in range(expected):
        stamp = start + index * step
        day = stamp.date().isoformat()
        entry = daily.setdefault(day, {'date': day, 'expected_readings': 0, 'readings_used': 0})
        entry['expected_readings'] += 1
        entry['readings_used'] += index in accepted
        if index not in accepted and gap_start is None:
            gap_start = index
        if index in accepted and gap_start is not None:
            gaps.append(_gap(start, step, gap_start, index))
            gap_start = None
    if gap_start is not None:
        gaps.append(_gap(start, step, gap_start, expected))
    for entry in daily.values():
        entry['coverage_percent'] = 100 * entry['readings_used'] / entry['expected_readings']

    reasons = []
    if fraction < MIN_COVERAGE:
        reasons.append('coverage below 70% of expected readings')
    if end - start < timedelta(days=MIN_DAYS) and not allow_short_window:
        reasons.append('analysis window shorter than 14 days')
    reason = '; '.join(reasons)
    values = list(accepted.values())
    metrics = {}

    def record(name, unit, compute):
        metrics[name] = {
            'value': None if reason else round(compute(), 10), 'unit': unit,
            'status': 'refused' if reason else 'reported', 'reason': reason or None,
            'readings_used': n, 'expected_readings': expected,
            'coverage_percent': fraction * 100,
        }

    bands = {
        'tir': lambda x: 70 <= x <= 180,
        'tbr': lambda x: x < 70,
        'tar': lambda x: x > 180,
        'tbr_level1': lambda x: 54 <= x < 70,
        'tbr_level2': lambda x: x < 54,
        'tar_level1': lambda x: 180 < x <= 250,
        'tar_level2': lambda x: x > 250,
    }
    for name, predicate in bands.items():
        record(name, '%', lambda predicate=predicate: 100 * sum(predicate(x) for x in values) / n)
    record('mean_glucose', 'mg/dL', lambda: fmean(values))
    record('gmi', '%', lambda: 3.31 + 0.02392 * fmean(values))
    record('cv', '%', lambda: 100 * pstdev(values) / fmean(values))
    return {
        'notice': 'Not a medical device. No treatment advice.',
        'window': {'start': start.isoformat(), 'end_exclusive': end.isoformat(),
                   'cadence_minutes': cadence_minutes,
                   'days': (end - start).total_seconds() / 86400,
                   'exploratory': end - start < timedelta(days=MIN_DAYS)},
        'readings_used': n, 'expected_readings': expected, 'coverage_percent': fraction * 100,
        'metrics': metrics,
        'quality': {'mixed_units': len(units) > 1, 'units_seen': sorted(units),
                    'duplicate_rows': sum(len(v) - 1 for v in groups.values()),
                    'conflicting_timestamps': conflicts, 'out_of_window_rows': outside,
                    'gaps': gaps,
                    'longest_gap_minutes': max((g['minutes'] for g in gaps), default=0)},
        'daily_coverage': list(daily.values()),
    }


def _gap(start, step, first, stop):
    return {'start': (start + first * step).isoformat(),
            'end_exclusive': (start + stop * step).isoformat(),
            'missing_readings': stop - first,
            'minutes': (stop - first) * step.total_seconds() / 60}

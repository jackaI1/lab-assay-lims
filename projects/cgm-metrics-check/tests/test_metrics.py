from datetime import datetime, timedelta, timezone
import math

import pytest

from cgm_metrics_check import Reading, analyze

START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def rows(values, step=5):
    return [Reading(START + timedelta(minutes=i * step), v, 'mg/dL') for i, v in enumerate(values)]


def short(readings, slots, **kwargs):
    return analyze(readings, start=START, end=START + timedelta(minutes=5 * slots),
                   cadence_minutes=5, allow_short_window=True, **kwargs)


def test_hand_computed_metrics():
    # 50,100,150,200: mean 125; population variance 3125; 2/4 in range.
    report = short(rows([50, 100, 150, 200]), 4)
    m = report['metrics']
    assert m['mean_glucose']['value'] == 125
    assert m['gmi']['value'] == pytest.approx(6.3)
    assert m['cv']['value'] == pytest.approx(44.72135955)
    for name, expected in [('tir', 50), ('tbr', 25), ('tar', 25), ('tbr_level2', 25), ('tar_level2', 0)]:
        assert m[name]['value'] == expected
    assert all(x['readings_used'] == 4 and x['expected_readings'] == 4
               and x['coverage_percent'] == 100 for x in m.values())
    assert report['window']['exploratory'] is True


def test_exact_boundaries():
    m = short(rows([53, 54, 69, 70, 180, 181, 250, 251]), 8)['metrics']
    assert m['tir']['value'] == 25
    assert m['tbr']['value'] == 37.5
    assert m['tar']['value'] == 37.5
    assert m['tbr_level1']['value'] == 25
    assert m['tbr_level2']['value'] == 12.5
    assert m['tar_level1']['value'] == 25
    assert m['tar_level2']['value'] == 12.5


def test_coverage_threshold_is_inclusive_and_cannot_be_relaxed():
    assert short(rows([100] * 7), 10)['metrics']['tir']['value'] == 100
    report = short(rows([100] * 6), 10)
    assert report['coverage_percent'] == 60
    assert all(m['value'] is None and 'coverage' in m['reason'] for m in report['metrics'].values())
    assert all(m['readings_used'] == 6 for m in report['metrics'].values())


def test_normal_report_requires_fourteen_days():
    report = analyze(rows([100] * 4), start=START, end=START + timedelta(minutes=20), cadence_minutes=5)
    assert all(m['value'] is None and '14 days' in m['reason'] for m in report['metrics'].values())
    full = analyze(rows([100] * 4032), start=START, end=START + timedelta(days=14), cadence_minutes=5)
    assert full['metrics']['tir']['value'] == 100
    assert len(full['daily_coverage']) == 14


def test_gaps_include_window_edges_and_never_fill():
    report = short(rows([100] * 10)[2:4] + rows([200] * 10)[6:9], 10)
    assert report['coverage_percent'] == 50
    assert [g['missing_readings'] for g in report['quality']['gaps']] == [2, 2, 1]
    assert report['quality']['longest_gap_minutes'] == 10
    assert report['daily_coverage'][0]['readings_used'] == 5


def test_duplicate_values_count_once_and_conflicts_drop_whole_slot():
    source = rows([100] * 10)
    report = short(source + [source[0], Reading(START + timedelta(minutes=5), 200, 'mg/dL')], 10)
    assert report['readings_used'] == 9
    assert report['quality']['duplicate_rows'] == 2
    assert report['quality']['conflicting_timestamps'] == 1
    assert report['metrics']['mean_glucose']['value'] == 100
    assert report['metrics']['tir']['coverage_percent'] == 90


def test_mixed_units_are_flagged_and_normalized():
    report = short([Reading(START, 180.182, 'mg/dL'),
                    Reading(START + timedelta(minutes=5), 10, 'mmol/L')], 2)
    assert report['quality']['mixed_units'] is True
    assert report['metrics']['mean_glucose']['value'] == pytest.approx(180.182)


def test_equivalent_units_at_same_timestamp_are_not_a_conflict():
    report = short([Reading(START, 180.182, 'mg/dL'), Reading(START, 10, 'mmol/L')], 1)
    assert report['readings_used'] == 1
    assert report['quality']['conflicting_timestamps'] == 0


def test_outside_window_excluded_and_timezones_compare_as_instants():
    offset = timezone(timedelta(hours=-5))
    report = short([Reading(START.astimezone(offset), 100, 'mg/dL'),
                    Reading(START + timedelta(minutes=5), 999, 'mg/dL'),
                    Reading(START - timedelta(minutes=5), 999, 'mg/dL')], 1)
    assert report['metrics']['mean_glucose']['value'] == 100
    assert report['quality']['out_of_window_rows'] == 2


def test_empty_input_refuses_instead_of_dividing_by_zero():
    report = short([], 10)
    assert report['coverage_percent'] == 0
    assert report['quality']['gaps'][0]['missing_readings'] == 10
    assert all(x['value'] is None for x in report['metrics'].values())


@pytest.mark.parametrize('value', [0, -1, math.nan, math.inf, True])
def test_rejects_invalid_quantities(value):
    with pytest.raises(ValueError):
        Reading(START, value, 'mg/dL')


def test_rejects_unknown_or_missing_units_and_naive_timestamps():
    for unit in ['', 'mg/L']:
        with pytest.raises(ValueError, match='unit'):
            Reading(START, 100, unit)
    with pytest.raises(ValueError, match='timezone'):
        Reading(datetime(2025, 1, 1), 100, 'mg/dL')


@pytest.mark.parametrize('kwargs', [
    {'cadence_minutes': 0}, {'cadence_minutes': -1}, {'cadence_minutes': float('nan')},
    {'end': START}, {'end': START + timedelta(minutes=7)},
    {'start': datetime(2025, 1, 1)},
])
def test_invalid_window_or_cadence_is_rejected(kwargs):
    args = dict(start=START, end=START + timedelta(minutes=10), cadence_minutes=5)
    args.update(kwargs)
    with pytest.raises(ValueError):
        analyze([], **args)


def test_off_grid_input_is_rejected_instead_of_overcounted():
    with pytest.raises(ValueError, match='grid'):
        short([Reading(START + timedelta(minutes=1), 100, 'mg/dL')], 2)


def test_unit_conversion_overflow_is_an_input_error():
    with pytest.raises(ValueError, match='normalized'):
        Reading(START, 1e308, 'mmol/L')


def test_output_precision_is_stable_for_hand_computed_gmi():
    assert short(rows([50, 100, 150, 200]), 4)['metrics']['gmi']['value'] == 6.3

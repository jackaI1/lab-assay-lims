"""Strict CSV input: no silently dropped rows, guessed units or reordered samples."""

import csv
from pathlib import Path

import numpy as np


def read_csv(path, columns, text_columns=()):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV needs unique column headers")
        missing = set(columns) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if len(rows) < 3:
        raise ValueError("at least three data rows required")
    result = {}
    for column in columns:
        try:
            values = [row[column] for row in rows]
            if any(v is None or not v.strip() for v in values):
                raise ValueError("blank value")
            result[column] = np.array(values, dtype=str if column in text_columns else float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid values in {column}: {exc}") from exc
        if column not in text_columns and not np.isfinite(result[column]).all():
            raise ValueError(f"{column} must contain finite numbers")
    return result


def positive(**values):
    for name, value in values.items():
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")


def integrate(y, x):
    return float(np.trapezoid(y, x))


def signed_charge(time, current):
    """Integrate positive and negative piecewise-linear current, splitting zero crossings."""
    positive_c = negative_c = 0.0
    for dt, a, b in zip(np.diff(time), current[:-1], current[1:], strict=True):
        if a * b < 0:
            fraction = abs(a) / (abs(a) + abs(b))
            pieces = [(a, dt * fraction), (b, dt * (1 - fraction))]
            for value, width in pieces:
                if value > 0:
                    positive_c += value * width / 2
                else:
                    negative_c -= value * width / 2
        elif a >= 0 and b >= 0:
            positive_c += dt * (a + b) / 2
        else:
            negative_c -= dt * (a + b) / 2
    return positive_c / 3.6, negative_c / 3.6

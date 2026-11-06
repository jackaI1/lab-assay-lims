import csv

import pytest


@pytest.fixture
def csv_file(tmp_path):
    def write(header, rows, name="input.csv"):
        path = tmp_path / name
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    return write


@pytest.fixture
def cc_rows():
    def rows(cycle=1, scale=1, truncated=False):
        return [
            [cycle, 0, 1, 0, "charge"],
            [cycle, 1800 * scale, 1, 0.5, "charge"],
            [cycle, 3600 * scale, 1, 1, "charge"],
            [cycle, 3600 * scale, -0.9, 1, "discharge"],
            [cycle, 5400 * scale, -0.9, 0.5, "discharge"],
            [cycle, 7200 * scale, -0.9, 0.3 if truncated else 0, "discharge"],
        ]

    return rows

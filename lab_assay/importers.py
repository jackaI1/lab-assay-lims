"""Strict normalized reader exports. Vendor headers must be removed first."""

import csv
import io
import math
import re
import zipfile

from openpyxl import load_workbook

MAX_BYTES = 2_000_000


def well_name(value):
    match = re.fullmatch(r"([A-Ha-h])0?([1-9]|1[0-2])", str(value).strip())
    if not match:
        raise ValueError(f"Invalid 96-well address: {value}")
    return match[1].upper() + str(int(match[2]))


def parse_reader(filename: str, content: bytes) -> dict[str, float]:
    if len(content) > MAX_BYTES:
        raise ValueError("Reader file exceeds 2 MB limit")
    try:
        if filename.lower().endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 10_000_000:
                    raise ValueError("Expanded workbook exceeds 10 MB limit")
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
            try:
                if len(wb.worksheets) != 1:
                    raise ValueError("Use one worksheet per reader export")
                rows = []
                for row in wb.active.iter_rows(values_only=True):
                    rows.append(list(row))
                    if len(rows) > 100:
                        raise ValueError("Reader export has too many rows")
            finally:
                wb.close()
        elif filename.lower().endswith(".csv"):
            rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        else:
            raise ValueError("Choose a .csv or .xlsx reader export")
        rows = [r for r in rows if any(v is not None and str(v).strip() for v in r)]
        if not rows:
            raise ValueError("Reader export is empty")
        header = [str(v).strip().lower() for v in rows[0]]
        pairs = []
        if header == ["well", "signal"]:
            if len(rows) > 97:
                raise ValueError("At most 96 wells are supported")
            for row in rows[1:]:
                if len(row) != 2:
                    raise ValueError("Each row needs well and signal")
                pairs.append(row)
        elif len(header) == 13 and header[1:] == [str(i) for i in range(1, 13)]:
            if len(rows) != 9:
                raise ValueError("Matrix needs rows A through H")
            for letter, row in zip("ABCDEFGH", rows[1:], strict=True):
                if len(row) != 13 or str(row[0]).strip().upper() != letter:
                    raise ValueError("Matrix needs 12 signals in each ordered row A through H")
                pairs.extend((f"{letter}{i}", v) for i, v in enumerate(row[1:], 1))
        else:
            raise ValueError("Expected well,signal header or a 12-column plate matrix")
        signals = {}
        for well, value in pairs:
            well = well_name(well)
            if well in signals:
                raise ValueError(f"Duplicate well: {well}")
            if isinstance(value, bool):
                raise ValueError(f"Non-numeric signal at {well}")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"Non-finite signal at {well}")
            signals[well] = number
        if not signals:
            raise ValueError("Reader export contains no signals")
        return signals
    except (TypeError, UnicodeError, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError("Unreadable reader export; use the documented CSV/XLSX template") from exc

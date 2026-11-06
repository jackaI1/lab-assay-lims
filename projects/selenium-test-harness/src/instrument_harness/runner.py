"""Run a reusable sweep and retain pass, limit failure, and operational errors."""

import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import Any
from uuid import uuid4

from selenium.common.exceptions import WebDriverException

from .instrument import BenchSupply
from .models import InstrumentError, Limits, Settings


@dataclass(frozen=True)
class SweepStep:
    settings: Settings
    limits: Limits


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False, encoding="utf-8"
        ) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class SweepRunner:
    def __init__(self, instrument: BenchSupply) -> None:
        self.instrument = instrument

    def run(self, steps: Sequence[SweepStep], output: Path) -> dict[str, Any]:
        if not steps:
            raise ValueError("a sweep needs at least one step")
        report: dict[str, Any] = {
            "schema_version": 1,
            "run_id": str(uuid4()),
            "started_at": _now(),
            "units": {"voltage": "V", "current": "mA", "resistance": "ohm"},
            "planned_steps": len(steps),
            "passed": False,
            "steps": [],
            "shutdown_error": None,
        }
        try:
            for index, step in enumerate(steps):
                started = monotonic()
                result: dict[str, Any] = {
                    "index": index,
                    "started_at": _now(),
                    "settings": asdict(step.settings),
                    "limits": asdict(step.limits),
                    "reading": None,
                    "violations": [],
                    "error": None,
                }
                try:
                    self.instrument.configure(step.settings)
                    reading = self.instrument.measure()
                    result["reading"] = asdict(reading)
                    result["violations"] = step.limits.violations(reading, step.settings)
                    result["status"] = "fail" if result["violations"] else "pass"
                except (InstrumentError, WebDriverException) as exc:
                    result["status"] = "error"
                    result["error"] = {"type": type(exc).__name__, "message": str(exc)}
                result["duration_s"] = round(monotonic() - started, 6)
                report["steps"].append(result)
                _write_report(output, report)
                if result["status"] == "error":
                    break  # A timed-out device is unsafe to reconfigure blindly.
        finally:
            try:
                self.instrument.output_off()
            except (InstrumentError, WebDriverException) as exc:
                report["shutdown_error"] = {"type": type(exc).__name__, "message": str(exc)}
            report["finished_at"] = _now()
            report["passed"] = (
                len(report["steps"]) == len(steps)
                and all(step["status"] == "pass" for step in report["steps"])
                and report["shutdown_error"] is None
            )
            _write_report(output, report)
        return report

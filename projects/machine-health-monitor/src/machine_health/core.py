"""Validated, auditable telemetry and persistent alert incidents. Times are UTC epoch seconds."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TAGS = {
    "cycle_count": (int, 0, 2**32 - 1),
    "cycle_time": (float, 0.05, 120),
    "motor_running": (bool, 0, 1),
    "fault_code": (int, 0, 5),
    "fault_count": (int, 0, 2**32 - 1),
}
FAULTS = {
    0: "No fault",
    1: "Low tank",
    2: "Conveyor timeout",
    3: "Guard open",
    4: "Emergency stop",
    5: "Fill position did not clear",
}


@dataclass(frozen=True)
class Config:
    window_seconds: float = 20
    stale_seconds: float = 3
    poll_seconds: float = 1
    ideal_cycle_seconds: float = 2
    drift_max: float = 0.25
    fault_rate_max: float = 5
    availability_min: float = 0.8

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.availability_min > 1:
            raise ValueError("availability_min must be at most 1")


@dataclass(frozen=True)
class Frame:
    values: dict[str, Any]
    source_time: float | None
    good: bool = True
    reasons: tuple[str, ...] = ()


def safe_json(value):
    """Preserve nonfinite rejected input as readable text, without invalid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {"type": type(value).__name__, "representation": repr(value)[:512]}


class Monitor:
    def __init__(self, path: str | Path, config: Config | None = None):
        self.config = config or Config()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY, received REAL NOT NULL, source REAL,
                accepted INTEGER NOT NULL, raw TEXT NOT NULL, reasons TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS readings_received ON readings(received);
            CREATE INDEX IF NOT EXISTS readings_source ON readings(accepted, source);
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY, rule TEXT NOT NULL, message TEXT NOT NULL,
                state TEXT NOT NULL, opened REAL NOT NULL, last_seen REAL NOT NULL,
                acknowledged REAL, cleared REAL, occurrences INTEGER NOT NULL DEFAULT 1);
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_alert ON alerts(rule)
                WHERE state != 'cleared';
        """)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def _latest_source(self):
        return self.db.execute("SELECT MAX(source) FROM readings WHERE accepted=1").fetchone()[0]

    def ingest(self, frame: Frame, now: float):
        reasons = list(frame.reasons)
        for tag, (kind, low, high) in TAGS.items():
            value = frame.values.get(tag)
            if value is None:
                reasons.append(f"missing:{tag}")
            elif (
                (kind is bool and type(value) is not bool)
                or (kind is int and type(value) is not int)
                or (kind is float and type(value) not in (int, float))
            ):
                reasons.append(f"invalid_type:{tag}")
            elif not math.isfinite(value) or not low <= value <= high:
                reasons.append(f"out_of_range:{tag}")
        if frame.source_time is None or not math.isfinite(frame.source_time):
            reasons.append("missing:source_time")
        else:
            if now - frame.source_time > self.config.stale_seconds:
                reasons.append("stale")
            if frame.source_time - now > 1:
                reasons.append("future_timestamp")
            last = self._latest_source()
            if last is not None and frame.source_time <= last:
                reasons.append("duplicate" if frame.source_time == last else "out_of_order")
        if not frame.good:
            reasons.append("bad_status")
        accepted = not reasons
        with self.db:
            self.db.execute(
                "INSERT INTO readings(received,source,accepted,raw,reasons) VALUES(?,?,?,?,?)",
                (
                    now,
                    frame.source_time,
                    accepted,
                    json.dumps(safe_json(frame.values)),
                    json.dumps(reasons),
                ),
            )
            self._rule("connection_lost", False, "Cannot reach the machine data server.", now)
            self._rule(
                "data_quality",
                not accepted,
                "Machine readings rejected. Check timestamps, signal quality and tag values.",
                now,
            )
            if accepted:
                self._rule(
                    "machine_fault",
                    frame.values["fault_code"] != 0,
                    "Machine fault: "
                    + FAULTS[frame.values["fault_code"]]
                    + ". Inspect the cause locally before resetting the line.",
                    now,
                )
                metrics = self.metrics(now)
                self._rule(
                    "cycle_drift",
                    metrics["cycle_time_drift"] > self.config.drift_max,
                    "Cycles are slower than the configured target. Inspect the fill station.",
                    now,
                )
                rate = metrics["fault_rate_per_minute"]
                if rate is not None:
                    self._rule(
                        "fault_rate",
                        rate > self.config.fault_rate_max,
                        "Fault count is rising too quickly. Review fault codes before restarting.",
                        now,
                    )
                availability = metrics["availability"]
                if availability is not None:
                    self._rule(
                        "availability",
                        availability < self.config.availability_min,
                        "The line is spending too much observed time stopped or faulted.",
                        now,
                    )
        return {"accepted": accepted, "reasons": reasons}

    def disconnected(self, now: float, message: str):
        with self.db:
            self.db.execute(
                "INSERT INTO readings(received,source,accepted,raw,reasons) VALUES(?,NULL,0,?,?)",
                (now, json.dumps({"error": message}), '["connection_lost"]'),
            )
            self._rule("connection_lost", True, "Cannot reach the machine data server.", now)

    def _rule(self, rule: str, firing: bool, message: str, now: float):
        incident = self.db.execute(
            "SELECT id FROM alerts WHERE rule=? AND state!='cleared'", (rule,)
        ).fetchone()
        if firing and incident:
            self.db.execute(
                "UPDATE alerts SET last_seen=?,message=?, occurrences=occurrences+1 WHERE id=?",
                (now, message, incident["id"]),
            )
        elif firing:
            self.db.execute(
                "INSERT INTO alerts(rule,message,state,opened,last_seen) VALUES(?,?,'active',?,?)",
                (rule, message, now, now),
            )
        elif incident:
            self.db.execute(
                "UPDATE alerts SET state='cleared',cleared=? WHERE id=?", (now, incident["id"])
            )

    def acknowledge(self, incident_id: int, now: float):
        with self.db:
            result = self.db.execute(
                "UPDATE alerts SET state='acknowledged',acknowledged=? "
                "WHERE id=? AND state='active'",
                (now, incident_id),
            )
        return bool(result.rowcount)

    def alerts(self, limit=100):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT * FROM alerts WHERE state!='cleared' OR id IN "
                "(SELECT id FROM alerts WHERE state='cleared' ORDER BY id DESC LIMIT ?) "
                "ORDER BY id DESC",
                (limit,),
            )
        ]

    def readings(self, limit=100):
        return [
            dict(row) | {"raw": json.loads(row["raw"]), "reasons": json.loads(row["reasons"])}
            for row in self.db.execute("SELECT * FROM readings ORDER BY id DESC LIMIT ?", (limit,))
        ]

    def metrics(self, now: float):
        cfg = self.config
        rows = self.db.execute(
            "SELECT id,source,raw FROM readings WHERE accepted=1 "
            "AND source>=? AND source<=? ORDER BY source",
            (now - cfg.window_seconds, now + 1),
        ).fetchall()
        points = [(r["id"], r["source"], json.loads(r["raw"])) for r in rows]
        observed = running = cycles = faults = 0.0
        reset = False
        for (id0, t0, a), (id1, t1, b) in zip(points, points[1:]):
            dt = t1 - t0
            # A rejected sample or a long gap is not evidence that the line kept running.
            rejected = self.db.execute(
                "SELECT 1 FROM readings WHERE accepted=0 AND id>? AND id<? LIMIT 1",
                (id0, id1),
            ).fetchone()
            if dt > cfg.poll_seconds * 2.5 or rejected:
                continue
            dc = b["cycle_count"] - a["cycle_count"]
            df = b["fault_count"] - a["fault_count"]
            if dc < 0 or df < 0:
                reset = True
                continue
            observed += dt
            if a["motor_running"] and a["fault_code"] == 0:
                running += dt
                cycles += dc
            faults += df
        drift = (
            (sum(v["cycle_time"] for _, _, v in points) / len(points) / cfg.ideal_cycle_seconds - 1)
            if points
            else None
        )
        return {
            "availability": running / observed if observed else None,
            "performance": min(1.0, cfg.ideal_cycle_seconds * cycles / running)
            if running
            else None,
            "fault_rate_per_minute": faults * 60 / observed if observed else None,
            "cycle_time_drift": drift,
            "observed_seconds": observed,
            "running_seconds": running,
            "coverage": observed / cfg.window_seconds,
            "counter_reset": reset,
            "accepted_samples": len(points),
        }

    def snapshot(self, now: float):
        latest = self.readings(1)
        latest = latest[0] if latest else None
        current = bool(
            latest and latest["accepted"] and now - latest["source"] <= self.config.stale_seconds
        )
        metrics = self.metrics(now)
        alerts = self.alerts()
        active = [a for a in alerts if a["state"] != "cleared"]
        condition = (
            ("attention" if active else "healthy" if metrics["observed_seconds"] else "unknown")
            if current
            else "unknown"
        )
        fault = FAULTS.get(latest["raw"].get("fault_code"), "Unknown") if current else "Unknown"
        report = (
            f"Filling line: {condition}. Current fault: {fault}. "
            f"This report covers the last {self.config.window_seconds:g} seconds; "
            f"{metrics['observed_seconds']:.1f} seconds have usable interval data. "
            f"{len(active)} alert(s) need attention. "
            "Acknowledging records review; it does not clear a fault or start the machine. "
        )
        if not current:
            report += "Current machine condition cannot be confirmed. Check the data connection. "
        if metrics["counter_reset"]:
            report += "A counter reset was detected; the reset interval is excluded. "
        if active:
            report += "Next checks: " + " ".join(a["message"] for a in active)
        else:
            report += "Continue observing the line and review the retained reading history."
        return {
            "condition": condition,
            "latest": latest,
            "metrics": metrics,
            "alerts": alerts,
            "report": report,
            "config": asdict(self.config),
            "now": now,
        }

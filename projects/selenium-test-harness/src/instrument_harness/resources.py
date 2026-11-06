"""Optional local resource ledger for tests and command-line runs."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def process_start(pid: int) -> str:
    return subprocess.check_output(["ps", "-p", str(pid), "-o", "lstart="], text=True).strip()


def audit(event: str, **metadata: Any) -> None:
    """Resource logs stay local; they are separate from portable measurement results."""
    destination = os.environ.get("HARNESS_RESOURCE_LOG")
    if destination:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"at": datetime.now(UTC).isoformat(), "event": event, **metadata})
            )
            stream.write("\n")

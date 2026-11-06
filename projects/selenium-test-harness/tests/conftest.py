import os
from pathlib import Path

import pytest

from instrument_harness import BenchSupply, SupplyPage, chrome, simulator


@pytest.fixture(scope="session")
def resources():
    previous = os.environ.get("HARNESS_RESOURCE_LOG")
    os.environ["HARNESS_RESOURCE_LOG"] = str(Path(".artifacts/resources.jsonl").resolve())
    try:
        with simulator() as url, chrome() as driver:
            yield driver, url
    finally:
        if previous is None:
            os.environ.pop("HARNESS_RESOURCE_LOG", None)
        else:
            os.environ["HARNESS_RESOURCE_LOG"] = previous


@pytest.fixture
def supply(resources):
    driver, url = resources
    page = SupplyPage(driver, url, timeout=1.0)
    supply = BenchSupply(page)
    supply.connect()  # Reload the one owned tab; each test starts with clean device state.
    try:
        yield supply
    finally:
        supply.output_off()

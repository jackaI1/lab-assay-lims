"""One owned Chrome session with cleanup on success, failure, and startup errors."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from tempfile import TemporaryDirectory

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from .resources import audit, process_start


@contextmanager
def chrome(*, headless: bool = True) -> Iterator[webdriver.Chrome]:
    with TemporaryDirectory(prefix="instrument-harness-chrome-") as profile:
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--window-size=1100,800")
        options.add_argument("--disable-dev-shm-usage")
        if os.environ.get("CI"):
            options.add_argument("--no-sandbox")
        if binary := os.environ.get("CHROME_BINARY"):
            options.binary_location = binary
        service = Service(executable_path=os.environ.get("CHROMEDRIVER"))
        driver = None
        metadata: dict[str, object] = {}
        try:
            driver = webdriver.Chrome(options=options, service=service)
            browser_pid = driver.capabilities.get("goog:processID")
            metadata = {
                "owner": "instrument-harness",
                "pid": service.process.pid,
                "start": process_start(service.process.pid),
                "port": service.port,
                "browser_pid": browser_pid,
                "browser_start": process_start(browser_pid) if browser_pid else None,
                "profile": profile,
                "cleanup": "driver.quit(); service.stop() in chrome() finally",
            }
            audit("chrome-start", **metadata)
            yield driver
        finally:
            try:
                if driver is not None:
                    driver.quit()  # Closes every tab in this isolated, owned profile.
            finally:
                service.stop()
                if metadata:
                    audit("chrome-stop", **metadata, exited=service.process.poll() is not None)

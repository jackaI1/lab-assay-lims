"""Full browser exercise with explicitly owned foreground service and guaranteed teardown."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen

import pytest
from playwright.sync_api import expect, sync_playwright


@pytest.fixture
def live_demo(tmp_path, endpoint):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        http_port = sock.getsockname()[1]
    opc_port = urlparse(endpoint).port
    config = tmp_path / "rules.json"
    config.write_text(json.dumps({"window_seconds": 6}))
    command = [
        sys.executable,
        "-m",
        "machine_health.cli",
        "demo",
        "--port",
        str(http_port),
        "--opc-port",
        str(opc_port),
        "--db",
        str(tmp_path / "demo.sqlite3"),
        "--config",
        str(config),
    ]
    log_path = tmp_path / "service.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        metadata = {
            "owner": "tests/test_browser.py::live_demo",
            "pid": process.pid,
            "started_at": time.time(),
            "ports": [http_port, opc_port],
            "cleanup": f"kill -INT {process.pid} (owned child only)",
        }
        print("Owned test fixture: " + json.dumps(metadata))
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail("Demo exited: " + log_path.read_text()[-3000:])
                try:
                    with urlopen(f"http://127.0.0.1:{http_port}/api/status", timeout=1) as response:
                        if json.load(response)["latest"]:
                            break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("Demo did not start: " + log_path.read_text()[-3000:])
            yield f"http://127.0.0.1:{http_port}"
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            assert process.poll() is not None
            for port in (http_port, opc_port):
                with socket.socket() as sock:
                    assert sock.connect_ex(("127.0.0.1", port)) != 0, f"Owned port {port} leaked"
            print(
                f"Cleaned fixture PID {process.pid}; both ports closed; exit {process.returncode}"
            )


def test_browser_fault_ack_recovery_report_and_mobile(live_demo):
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(viewport={"width": 1360, "height": 1000})
            page = context.new_page()
            try:
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(live_demo)
                expect(page.locator("#condition")).to_have_text(
                    "Within configured limits", timeout=10000
                )
                page.wait_for_function(
                    "async () => (await (await fetch('/api/status')).json())"
                    ".latest.raw.cycle_count >= 2"
                )
                page.select_option("#scenario", "slow")
                page.get_by_role("button", name="Apply scenario").click()
                alert = page.locator("#alerts .alert").filter(has_text="Cycle time drifting")
                expect(alert).to_be_visible(timeout=12000)
                if path := os.environ.get("HEALTH_SCREENSHOT"):
                    page.screenshot(path=path, full_page=True)
                alert.get_by_role("button", name="Acknowledge").click()
                expect(alert).to_contain_text("acknowledged")
                page.get_by_role("button", name="Restore normal").click()
                expect(page.locator("#alerts")).to_contain_text("No open alerts", timeout=15000)
                page.select_option("#scenario", "missing")
                page.get_by_role("button", name="Apply scenario").click()
                expect(page.locator("#condition")).to_have_text("Condition unknown", timeout=8000)
                expect(page.locator("#readings")).to_contain_text(
                    "missing:cycle_time", timeout=8000
                )
                with page.expect_download() as download:
                    page.get_by_role("link", name="Download report").click()
                report = download.value.path().read_text()
                assert "Current machine condition cannot be confirmed" in report
                assert "missing:cycle_time" in report
                page.get_by_role("button", name="Restore normal").click()
                expect(page.locator("#condition")).to_have_text(
                    "Within configured limits", timeout=12000
                )
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                expect(page.get_by_role("button", name="Restore normal")).to_be_visible()
                page.route("**/api/status", lambda route: route.abort())
                expect(page.locator("#condition")).to_have_text("Condition unknown", timeout=5000)
                expect(page.locator("#availability")).to_have_text("Unknown")
                assert not errors
            finally:
                page.close()
                context.close()
        finally:
            browser.close()

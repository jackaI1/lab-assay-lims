"""Real browser workflow with scoped server/browser cleanup, also run in CI."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "playwright-artifacts"


def process_metadata():
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,lstart=,comm="], capture_output=True, text=True, check=True
    )
    records = {}
    for line in result.stdout.splitlines():
        values = line.split(None, 7)
        if len(values) == 8:
            records[int(values[0])] = dict(
                pid=int(values[0]), parent=int(values[1]), start=" ".join(values[2:7]), name=values[7]
            )
    return records


def descendants(records, parent):
    owned = set()
    while True:
        children = {pid for pid, r in records.items() if r["parent"] == parent or r["parent"] in owned}
        if children <= owned:
            return owned
        owned |= children


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    owned_browser = {}
    with tempfile.TemporaryDirectory(prefix="lab-assay-browser-") as temp:
        with socket.socket() as allocation:
            allocation.bind(("127.0.0.1", 0))
            port = allocation.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        env = {**os.environ, "LIMS_DB": str(Path(temp) / "browser.sqlite")}
        with (Path(temp) / "server.log").open("w+") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "lab_assay.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            print(
                json.dumps(
                    dict(
                        owner="scripts/browser_check.py",
                        pid=server.pid,
                        started=time.time(),
                        port=port,
                        cleanup=f"kill -TERM {server.pid}",
                    )
                )
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("Test server exited unexpectedly")
                    try:
                        with urlopen(url, timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Test server did not start")
                with sync_playwright() as runtime:
                    browser = runtime.chromium.launch(headless=True)
                    snapshot = process_metadata()
                    owned_browser = {
                        pid: meta
                        for pid, meta in snapshot.items()
                        if pid in descendants(snapshot, os.getpid())
                        and ("chrome" in meta["name"].lower() or "chromium" in meta["name"].lower())
                    }
                    print(
                        json.dumps(
                            dict(
                                owner="scripts/browser_check.py",
                                browser_processes=list(owned_browser.values()),
                                port="pipe",
                                cleanup="context.close(); browser.close() in finally",
                            )
                        )
                    )
                    try:
                        context = browser.new_context(
                            viewport={"width": 1440, "height": 1000}, accept_downloads=True
                        )
                        try:
                            page = context.new_page()
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            page.goto(url)
                            page.get_by_role("button", name="Open synthetic demo").click()
                            page.get_by_text("Quality checks passed", exact=True).wait_for()
                            rows = page.locator("#sample-results tr")
                            for name, truth in [("DEMO-S1", 7), ("DEMO-S2", 12)]:
                                row = rows.filter(has=page.get_by_role("cell", name=name, exact=True))
                                recovered = float(row.locator("td").nth(1).inner_text().split()[0])
                                assert abs(recovered - truth) / truth < 0.04
                            assert "S1" in page.locator("#sample-results").inner_text()
                            page.get_by_role("button", name="A1: standard", exact=True).click()
                            assert "Raw" in page.locator("#well-detail").inner_text()
                            with page.expect_download() as download:
                                page.get_by_role("link", name="Download results CSV").click()
                            assert Path(download.value.path()).read_text().startswith("well,role,sample_id")
                            page.get_by_role("button", name="Generate protocol", exact=True).click()
                            page.locator("#protocol-result").wait_for(state="visible")
                            assert "stock_ul" in page.locator("#robot-plan").inner_text()
                            with page.expect_download() as download:
                                page.get_by_role("link", name="Download Python protocol").click()
                            source = Path(download.value.path()).read_text()
                            assert "apiLevel" in source
                            page.locator("#protocol-kind").select_option("transfer")
                            page.get_by_role("button", name="Generate protocol", exact=True).click()
                            expect(page.locator("#robot-plan")).to_contain_text("source_remaining_ul")
                            # Failure case: impossible source depletion must give an actionable error.
                            page.locator("#stock").fill("A1,40")
                            page.get_by_role("button", name="Generate protocol", exact=True).click()
                            expect(page.locator("#status")).to_contain_text("20 uL left")
                            # Failure case: malformed import must not create a new saved import.
                            before = page.locator("#import-select option").count()
                            page.locator("#reader-file").set_input_files(
                                {
                                    "name": "bad.csv",
                                    "mimeType": "text/csv",
                                    "buffer": b"well,signal\nA1,OVRFLW",
                                }
                            )
                            page.get_by_role("button", name="Import reader file", exact=True).click()
                            expect(page.locator("#status")).to_have_class("error")
                            assert page.locator("#import-select option").count() == before
                            # Register records through visible forms.
                            page.locator("#sample-form input[name=id]").fill("BUFFER-UI")
                            page.locator("#sample-form input[name=description]").fill(
                                "Browser workflow buffer"
                            )
                            page.get_by_role("button", name="Register sample", exact=True).click()
                            expect(page.locator("#sample-list")).to_contain_text("BUFFER-UI")
                            page.locator("#lot-form input[name=id]").fill("LOT-UI")
                            page.locator("#lot-form input[name=reagent]").fill("Buffer reagent")
                            page.locator("#lot-form input[name=expires_on]").fill("2099-12-31")
                            page.get_by_role("button", name="Register lot", exact=True).click()
                            expect(page.locator("#lot-list")).to_contain_text("LOT-UI")
                            page.locator("#plate-name").fill("Browser plate")
                            page.locator("#lot-select").select_option("LOT-UI")
                            page.get_by_role("button", name="Use demo layout", exact=True).click()
                            expect(page.locator("#map-count")).to_contain_text("39")
                            page.get_by_role("button", name="Save plate map", exact=True).click()
                            expect(page.locator("#plate-detail")).to_contain_text("Browser plate")
                            expect(page.locator("#well-detail")).to_have_text(
                                "Select a well to inspect its contents."
                            )
                            from lab_assay.demo import synthetic_plate

                            page.locator("#reader-file").set_input_files(
                                {
                                    "name": "synthetic.csv",
                                    "mimeType": "text/csv",
                                    "buffer": synthetic_plate()[1],
                                }
                            )
                            page.get_by_role("button", name="Import reader file", exact=True).click()
                            expect(page.locator("#import-select option")).to_have_count(1)
                            page.get_by_role("button", name="Calculate and save analysis", exact=True).click()
                            page.get_by_text("Quality checks passed", exact=True).wait_for()
                            assert not errors, errors
                            page.get_by_role("button", name="Open synthetic demo").click()
                            expect(page.locator("#plate-detail")).to_contain_text("Synthetic demo")
                            page.evaluate("window.scrollTo(0,0)")
                            page.screenshot(path=str(ARTIFACTS / "desktop.png"), full_page=True)
                            page.locator("#review").screenshot(path=str(ARTIFACTS / "plate-review.png"))
                            page.set_viewport_size({"width": 390, "height": 844})
                            page.screenshot(path=str(ARTIFACTS / "mobile.png"), full_page=True)
                            metrics = page.evaluate(
                                "({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})"
                            )
                            assert metrics["scrollWidth"] <= metrics["width"], metrics
                            page.goto(url + "/docs")
                            expect(page.locator("#swagger-ui h2.title")).to_contain_text("Lab assay notebook")
                            expect(page.locator('[data-path="/api/samples"]').first).to_be_visible()
                            assert not errors, errors
                            print(
                                "Browser workflow passed: demo, well inspection, CSV and Python downloads, two protocol types, invalid import/stock, sample/lot/plate creation, import and analysis; desktop/mobile fit."
                            )
                        finally:
                            context.close()
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                with socket.socket() as probe:
                    assert probe.connect_ex(("127.0.0.1", port)) != 0, "Owned server port remains open"
                remaining = process_metadata()
                survivors = [
                    pid
                    for pid, meta in owned_browser.items()
                    if pid in remaining and remaining[pid]["start"] == meta["start"]
                ]
                assert not survivors, f"Owned browser processes remain: {survivors}"
                print(
                    json.dumps(
                        dict(
                            cleanup="verified",
                            server_returncode=server.returncode,
                            port_closed=port,
                            browser_processes_closed=len(owned_browser),
                        )
                    )
                )


if __name__ == "__main__":
    main()

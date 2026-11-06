import hashlib
import json
from io import BytesIO

import pytest

from fee_schedule_diff.cli import download, main
from fee_schedule_diff.extract import parse_page


def test_cached_download_and_checksum_mismatch_leave_original(tmp_path, monkeypatch):
    good = b"%PDF- pinned edition"
    source = dict(
        label="edition",
        url="https://www2.gov.bc.ca/source.pdf",
        sha256=hashlib.sha256(good).hexdigest(),
    )
    path = tmp_path / "edition.pdf"
    path.write_bytes(good)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: pytest.fail("network call"))
    assert download(source, tmp_path) == path
    path.write_bytes(b"original")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: BytesIO(b"%PDF- different"))
    with pytest.raises(ValueError, match="checksum"):
        download(source, tmp_path)
    assert path.read_bytes() == b"original"
    assert not list(tmp_path.glob("*.part"))


def test_html_response_and_non_government_host_rejected(tmp_path, monkeypatch):
    source = dict(label="edition", url="https://www2.gov.bc.ca/source.pdf", sha256="x")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: BytesIO(b"<html>error</html>"))
    with pytest.raises(ValueError, match="PDF"):
        download(source, tmp_path)
    source["url"] = "https://gov.bc.ca.example.test/source.pdf"
    with pytest.raises(ValueError, match="gov.bc.ca"):
        download(source, tmp_path)


def test_cli_compare_and_validation(tmp_path, sampled_editions):
    paths = []
    for i, edition in enumerate(sampled_editions):
        path = tmp_path / f"{i}.json"
        path.write_text(json.dumps(edition))
        paths.append(str(path))
    result, report, short = [tmp_path / name for name in ("diff.json", "diff.md", "short.md")]
    assert (
        main(
            [
                "compare",
                *paths,
                "--out",
                str(result),
                "--markdown",
                str(report),
                "--short",
                str(short),
            ]
        )
        == 0
    )
    assert "#page=" in report.read_text()
    assert result.exists() and short.exists()
    assert main(["validate", *paths, "--out", str(tmp_path / "accuracy.json")]) == 0
    assert (
        main(
            [
                "extract",
                "missing.pdf",
                "--url",
                "javascript:bad",
                "--label",
                "x",
                "--out",
                str(result),
            ]
        )
        == 2
    )


def test_empty_page_is_explicit_review():
    items, review = parse_page([], 1, "https://www2.gov.bc.ca/a.pdf")
    assert not items
    assert "no extractable" in review[0]["reason"]


def test_transient_disconnect_is_retried(tmp_path, monkeypatch):
    data = b"%PDF- pinned edition"
    source = dict(
        label="edition",
        url="https://www2.gov.bc.ca/source.pdf",
        sha256=hashlib.sha256(data).hexdigest(),
    )
    calls = []

    def response(request, **kwargs):
        calls.append(request)
        if len(calls) == 1:
            raise ConnectionResetError("temporary disconnect")
        return BytesIO(data)

    monkeypatch.setattr("urllib.request.urlopen", response)
    monkeypatch.setattr("time.sleep", lambda _: None)
    assert download(source, tmp_path).read_bytes() == data
    assert len(calls) == 2
    assert "fee-schedule-diff" in calls[0].get_header("User-agent")


def test_access_denied_is_not_retried(tmp_path, monkeypatch):
    from urllib.error import HTTPError

    calls = []

    def denied(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://www2.gov.bc.ca/source.pdf", 403, "Forbidden", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", denied)
    with pytest.raises(HTTPError):
        download(
            dict(label="edition", url="https://www2.gov.bc.ca/source.pdf", sha256="x"), tmp_path
        )
    assert len(calls) == 1

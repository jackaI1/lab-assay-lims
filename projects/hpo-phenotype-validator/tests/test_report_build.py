import hashlib
import json
from pathlib import Path
from scripts import build_reports


def test_regeneration_removes_packet_when_example_becomes_blocked(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    raw = Path("tests/fixtures/mini.obo").read_bytes()
    (data / "hp.obo").write_bytes(raw)
    (data / "manifest.json").write_text(json.dumps({"sha256": hashlib.sha256(raw).hexdigest()}))
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "report-config.json").write_text('{"created":"2026-11-05T00:00:00Z"}')
    (examples / "phrases.csv").write_text(
        "split,phrase,expected_id,rationale\neval,Seizure,HP:0001250,label\n"
    )
    good = {"subject_id": "fictional-test", "fictional": True, "features": [{"id": "HP:0001250"}]}
    for name in ["accepted.json", "needs-review.json"]:
        (examples / name).write_text(json.dumps(good))
    monkeypatch.setattr(build_reports, "ROOT", tmp_path)
    out = tmp_path / "reports"
    out.mkdir()
    build_reports.build(out)
    assert (out / "accepted/phenopacket.json").exists()
    good["features"] = [{"text": "seizurre"}]
    (examples / "accepted.json").write_text(json.dumps(good))
    build_reports.build(out)
    assert json.loads((out / "accepted/validation.json").read_text())["exportable"] is False
    assert not (out / "accepted/phenopacket.json").exists()

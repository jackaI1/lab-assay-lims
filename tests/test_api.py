import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from lab_assay.app import create_app
from lab_assay.demo import synthetic_plate


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite")) as client:
        yield client


def setup_plate(client, expired=False):
    assert (
        client.post("/api/samples", json={"id": "DEMO-S1", "description": "buffer test"}).status_code == 201
    )
    assert (
        client.post("/api/samples", json={"id": "DEMO-S2", "description": "buffer test"}).status_code == 201
    )
    expiry = date.today() + timedelta(days=-1 if expired else 90)
    assert (
        client.post(
            "/api/lots", json={"id": "LOT1", "reagent": "antibody", "expires_on": str(expiry)}
        ).status_code
        == 201
    )
    mapping, content, truth = synthetic_plate()
    response = client.post(
        "/api/plates", json={"name": "Plate 1", "lot_id": "LOT1", "unit": "ng/mL", "wells": mapping}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], content, truth


def test_end_to_end_import_analysis_audit_and_download(client):
    plate, content, truth = setup_plate(client)
    response = client.post(f"/api/plates/{plate}/imports", files={"file": ("plate.csv", content, "text/csv")})
    assert response.status_code == 201, response.text
    run = response.json()["id"]
    response = client.post(f"/api/imports/{run}/analyses", json={"model": "4pl"})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["result"]["passed"]
    groups = {g["key"]: g for g in result["result"]["groups"]}
    for name, value in truth.items():
        assert groups["sample:" + name]["concentration"] == pytest.approx(value, rel=0.04)
    assert client.get(f"/api/imports/{run}/file").content == content
    assert client.get(f"/api/analyses/{result['id']}/csv").status_code == 200
    events = client.get("/api/audit").json()
    assert [e["action"] for e in events][-2:] == ["reader.import", "assay.analyse"]
    assert all(e["actor"] == "local-user" for e in events)
    assert client.get(f"/api/plates/{plate}").json()["wells"]
    assert (
        client.post(f"/api/plates/{plate}/imports", files={"file": ("same.csv", content)}).status_code == 409
    )


def test_bad_import_is_atomic_and_invalid_links_rejected(client):
    plate, content, _ = setup_plate(client)
    count = len(client.get("/api/audit").json())
    bad = b"well,signal\nA1,nan"
    assert client.post(f"/api/plates/{plate}/imports", files={"file": ("bad.csv", bad)}).status_code == 422
    assert len(client.get("/api/audit").json()) == count
    assert client.get(f"/api/plates/{plate}").json()["imports"] == []
    mapping, _, _ = synthetic_plate()
    mapping[-1]["sample_id"] = "missing"
    assert (
        client.post("/api/plates", json={"name": "bad", "lot_id": "LOT1", "wells": mapping}).status_code
        == 422
    )
    assert (
        client.post("/api/plates", json={"name": "bad", "lot_id": "missing", "wells": mapping}).status_code
        == 422
    )
    assert client.get("/api/plates/999").status_code == 404
    assert client.post("/api/imports/999/analyses", json={"model": "4pl"}).status_code == 404


def test_expired_lot_flags_qc(client):
    plate, content, _ = setup_plate(client, expired=True)
    run = client.post(f"/api/plates/{plate}/imports", files={"file": ("p.csv", content)}).json()["id"]
    analysis = client.post(f"/api/imports/{run}/analyses", json={"model": "4pl"}).json()["result"]
    assert "EXPIRED_REAGENT_LOT" in analysis["flags"]
    assert not analysis["passed"]


def test_validation_and_duplicate_records(client):
    assert client.post("/api/samples", json={"id": "", "description": "x"}).status_code == 422
    assert client.post("/api/samples", json={"id": "s", "description": "x"}).status_code == 201
    assert client.post("/api/samples", json={"id": "s", "description": "x"}).status_code == 409
    assert client.post("/api/lots", json={"id": "l", "reagent": "a", "expires_on": "bad"}).status_code == 422
    assert client.post("/api/plates", json={"name": "x", "lot_id": "l", "wells": []}).status_code == 422


def test_audit_and_records_are_append_only(tmp_path):
    from lab_assay.store import Store

    store = Store(tmp_path / "a.sqlite")
    store.create_sample({"id": "s", "description": "sample"}, "tester")
    with sqlite3.connect(store.path) as db:
        for statement in [
            'UPDATE audit SET actor="fake"',
            "DELETE FROM audit",
            'UPDATE samples SET description="fake"',
            "DELETE FROM samples",
        ]:
            with pytest.raises(sqlite3.DatabaseError):
                db.execute(statement)
    assert store.list_records("samples")[0]["description"] == "sample"


def test_demo_is_repeatable_without_duplicate_records(client):
    a = client.post("/api/demo")
    b = client.post("/api/demo")
    assert a.status_code == 201 and b.status_code == 200
    assert a.json()["plate_id"] == b.json()["plate_id"]
    assert len(client.get("/api/plates").json()) == 1
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_local_origin_and_host_protection(client):
    assert client.post("/api/demo", headers={"origin": "https://elsewhere.example"}).status_code == 403
    assert client.get("/api/samples", headers={"host": "elsewhere.example"}).status_code == 400
    assert client.get("/api/audit").json() == []


def test_xlsx_import_and_protocol_audit(client):
    import io

    from openpyxl import Workbook

    from lab_assay.importers import parse_reader

    plate, content, _ = setup_plate(client)
    wb = Workbook()
    sheet = wb.active
    sheet.append(["well", "signal"])
    for well, value in parse_reader("p.csv", content).items():
        sheet.append([well, value])
    out = io.BytesIO()
    wb.save(out)
    result = client.post(f"/api/plates/{plate}/imports", files={"file": ("p.xlsx", out.getvalue())})
    assert result.status_code == 201
    assert client.get("/api/imports/" + str(result.json()["id"]) + "/file").content == out.getvalue()
    protocol = client.post(f"/api/plates/{plate}/protocols", json={"kind": "serial"})
    assert protocol.status_code == 201
    assert protocol.json()["plan"]["tips"] == 16
    assert (
        client.get("/api/protocols/" + str(protocol.json()["id"]) + "/file").text == protocol.json()["source"]
    )
    assert client.get("/api/audit").json()[-1]["action"] == "protocol.generate"


def test_replace_cannot_overwrite_records_or_audit_from_an_independent_connection(tmp_path):
    from lab_assay.store import Store

    store = Store(tmp_path / "replace.sqlite")
    store.create_sample({"id": "s", "description": "original"}, "tester")
    with sqlite3.connect(store.path) as db:
        for statement in [
            "INSERT OR REPLACE INTO samples VALUES('s','replacement')",
            "INSERT OR REPLACE INTO audit VALUES(1,'fake','fake','fake','fake','{}')",
            "INSERT INTO samples VALUES('s','replacement') ON CONFLICT(id) DO UPDATE SET description='replacement'",
        ]:
            with pytest.raises(sqlite3.DatabaseError):
                db.execute(statement)
    assert store.list_records("samples")[0]["description"] == "original"
    assert store.list_records("audit")[0]["actor"] == "tester"


def test_demo_does_not_reuse_unrelated_sample_ids_or_leave_partial_records(client):
    client.post("/api/samples", json={"id": "DEMO-S1", "description": "Unrelated existing research sample"})
    before = client.get("/api/audit").json()
    response = client.post("/api/demo")
    assert response.status_code == 422
    assert "reserved" in response.json()["detail"].lower()
    assert client.get("/api/audit").json() == before
    assert client.get("/api/lots").json() == []
    assert client.get("/api/plates").json() == []


def test_demo_seeding_rolls_back_on_failure(tmp_path, monkeypatch):
    from lab_assay.demo import seed_demo
    from lab_assay.store import Store

    store = Store(tmp_path / "rollback.sqlite")

    def fail(*args, **kwargs):
        raise ValueError("simulated calculation failure")

    monkeypatch.setattr(store, "save_analysis", fail)
    with pytest.raises(ValueError):
        seed_demo(store)
    assert store.list_records("samples") == []
    assert store.list_records("lots") == []
    assert store.list_records("plates") == []
    assert store.list_records("audit") == []

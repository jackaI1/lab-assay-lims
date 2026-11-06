import hashlib
import json

import pytest

from image_qc.data import download, load_manifest, source_record


def api_record():
    return {
        "public": True,
        "isic_id": "ISIC_0024306",
        "copyright_license": "CC-BY-NC",
        "attribution": "MILK study team",
        "files": {"full": {"url": "https://isic-archive.s3.amazonaws.com/images/x.jpg"}},
        "metadata": {"clinical": {"lesion_id": "IL_1", "diagnosis_3": "Nevus"}},
    }


def test_record_keeps_provenance_without_demographics():
    r = source_record(api_record())
    assert r["label"] == 0
    assert r["lesion_id"] == "IL_1"
    assert r["license"] == "CC-BY-NC-4.0"
    assert "metadata" not in r


@pytest.mark.parametrize("field,value", [("public", False), ("copyright_license", "unknown")])
def test_nonpublic_or_unknown_license_fails(field, value):
    a = api_record()
    a[field] = value
    with pytest.raises(ValueError):
        source_record(a)


def test_duplicate_lesions_rejected(tmp_path):
    r = source_record(api_record()) | {"sha256": "a" * 64}
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps([r, r | {"isic_id": "ISIC_0024307"}]))
    with pytest.raises(ValueError, match="duplicate"):
        load_manifest(p)


def test_cached_data_checksum_verified_without_network(tmp_path):
    blob = b"public fixture bytes"
    record = source_record(api_record()) | {"sha256": hashlib.sha256(blob).hexdigest()}
    p = tmp_path / (record["isic_id"] + ".jpg")
    p.write_bytes(blob)
    download([record], tmp_path)
    p.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        download([record], tmp_path)


@pytest.mark.parametrize("count", [0, -1, 4])
def test_invalid_refresh_preserves_existing_manifest(tmp_path, count):
    from image_qc.data import freeze_manifest

    path = tmp_path / "manifest.json"
    path.write_text("existing snapshot")
    with pytest.raises(ValueError, match="at least 5"):
        freeze_manifest(path, count)
    assert path.read_text() == "existing snapshot"


def test_failed_refresh_validation_preserves_existing_manifest(tmp_path, monkeypatch):
    from image_qc import data

    path = tmp_path / "manifest.json"
    path.write_text("existing snapshot")

    def response(url):
        if "search" not in url:
            return b"identical image bytes"
        melanoma = "Melanoma" in url
        page = []
        for i in range(5):
            r = api_record()
            n = i + (5 if melanoma else 0)
            r["isic_id"] = f"ISIC_{n:07}"
            r["metadata"]["clinical"] = {
                "lesion_id": f"fixture-{n}",
                "diagnosis_3": "Melanoma, NOS" if melanoma else "Nevus",
            }
            page.append(r)
        return json.dumps({"results": page, "next": None}).encode()

    monkeypatch.setattr(data, "read_url", response)
    with pytest.raises(ValueError, match="duplicate"):
        data.freeze_manifest(path, 5)
    assert path.read_text() == "existing snapshot"
    assert not list(tmp_path.glob(".manifest-*.json"))

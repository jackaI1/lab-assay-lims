import hashlib
import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from image_qc.experiment import run


@pytest.fixture
def fixture_dataset(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    records = []
    for i in range(20):
        pixels = np.random.default_rng(i).integers(60, 220, (128, 128, 3), dtype=np.uint8)
        pixels[30:90, 40:100] //= i % 2 + 1
        name = f"ISIC_{i:07}"
        p = image_dir / (name + ".jpg")
        Image.fromarray(pixels).save(p)
        records.append(
            {
                "isic_id": name,
                "lesion_id": f"fixture-{i}",
                "label": i % 2,
                "diagnosis": "Nevus" if i % 2 == 0 else "Melanoma, NOS",
                "url": f"https://isic-archive.s3.amazonaws.com/images/{name}.jpg",
                "license": "CC-BY-NC-4.0",
                "collection": 212,
                "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
                "attribution": "Synthetic test fixture; no clinical source",
                "source": "https://example.org/fixture",
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(records))
    return manifest, image_dir


def test_end_to_end_offline_report_and_abstaining_cli(tmp_path, fixture_dataset):
    manifest, image_dir = fixture_dataset
    out = tmp_path / "report"
    m = run(manifest, image_dir, out)
    assert m["dataset"]["split_counts"] == {"train": 12, "validation": 4, "test": 4}
    assert m["overall"]["n"] == 64
    assert sum(1 for _ in (out / "predictions.csv").open()) == 65
    assert (out / "REPORT.md").exists()
    html = (out / "index.html").read_text()
    assert "data:image/jpeg;base64," in html
    assert "Not a diagnostic tool" in html
    # Exercise the real installed CLI on an invalid/constant photo and a missing file.
    black = tmp_path / "black.png"
    Image.new("RGB", (128, 128), "black").save(black)
    command = ["image-qc", "check", str(black), "--model", str(out / "models.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "abstain"
    result = subprocess.run(
        command[:2] + [str(tmp_path / "missing.jpg")] + command[3:], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "error" in result.stderr.lower()


def test_held_out_pixels_cannot_change_fitted_gate(tmp_path, fixture_dataset):
    from image_qc.experiment import split_sources

    manifest, image_dir = fixture_dataset
    records = json.loads(manifest.read_text())
    split = split_sources(records)
    first, second = tmp_path / "first", tmp_path / "second"
    run(manifest, image_dir, first)
    for i, r in enumerate(records):
        if split[r["isic_id"]] == "test":
            path = image_dir / (r["isic_id"] + ".jpg")
            pixels = np.random.default_rng(100 + i).integers(0, 255, (128, 128, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(path)
            r["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(records))
    run(manifest, image_dir, second)
    a = json.loads((first / "models.json").read_text())
    b = json.loads((second / "models.json").read_text())
    for field in ("quality", "lesion", "threshold", "rules"):
        assert a[field] == b[field]

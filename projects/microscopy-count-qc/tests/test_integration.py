import json
import subprocess
import sys
import numpy as np
import tifffile
from PIL import Image


def test_classical_cli_runs_from_images_to_offline_report(tmp_path):
    for name in ("images", "masks", "metadata"):
        (tmp_path / name).mkdir()
    for i, split in enumerate(("training", "validation", "test")):
        stem = f"field{i}"
        image = np.zeros((64, 64), dtype=np.uint16)
        yy, xx = np.ogrid[:64, :64]
        image[(yy - 32) ** 2 + (xx - 32) ** 2 < 100] = 3000
        mask = np.zeros((64, 64, 3), dtype=np.uint8)
        mask[image > 0, 0] = 255
        tifffile.imwrite(tmp_path / "images" / f"{stem}.tif", image)
        Image.fromarray(mask).save(tmp_path / "masks" / f"{stem}.png")
        (tmp_path / "metadata" / f"{split}.txt").write_text(f"{stem}.png\n")
    out = tmp_path / "report"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "microscopy_qc",
            "run",
            "--data",
            str(tmp_path),
            "--output",
            str(out),
            "--methods",
            "watershed",
        ],
        check=True,
    )
    run = json.loads((out / "results.json").read_text())
    assert run["rows"][0]["true_count"] == 1
    assert run["rows"][0]["pred_count"] == 1
    assert run["rows"][0]["metrics"]["0.5"]["f1"] == 1
    assert run["provenance"]["splits"]["test"] == ["field2"]
    assert (out / "index.html").stat().st_size > 1000


def test_render_command_is_available():
    result = subprocess.run(
        [sys.executable, "-m", "microscopy_qc", "render", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--output" in result.stdout


def test_duplicate_methods_are_rejected_before_double_counting(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "microscopy_qc",
            "run",
            "--data",
            str(tmp_path),
            "--methods",
            "watershed",
            "watershed",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Duplicate methods" in result.stderr

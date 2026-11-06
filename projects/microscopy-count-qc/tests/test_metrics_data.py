import numpy as np
import pytest
from microscopy_qc.data import decode_mask, validate_splits, safe_extract, sha256
from microscopy_qc.metrics import evaluate, match_instances


def test_touching_distinct_values_are_not_joined():
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    rgb[1:3, 1:3, 0] = 100
    rgb[1:3, 3:5, 0] = 200
    assert decode_mask(rgb).max() == 2


def test_mask_uses_first_channel_not_boundary_channel():
    rgb = np.zeros((5, 5, 3), dtype=np.uint8)
    rgb[1:4, 1:4, 1] = 255
    assert decode_mask(rgb).max() == 0


def test_split_overlap_and_missing_data_rejected():
    with pytest.raises(ValueError):
        validate_splits(
            {"training": ["a"], "validation": ["b"], "test": ["a"]}, {"a", "b"}
        )
    with pytest.raises(ValueError):
        validate_splits(
            {"training": ["a"], "validation": ["b"], "test": ["c"]}, {"a", "b"}
        )


def test_matching_noncontiguous_ids_counts_merge_and_false_positive():
    truth = np.array([[1, 1, 0, 9, 9, 0, 0]])
    pred = np.array([[5, 5, 5, 5, 5, 0, 42]])
    result = evaluate(truth, pred, 0.4)
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 1)
    assert result["f1"] == 0.5
    assert result["count_error"] == 0
    assert evaluate(truth, pred, 0.5)["tp"] == 0


def test_matching_maximizes_cardinality_before_iou():
    # Choosing .9 greedily loses a match; both .51 edges must win.
    from microscopy_qc.metrics import assign_iou

    assert len(assign_iou(np.array([[0.9, 0.51], [0.51, 0.49]]), 0.5)) == 2


@pytest.mark.parametrize(
    "truth,pred,want",
    [
        ([0, 0], [0, 0], (0, 0, 0, 1.0)),
        ([1, 1], [0, 0], (0, 0, 1, 0.0)),
        ([0, 0], [2, 2], (0, 1, 0, 0.0)),
    ],
)
def test_empty_images(truth, pred, want):
    r = evaluate(np.array([truth]), np.array([pred]), 0.5)
    assert (r["tp"], r["fp"], r["fn"], r["f1"]) == want


def test_shape_mismatch_rejected():
    with pytest.raises(ValueError):
        match_instances(np.zeros((2, 2)), np.zeros((3, 2)), 0.5)


def test_zip_traversal_rejected(tmp_path):
    import zipfile

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escape", "bad")
    with pytest.raises(ValueError):
        safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "escape").exists()


def test_hash_computed_from_bytes(tmp_path):
    p = tmp_path / "data"
    p.write_bytes(b"abc")
    assert (
        sha256(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_download_rejects_modified_archive(tmp_path):
    from microscopy_qc.data import download_dataset

    (tmp_path / "archives").mkdir()
    (tmp_path / "archives" / "images.zip").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA256"):
        download_dataset(tmp_path, "sources.json")


def test_extracted_data_change_is_rejected_before_official_claim(tmp_path):
    import json
    import zipfile
    from microscopy_qc.data import verify_download

    archives = tmp_path / "archives"
    archives.mkdir()
    path = archives / "metadata.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("metadata/test.txt", "official.png\n")
    safe_extract(path, tmp_path)
    manifest = {
        "dataset": "BBBC039v1",
        "archives": {"metadata": {"sha256": sha256(path)}},
    }
    (tmp_path / "download_provenance.json").write_text(json.dumps(manifest))
    assert verify_download(tmp_path)["dataset"] == "BBBC039v1"
    (tmp_path / "metadata" / "test.txt").write_text("changed.png\n")
    with pytest.raises(ValueError, match="Extracted data changed"):
        verify_download(tmp_path)

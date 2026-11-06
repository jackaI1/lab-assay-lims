import numpy as np
import pytest
from PIL import Image

from image_qc.images import VARIANTS, degrade, features, load_image


@pytest.fixture
def photo():
    rng = np.random.default_rng(7)
    a = rng.integers(100, 220, (128, 128, 3), dtype=np.uint8)
    a[35:95, 40:90] //= 2
    return Image.fromarray(a)


def test_blur_reduces_focus(photo):
    assert features(degrade(photo, "blur", 3))["focus"] < features(photo)["focus"] / 10


def test_exposure_changes_measured_brightness(photo):
    clean = features(photo)["brightness"]
    assert features(degrade(photo, "dark", 3))["brightness"] < clean / 3
    assert features(degrade(photo, "bright", 3))["high_clip"] > 0.5


def test_framing_has_known_visible_fraction(photo):
    f = features(degrade(photo, "framing", 3))
    assert f["coverage"] == pytest.approx(0.45, abs=0.02)


def test_hair_adds_dark_lines_reproducibly(photo):
    a = degrade(photo, "hair", 3, seed=9)
    assert np.array_equal(a, degrade(photo, "hair", 3, seed=9))
    assert not np.array_equal(a, degrade(photo, "hair", 3, seed=10))
    assert features(a)["hair_response"] > features(photo)["hair_response"]


def test_variants_are_explicit_and_input_is_unchanged(photo):
    before = np.array(photo).copy()
    assert len(VARIANTS) == 16
    for kind, strength in VARIANTS:
        assert degrade(photo, kind, strength).size == photo.size
    assert np.array_equal(before, photo)


@pytest.mark.parametrize("kind,strength", [("blur", 0), ("clean", 2), ("unknown", 1)])
def test_invalid_degradation_rejected(photo, kind, strength):
    with pytest.raises(ValueError):
        degrade(photo, kind, strength)


def test_load_normalizes_exif_and_size(tmp_path, photo):
    path = tmp_path / "photo.jpg"
    photo.save(path)
    assert load_image(path).size == (128, 128)
    with pytest.raises(ValueError, match="small"):
        tiny = tmp_path / "tiny.png"
        Image.new("RGB", (8, 8)).save(tiny)
        load_image(tiny)


def test_features_finite_for_flat_image():
    f = features(Image.new("RGB", (128, 128), "black"))
    assert np.isfinite(list(f.values())).all()
    assert f["focus"] == 0
    assert f["coverage"] == 0

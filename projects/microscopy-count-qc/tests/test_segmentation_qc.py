import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.draw import disk
from microscopy_qc.segment import watershed_segment
from microscopy_qc.qc import focus_score, inspect_image, calibrate


def nuclei():
    image = np.zeros((96, 96), dtype=float)
    for center in [(48, 35), (48, 59)]:
        image[disk(center, 15, shape=image.shape)] = 1
    return image


def test_watershed_separates_touching_nuclei():
    labels = watershed_segment(nuclei(), diameter=30, min_area=40)
    assert labels.max() == 2
    assert labels[48, 35] != labels[48, 59]


def test_blank_image_has_no_cells_and_focus_warning():
    image = np.zeros((40, 40))
    labels = watershed_segment(image, diameter=20, min_area=10)
    assert labels.max() == 0
    qc = inspect_image(
        image, labels, {"focus_cutoff": 0.01, "area_cutoff": 800, "diameter": 30}
    )
    assert qc["focus_flag"] is True
    assert qc["merge_ids"] == []


def test_blur_reduces_focus_and_triggers_flag():
    sharp = nuclei()
    blurry = gaussian_filter(sharp, 4)
    cutoff = (focus_score(sharp) + focus_score(blurry)) / 2
    config = {"focus_cutoff": cutoff, "area_cutoff": 10000, "diameter": 30}
    assert not inspect_image(sharp, sharp.astype(int), config)["focus_flag"]
    assert inspect_image(blurry, sharp.astype(int), config)["focus_flag"]


def test_merge_flag_uses_prediction_shape_without_ground_truth():
    image = nuclei()
    qc = inspect_image(
        image,
        image.astype(int),
        {"focus_cutoff": 0, "area_cutoff": 5000, "diameter": 30},
    )
    assert qc["merge_ids"] == [1]  # separated peaks in one prediction


def test_calibration_uses_supplied_training_examples():
    image = nuclei()
    labels = watershed_segment(image, 30, 40)
    config = calibrate([(image, labels)])
    assert 20 < config["diameter"] < 40
    assert config["area_cutoff"] > 600
    assert config["focus_cutoff"] > 0

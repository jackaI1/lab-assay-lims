"""Classical watershed and frozen Cellpose nuclei inference."""

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.filters import threshold_otsu, gaussian
from skimage.morphology import remove_small_objects, remove_small_holes
from skimage.segmentation import watershed


def normalize(image):
    image = np.asarray(image, dtype=np.float32)
    if image.ndim != 2 or not np.all(np.isfinite(image)):
        raise ValueError("Expected a finite 2D image")
    low, high = np.percentile(image, [1, 99.8])
    return (
        np.clip((image - low) / (high - low), 0, 1)
        if high > low
        else np.zeros_like(image)
    )


def watershed_segment(image, diameter, min_area):
    smooth = gaussian(normalize(image), sigma=1)
    if not np.any(smooth):
        return np.zeros(smooth.shape, dtype=np.int32)
    foreground = remove_small_objects(
        smooth > threshold_otsu(smooth), min_size=int(min_area)
    )
    foreground = remove_small_holes(foreground, area_threshold=int(min_area))
    distance = ndi.distance_transform_edt(foreground)
    coords = peak_local_max(
        distance,
        min_distance=max(1, int(diameter * 0.35)),
        labels=foreground,
        exclude_border=False,
    )
    markers = np.zeros(image.shape, dtype=np.int32)
    for index, (y, x) in enumerate(coords, 1):
        markers[y, x] = index
    labels = watershed(-distance, markers, mask=foreground)
    # Drop tiny watershed fragments without renumbering assumptions.
    areas = np.bincount(labels.ravel())
    labels[np.isin(labels, np.flatnonzero(areas < min_area))] = 0
    return labels.astype(np.int32)


def load_cellpose(threads=2):
    import torch
    from cellpose import models

    torch.set_num_threads(threads)
    torch.manual_seed(0)
    return models.CellposeModel(gpu=False, model_type="nuclei")


def cellpose_segment(model, image, diameter, min_area):
    masks, _, _ = model.eval(
        image,
        channels=[0, 0],
        diameter=diameter,
        flow_threshold=0.4,
        cellprob_threshold=0.0,
        min_size=int(min_area),
        augment=False,
    )
    return np.asarray(masks, dtype=np.int32)

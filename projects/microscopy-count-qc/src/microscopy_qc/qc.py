"""Train-calibrated review heuristics, independent of test annotations."""

import numpy as np
from scipy.ndimage import laplace, distance_transform_edt
from skimage.feature import peak_local_max
from skimage.measure import regionprops
from .segment import normalize


def focus_score(image):
    return float(np.var(laplace(normalize(image))))


def calibrate(pairs):
    areas, focus = [], []
    for image, labels in pairs:
        areas.extend(r.area for r in regionprops(labels))
        focus.append(focus_score(image))
    if not areas:
        raise ValueError("Training annotations contain no nuclei")
    return {
        "diameter": float(2 * np.sqrt(np.median(areas) / np.pi)),
        "min_area": max(5, int(np.percentile(areas, 5) * 0.25)),
        "focus_cutoff": float(np.percentile(focus, 5)),
        "area_cutoff": float(np.percentile(areas, 95) * 1.5),
    }


def inspect_image(image, labels, config):
    score = focus_score(image)
    merges, details = [], []
    for region in regionprops(labels):
        padded = np.pad(region.image, 1)
        distance = distance_transform_edt(padded)
        peaks = peak_local_max(
            distance,
            min_distance=max(1, int(config["diameter"] * 0.5)),
            threshold_abs=config["diameter"] * 0.2,
            exclude_border=False,
        )
        reasons = []
        if region.area > config["area_cutoff"]:
            reasons.append("large area")
        if len(peaks) >= 2:
            reasons.append("separated interior peaks")
        if reasons:
            merges.append(int(region.label))
            details.append(
                {
                    "label": int(region.label),
                    "area": int(region.area),
                    "reasons": reasons,
                }
            )
    return {
        "focus_score": score,
        "focus_flag": bool(score < config["focus_cutoff"]),
        "merge_ids": merges,
        "merge_details": details,
    }

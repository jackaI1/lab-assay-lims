"""Object metrics: cardinality-first one-to-one matching at each IoU."""

import numpy as np
from scipy.optimize import linear_sum_assignment


def assign_iou(iou, threshold):
    if not 0 < threshold <= 1:
        raise ValueError("IoU threshold must be in (0, 1]")
    if not iou.size:
        return []
    eligible = iou >= threshold
    # A whole extra match outweighs every possible change in total IoU.
    reward = eligible * (min(iou.shape) + 1 + iou)
    rows, cols = linear_sum_assignment(reward, maximize=True)
    return [(int(r), int(c)) for r, c in zip(rows, cols) if eligible[r, c]]


def match_instances(truth, pred, threshold):
    truth, pred = np.asarray(truth), np.asarray(pred)
    if truth.shape != pred.shape or truth.ndim != 2:
        raise ValueError("Label images must be matching 2D arrays")
    for array in (truth, pred):
        if not np.issubdtype(array.dtype, np.integer) or np.any(array < 0):
            raise ValueError("Labels must be nonnegative integers")
    t_ids, t_inv = np.unique(truth, return_inverse=True)
    p_ids, p_inv = np.unique(pred, return_inverse=True)
    intersections = np.bincount(
        t_inv * len(p_ids) + p_inv, minlength=len(t_ids) * len(p_ids)
    ).reshape(len(t_ids), len(p_ids))
    unions = (
        intersections.sum(1)[:, None] + intersections.sum(0)[None, :] - intersections
    )
    iou = np.divide(
        intersections, unions, out=np.zeros_like(unions, dtype=float), where=unions > 0
    )
    ti, pi = np.flatnonzero(t_ids > 0), np.flatnonzero(p_ids > 0)
    pairs = assign_iou(iou[np.ix_(ti, pi)], threshold)
    matches = [(int(t_ids[ti[t]]), int(p_ids[pi[p]])) for t, p in pairs]
    return matches, [int(x) for x in t_ids if x > 0], [int(x) for x in p_ids if x > 0]


def evaluate(truth, pred, threshold):
    pairs, t_ids, p_ids = match_instances(truth, pred, threshold)
    tp = len(pairs)
    fp, fn = len(p_ids) - tp, len(t_ids) - tp
    error = len(p_ids) - len(t_ids)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0,
        "true_count": len(t_ids),
        "pred_count": len(p_ids),
        "count_error": error,
        "absolute_count_error": abs(error),
        "relative_count_error": abs(error) / len(t_ids) if t_ids else None,
    }


def summarize(rows, thresholds):
    summary = {}
    for method in sorted({r["method"] for r in rows}):
        group = [r for r in rows if r["method"] == method]
        scores = {}
        for threshold in thresholds:
            metrics = [r["metrics"][str(threshold)] for r in group]
            tp, fp, fn = (sum(m[key] for m in metrics) for key in ("tp", "fp", "fn"))
            scores[str(threshold)] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "micro_f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0,
                "macro_f1": float(np.mean([m["f1"] for m in metrics])),
            }
        summary[method] = {
            "images": len(group),
            "metrics": scores,
            "count_mae": float(np.mean([r["absolute_count_error"] for r in group])),
            "count_bias": float(np.mean([r["count_error"] for r in group])),
            "true_count": sum(r["true_count"] for r in group),
            "pred_count": sum(r["pred_count"] for r in group),
            "focus_flags": sum(r["qc"]["focus_flag"] for r in group),
            "images_with_merge_flags": sum(bool(r["qc"]["merge_ids"]) for r in group),
        }
    return summary

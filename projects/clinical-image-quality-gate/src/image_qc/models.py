"""Small logistic models exported as non-executable JSON numeric parameters."""

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .images import features, lesion_vector, quality_vector


def fit_logistic(x: np.ndarray, y: np.ndarray) -> dict:
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0, solver="liblinear", class_weight="balanced", max_iter=2000, random_state=42
        ),
    )
    model.fit(x, y)
    scaler, logistic = model.steps[0][1], model.steps[1][1]
    return {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": logistic.coef_[0].tolist(),
        "intercept": float(logistic.intercept_[0]),
    }


def probability(model: dict, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x)
    z = ((x - np.array(model["mean"])) / np.array(model["scale"])) @ np.array(model["coef"])
    return expit(z + model["intercept"])


def calibrate_rules(validation_features: list[dict]) -> dict:
    # Each tail permits about 2% of validation acceptable images to fail one check.
    return {
        name: float(np.quantile([r[name] for r in validation_features], q))
        for name, q in (
            ("focus", 0.02),
            ("low_clip", 0.98),
            ("high_clip", 0.98),
            ("coverage", 0.02),
            ("hair_response", 0.98),
        )
    }


def rule_reasons(f: dict, thresholds: dict) -> list[str]:
    reasons = []
    for name in ("focus", "coverage"):
        if f[name] < thresholds[name]:
            reasons.append(f"low {name}")
    for name in ("low_clip", "high_clip", "hair_response"):
        if f[name] > thresholds[name]:
            reasons.append(f"high {name}")
    return reasons


def quality_decision(image, bundle: dict, method: str = "learned") -> dict:
    f = features(image)
    if f["contrast"] < 0.005:
        return {
            "decision": "abstain",
            "reject_probability": None,
            "reasons": ["near-constant image"],
            "measurements": f,
        }
    if method == "rules":
        reasons = rule_reasons(f, bundle["rules"])
        p = None
    elif method == "learned":
        p = float(probability(bundle["quality"], quality_vector(image)))
        reasons = (
            ["learned damage score exceeds validation threshold"] if p > bundle["threshold"] else []
        )
    else:
        raise ValueError("method must be learned or rules")
    return {
        "decision": "abstain" if reasons else "accept",
        "reject_probability": p,
        "reasons": reasons,
        "measurements": f,
    }


def selective_predict(image, bundle: dict, method: str = "learned") -> dict:
    result = quality_decision(image, bundle, method)
    result["lesion_prediction"] = None
    result["notice"] = "Research demonstration only. Not a diagnostic tool."
    if result["decision"] == "accept":
        p = float(probability(bundle["lesion"], lesion_vector(image)))
        result["lesion_prediction"] = "melanoma" if p >= 0.5 else "nevus"
    return result

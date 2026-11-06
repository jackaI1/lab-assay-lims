import json

import numpy as np
import pytest
from PIL import Image

from image_qc.experiment import split_sources, summarize
from image_qc.models import fit_logistic, probability, selective_predict


def test_split_is_balanced_disjoint_and_order_independent():
    records = [{"isic_id": f"i{i}", "lesion_id": f"l{i}", "label": i % 2} for i in range(40)]
    a = split_sources(records)
    assert a == split_sources(list(reversed(records)))
    assert sorted(a.values()).count("train") == 24
    for split in ("train", "validation", "test"):
        labels = [r["label"] for r in records if a[r["isic_id"]] == split]
        assert sum(labels) == len(labels) / 2


def test_split_refuses_shared_lesions():
    records = [{"isic_id": f"i{i}", "lesion_id": "same", "label": i % 2} for i in range(40)]
    with pytest.raises(ValueError, match="lesion"):
        split_sources(records)


def test_json_model_learns_separation_and_roundtrips():
    x = np.array([[-3, 1], [-2, 1], [-1, 1], [1, 1], [2, 1], [3, 1]])
    model = json.loads(json.dumps(fit_logistic(x, np.array([0, 0, 0, 1, 1, 1]))))
    p = probability(model, x)
    assert p[0] < 0.2
    assert p[-1] > 0.8
    assert np.isfinite(p).all()


def test_rejected_image_never_reaches_lesion_classifier():
    image = Image.new("RGB", (128, 128), "black")
    # Intentionally invalid lesion model: an attempted inference would fail.
    bundle = {
        "quality": {"mean": [0] * 8, "scale": [1] * 8, "coef": [0] * 8, "intercept": 10},
        "threshold": 0.5,
        "lesion": {},
    }
    result = selective_predict(image, bundle)
    assert result["decision"] == "abstain"
    assert result["lesion_prediction"] is None
    assert result["reasons"]


def test_accepted_image_gets_downstream_prediction():
    bundle = {
        "quality": {"mean": [0] * 8, "scale": [1] * 8, "coef": [0] * 8, "intercept": -10},
        "threshold": 0.5,
        "lesion": {"mean": [0] * 96, "scale": [1] * 96, "coef": [0] * 96, "intercept": -1},
    }
    result = selective_predict(
        Image.fromarray(np.random.default_rng(1).integers(80, 220, (128, 128, 3), dtype=np.uint8)),
        bundle,
    )
    assert result["decision"] == "accept"
    assert result["lesion_prediction"] == "nevus"


def test_accuracy_denominators_and_empty_groups():
    rows = [
        {
            "isic_id": "a",
            "kind": "clean",
            "strength": 0,
            "bad": 0,
            "label": 0,
            "lesion_pred": 0,
            "rules_accept": True,
            "learned_accept": True,
        },
        {
            "isic_id": "b",
            "kind": "blur",
            "strength": 2,
            "bad": 1,
            "label": 1,
            "lesion_pred": 0,
            "rules_accept": False,
            "learned_accept": True,
        },
    ]
    s = summarize(rows, bootstrap=20)
    assert s["overall"]["accuracy"] == 0.5
    assert s["rules"]["accepted"]["accuracy"] == 1.0
    assert s["rules"]["rejected"]["accuracy"] == 0.0
    assert s["learned"]["rejected"]["accuracy"] is None
    assert s["rules"]["bad_rejected"] == {"n": 1, "total": 1, "rate": 1.0}


@pytest.mark.parametrize("color", ["black", "white", "gray"])
def test_flat_image_abstains_even_if_model_would_accept(color):
    bundle = {
        "quality": {"mean": [0] * 8, "scale": [1] * 8, "coef": [0] * 8, "intercept": -10},
        "threshold": 0.5,
        "lesion": {},
    }
    assert selective_predict(Image.new("RGB", (128, 128), color), bundle)["decision"] == "abstain"


def test_threshold_curve_never_accepts_hard_abstentions():
    rows = [
        {
            "isic_id": "a",
            "kind": "dark",
            "strength": 3,
            "bad": 1,
            "label": 1,
            "lesion_pred": 0,
            "rules_accept": False,
            "learned_accept": False,
            "reject_probability": None,
        },
        {
            "isic_id": "b",
            "kind": "clean",
            "strength": 0,
            "bad": 0,
            "label": 0,
            "lesion_pred": 0,
            "rules_accept": True,
            "learned_accept": True,
            "reject_probability": 0.3,
        },
    ]
    m = summarize(rows, bootstrap=20)
    assert m["threshold_curve"][0]["n"] == 0
    assert m["threshold_curve"][-1]["n"] == 1


def test_empty_evaluation_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        summarize([])

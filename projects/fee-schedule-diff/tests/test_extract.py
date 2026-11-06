import json

import pytest

from fee_schedule_diff.extract import assemble, parse_page
from fee_schedule_diff.validate import validate

from conftest import FIXTURES

URL = "https://www2.gov.bc.ca/example.pdf"


def words(lines):
    result = []
    for i, parts in enumerate(lines):
        for x, text in parts:
            result.append(
                {"text": text, "x0": x, "x1": x + 20, "top": 100 + i * 12, "bottom": 110 + i * 12}
            )
    return result


def test_hand_checked_complete_pages(sampled_editions):
    score = validate(sampled_editions, json.loads((FIXTURES / "gold.json").read_text()))
    assert score["errors"] == []
    assert score["metrics"]["exact_precision"] == 1
    assert score["metrics"]["exact_recall"] == 1


@pytest.mark.parametrize(
    "code,price,reason",
    [
        ("P01210", "66.32", "percentage or conditional fee"),
        ("12345*", "66.32", "asterisk-qualified code requires review"),
        ("12345", "TBD", "no single fixed monetary fee"),
    ],
)
def test_uncertain_rows_are_flagged(code, price, reason):
    body = words([[(72, code), (126, "44% of surgical fee"), (400, "....."), (500, price)]])
    items, review = parse_page(body, 2, URL)
    assert not items
    assert review[0]["reason"] == reason
    assert review[0]["url"] == URL + "#page=2"


def test_multiple_prices_never_pick_one():
    body = words(
        [
            [(72, "12345"), (126, "Procedure")],
            [(126, "minimum ....."), (500, "10.00")],
            [(126, "maximum ....."), (500, "20.00")],
        ]
    )
    items, review = parse_page(body, 4, URL)
    assert not items
    assert review[0]["reason"] == "multiple monetary fees"


def test_missing_leader_is_not_a_fee():
    items, review = parse_page(words([[(72, "12345"), (126, "Unclear"), (500, "10.00")]]), 1, URL)
    assert not items
    assert review[0]["reason"] == "fee without table leader dots"


def test_duplicates_quarantine_conflicts_and_consolidate_identical():
    a = words([[(72, "12345"), (126, "Procedure ....."), (500, "10.00")]])
    b = words([[(72, "12345"), (126, "Procedure ....."), (500, "20.00")]])
    source = {"url": URL, "label": "demo"}
    assert assemble([(1, a), (2, b)], source)["blocked_codes"] == ["12345"]
    assert not assemble([(1, a), (2, b)], source)["items"]
    assert assemble([(1, a), (2, a)], source)["items"][0]["occurrences"] == [1, 2]


def test_sample_evaluator_detects_omissions_and_extra_rows(sampled_editions):
    gold = json.loads((FIXTURES / "gold.json").read_text())
    sampled_editions[0]["rows"] = []
    assert validate(sampled_editions, gold)["metrics"]["exact_recall"] < 1
    sampled_editions[1]["rows"][0]["fee"] = "0.00"
    assert validate(sampled_editions, gold)["errors"]

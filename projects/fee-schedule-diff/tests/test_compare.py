from copy import deepcopy

from fee_schedule_diff.compare import compare, markdown


def row(code, fee="10.00", description="Procedure", prefix="", page=1):
    return dict(
        code=code,
        fee=fee,
        description=description,
        prefix=prefix,
        page=page,
        url=f"https://www2.gov.bc.ca/source.pdf#page={page}",
    )


def edition(items, blocked=()):
    return dict(
        items=items,
        blocked_codes=list(blocked),
        review=[],
        source=dict(label="edition", url="https://www2.gov.bc.ca/source.pdf"),
    )


def test_all_changes_and_page_links():
    old = edition([row("00001"), row("00002"), row("00003"), row("00005")])
    new = edition(
        [
            row("00002", "11.00"),
            row("00003", description="Reworded | row", page=4),
            row("00004"),
            row("00005", prefix="P"),
        ]
    )
    result = compare(old, new)
    assert result["counts"] == dict(added=1, removed=1, fee=1, description=1, prefix=1)
    report = markdown(result)
    assert "#page=4" in report
    assert r"Reworded \| row" in report
    assert result["changes"][0]["before"]["code"] == "00001"


def test_uncertainty_either_side_suppresses_false_add_remove():
    a = edition([row("00001")])
    b = edition([], blocked=["00001"])
    assert compare(a, b)["changes"] == []
    assert compare(b, a)["changes"] == []


def test_decimal_equality_and_deterministic_no_mutation():
    a, b = edition([row("00001", "10.0")]), edition([row("00001", "10.00")])
    original = deepcopy(a)
    assert not compare(a, b)["changes"]
    assert a == original
    assert compare(a, b) == compare(a, b)

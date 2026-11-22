"""Unit tests for validate_sighting in species.py (E03).

Covers the validation logic so coverage holds even when judge tests are skipped.
"""

from datetime import date

from app.species import validate_sighting

GOOD = {
    "seen_on": "2026-06-05",
    "count": "4",
    "notes": "under the board",
    "removed": "1",
    "object_id": "7",
}


def test_validate_sighting_good():
    values, errors = validate_sighting(GOOD, {7})
    assert errors == {}
    assert values == {
        "seen_on": date(2026, 6, 5),
        "count": 4,
        "notes": "under the board",
        "removed": True,
        "object_id": 7,
    }


def test_validate_sighting_minimal():
    values, errors = validate_sighting({"seen_on": "2026-06-05"}, set())
    assert errors == {}
    assert values == {
        "seen_on": date(2026, 6, 5),
        "count": None,
        "notes": "",
        "removed": False,
        "object_id": None,
    }


def test_validate_sighting_seen_on_empty():
    form = {"seen_on": "", "count": "1", "object_id": ""}
    values, errors = validate_sighting(form, {1})
    assert errors == {"seen_on": "Pick the date you saw it"}
    assert values["seen_on"] == ""


def test_validate_sighting_seen_on_invalid():
    form = {"seen_on": "June", "count": "1", "object_id": ""}
    values, errors = validate_sighting(form, {1})
    assert errors == {"seen_on": "Pick the date you saw it"}
    assert values["seen_on"] == "June"


def test_validate_sighting_count_zero():
    form = {"seen_on": "2026-06-05", "count": "0", "object_id": ""}
    values, errors = validate_sighting(form, {1})
    assert errors == {"count": "A whole number, 1 or more"}
    assert values["count"] is None


def test_validate_sighting_count_nonnumeric():
    form = {"seen_on": "2026-06-05", "count": "lots", "object_id": ""}
    values, errors = validate_sighting(form, {1})
    assert errors == {"count": "A whole number, 1 or more"}
    assert values["count"] is None


def test_validate_sighting_notes_over_limit():
    form = {"seen_on": "2026-06-05", "notes": "n" * 2001, "object_id": ""}
    values, errors = validate_sighting(form, {1})
    assert errors == {"notes": "At most 2000 characters"}


def test_validate_sighting_object_id_not_in_list():
    values, errors = validate_sighting(
        {"seen_on": "2026-06-05", "object_id": "999"}, {7}
    )
    assert errors == {"object_id": "Pick an object from the list"}
    assert values["object_id"] is None


def test_validate_sighting_removed_unset():
    values, errors = validate_sighting({"seen_on": "2026-06-05", "removed": ""}, {1})
    assert errors == {}
    assert values["removed"] is False


def test_validate_sighting_removed_present():
    values, errors = validate_sighting({"seen_on": "2026-06-05", "removed": "1"}, {1})
    assert errors == {}
    assert values["removed"] is True


def test_validate_sighting_all_fields():
    values, errors = validate_sighting(GOOD, {7, 8, 9})
    assert errors == {}
    assert set(values.keys()) == {"seen_on", "count", "notes", "removed", "object_id"}

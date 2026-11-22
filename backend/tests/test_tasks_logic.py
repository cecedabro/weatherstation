"""Tests for pure helpers in app/tasks.py (T03 – Tasks logic).

SPEC §14.1 – task_sort_key, §14.2 – deadline_text,
§14.3 – validate_task_form, and local_today.
"""

from datetime import UTC, date, datetime, timedelta

from app.tasks import (
    deadline_text,
    local_today,
    task_sort_key,
    validate_task_form,
)

# Default values used when testing individual fields
_DEFAULTS = {
    "title": "Test task",
    "category": "repair",
    "urgency": "high",
    "deadline": "2026-06-01",
    "object_id": "1",
}


def _merge(form: dict, defaults: dict) -> dict:
    """Merge *defaults* into *form* (form keys take priority)."""
    merged = dict(defaults)
    merged.update(form)
    return merged


# ---------------------------------------------------------------------------
# deadline_text  (SPEC 14.2)
# ---------------------------------------------------------------------------


class TestDeadlineTextToday:
    """deadline_text when deadline == today → 'due today'."""

    def test_same_date(self):
        today = date(2026, 5, 15)
        text, overdue = deadline_text(today, today)
        assert text == "due today"
        assert overdue is False

    def test_same_mid_month(self):
        today = date(2026, 11, 22)
        text, overdue = deadline_text(today, today)
        assert text == "due today"
        assert overdue is False


class TestDeadlineTextTomorrow:
    """deadline_text when deadline == today + 1 day → 'due tomorrow'."""

    def test_tomorrow(self):
        today = date(2026, 5, 15)
        deadline = today + timedelta(days=1)
        text, overdue = deadline_text(deadline, today)
        assert text == "due tomorrow"
        assert overdue is False

    def test_end_of_month(self):
        today = date(2026, 1, 31)
        deadline = today + timedelta(days=1)
        text, overdue = deadline_text(deadline, today)
        assert text == "due tomorrow"
        assert overdue is False


class TestDeadlineTextInNDays:
    """deadline_text when deadline > today + 1 → 'due in N days'."""

    def test_two_days(self):
        today = date(2026, 5, 15)
        deadline = today + timedelta(days=2)
        text, overdue = deadline_text(deadline, today)
        assert text == "due in 2 days"
        assert overdue is False

    def test_7_days(self):
        today = date(2026, 12, 1)
        deadline = today + timedelta(days=7)
        text, overdue = deadline_text(deadline, today)
        assert text == "due in 7 days"
        assert overdue is False

    def test_365_days(self):
        today = date(2026, 1, 1)
        deadline = today + timedelta(days=365)
        text, overdue = deadline_text(deadline, today)
        assert text == "due in 365 days"
        assert overdue is False


class TestDeadlineTextOverdue:
    """deadline_text when deadline < today → 'overdue by N days'."""

    def test_overdue_one_day(self):
        today = date(2026, 5, 15)
        deadline = today - timedelta(days=1)
        text, overdue = deadline_text(deadline, today)
        assert text == "overdue by 1 days"
        assert overdue is True

    def test_overdue_three_days(self):
        today = date(2026, 10, 1)
        deadline = today - timedelta(days=3)
        text, overdue = deadline_text(deadline, today)
        assert text == "overdue by 3 days"
        assert overdue is True

    def test_overdue_30_days(self):
        today = date(2026, 1, 1)
        deadline = today - timedelta(days=30)
        text, overdue = deadline_text(deadline, today)
        assert text == "overdue by 30 days"
        assert overdue is True


# ---------------------------------------------------------------------------
# task_sort_key  (SPEC 14.1)
# ---------------------------------------------------------------------------


class _FakeTask:
    """Minimal task-like object for testing sort_key."""

    def __init__(
        self,
        urgency: str,
        deadline=None,
        created_at=None,
    ):
        self.urgency = urgency
        self.deadline = deadline
        self.created_at = created_at


class TestSortUrgency:
    """Sort by urgency: critical, high, normal, low."""

    def test_critical_first(self):
        low = _FakeTask("low", deadline=date(2026, 1, 1))
        crit = _FakeTask("critical", deadline=date(2026, 12, 31))
        assert task_sort_key(crit) < task_sort_key(low)

    def test_high_before_normal(self):
        normal = _FakeTask("normal", deadline=date(2026, 1, 1))
        high = _FakeTask("high", deadline=date(2026, 12, 31))
        assert task_sort_key(high) < task_sort_key(normal)

    def test_normal_before_low(self):
        low = _FakeTask("low", deadline=date(2026, 1, 1))
        normal = _FakeTask("normal", deadline=date(2026, 12, 31))
        assert task_sort_key(normal) < task_sort_key(low)

    def test_all_urgency_order(self):
        tasks = [
            _FakeTask("low"),
            _FakeTask("critical"),
            _FakeTask("high"),
            _FakeTask("normal"),
        ]
        tasks.sort(key=task_sort_key)
        assert [t.urgency for t in tasks] == ["critical", "high", "normal", "low"]


class TestSortDeadline:
    """Same urgency: sooner deadline first; None deadline last."""

    def test_sooner_first(self):
        early = _FakeTask("normal", deadline=date(2026, 1, 1))
        late = _FakeTask("normal", deadline=date(2026, 12, 31))
        assert task_sort_key(early) < task_sort_key(late)

    def test_none_deadline_last(self):
        with_deadline = _FakeTask("critical", deadline=date(2026, 1, 1))
        no_deadline = _FakeTask("critical")
        assert task_sort_key(with_deadline) < task_sort_key(no_deadline)

    def test_none_deadline_vs_none(self):
        a = _FakeTask("normal")
        b = _FakeTask("normal")
        # Both None deadlines → compare created_at (both None → equal)
        assert task_sort_key(a) == task_sort_key(b)


class TestSortCreatedNewestFirst:
    """Same urgency and deadline: newest first."""

    def test_newer_first(self):
        old = _FakeTask(
            "normal", deadline=date(2026, 6, 1), created_at=datetime(2026, 5, 1, tzinfo=UTC)
        )
        new = _FakeTask(
            "normal", deadline=date(2026, 6, 1), created_at=datetime(2026, 5, 10, tzinfo=UTC)
        )
        assert task_sort_key(new) < task_sort_key(old)

    def test_same_deadline_different_created(self):
        one = _FakeTask(
            "high", deadline=date(2026, 3, 15), created_at=datetime(2026, 3, 1, tzinfo=UTC)
        )
        two = _FakeTask(
            "high", deadline=date(2026, 3, 15), created_at=datetime(2026, 3, 10, tzinfo=UTC)
        )
        three = _FakeTask(
            "high", deadline=date(2026, 3, 15), created_at=datetime(2026, 3, 5, tzinfo=UTC)
        )
        tasks = [one, two, three]
        tasks.sort(key=task_sort_key)
        assert tasks[0].created_at.day == 10
        assert tasks[1].created_at.day == 5
        assert tasks[2].created_at.day == 1


class TestSortCombined:
    """All three criteria together."""

    def test_full_sort(self):
        tasks = [
            _FakeTask(
                "low", deadline=date(2026, 1, 1), created_at=datetime(2026, 1, 1, tzinfo=UTC)
            ),
            _FakeTask(
                "critical", deadline=date(2026, 12, 31), created_at=datetime(2026, 1, 1, tzinfo=UTC)
            ),
            _FakeTask("normal", deadline=None, created_at=datetime(2026, 1, 1, tzinfo=UTC)),
            _FakeTask(
                "critical", deadline=date(2026, 1, 1), created_at=datetime(2026, 6, 1, tzinfo=UTC)
            ),
            _FakeTask(
                "high", deadline=date(2026, 2, 1), created_at=datetime(2026, 1, 1, tzinfo=UTC)
            ),
        ]
        tasks.sort(key=task_sort_key)
        assert [t.urgency for t in tasks] == ["critical", "critical", "high", "normal", "low"]
        # The two critical tasks: earliest deadline first
        assert tasks[0].deadline == date(2026, 1, 1)
        assert tasks[1].deadline == date(2026, 12, 31)


# ---------------------------------------------------------------------------
# local_today  (Europe/Amsterdam date)
# ---------------------------------------------------------------------------


class TestLocalToday:
    """local_today returns a date in Europe/Amsterdam timezone."""

    def test_returns_date(self):
        result = local_today()
        assert isinstance(result, date)
        assert result.year > 2000

    def test_returns_aware_date(self):
        amster = __import__("zoneinfo").ZoneInfo("Europe/Amsterdam")
        expected = datetime.now(UTC).astimezone(amster).date()
        assert local_today() == expected


# ---------------------------------------------------------------------------
# validate_task_form  (SPEC 14.3)
# ---------------------------------------------------------------------------


class TestValidateTitle:
    """Title: 1–120 characters after trimming."""

    def test_empty_title(self):
        values, errors = validate_task_form(_merge({"title": ""}, _DEFAULTS))
        assert "title" in errors
        assert values["title"] == ""

    def test_whitespace_only_title(self):
        values, errors = validate_task_form(_merge({"title": "   "}, _DEFAULTS))
        assert "title" in errors
        assert values["title"] == ""

    def test_valid_minimal_title(self):
        values, errors = validate_task_form(_merge({"title": "X"}, _DEFAULTS))
        assert errors == {}
        assert values["title"] == "X"

    def test_valid_120_char_title(self):
        values, errors = validate_task_form(_merge({"title": "A" * 120}, _DEFAULTS))
        assert errors == {}
        assert values["title"] == "A" * 120

    def test_too_long_121_chars(self):
        values, errors = validate_task_form(_merge({"title": "A" * 121}, _DEFAULTS))
        assert "title" in errors
        assert values["title"] == "A" * 121

    def test_leading_trailing_whitespace_trimmed(self):
        values, errors = validate_task_form(_merge({"title": "  Hello  "}, _DEFAULTS))
        assert errors == {}
        assert values["title"] == "Hello"

    def test_none_title(self):
        values, errors = validate_task_form(_merge({"title": None}, _DEFAULTS))
        assert "title" in errors
        assert values["title"] == ""


class TestValidateNotes:
    """Notes: ≤ 2000 characters."""

    def test_empty_notes(self):
        values, errors = validate_task_form(_merge({"notes": ""}, _DEFAULTS))
        assert errors == {}
        assert values["notes"] == ""

    def test_max_2000_notes(self):
        values, errors = validate_task_form(_merge({"notes": "X" * 2000}, _DEFAULTS))
        assert errors == {}
        assert values["notes"] == "X" * 2000

    def test_over_2000_truncated(self):
        values, errors = validate_task_form(_merge({"notes": "X" * 2001}, _DEFAULTS))
        assert errors == {}
        assert values["notes"] == "X" * 2000

    def test_none_notes(self):
        values, errors = validate_task_form(_merge({"notes": None}, _DEFAULTS))
        assert errors == {}
        assert values["notes"] == ""


class TestValidateCategory:
    """Category must be in TASK_CATEGORIES."""

    def test_valid_category_repair(self):
        values, errors = validate_task_form(_merge({"category": "repair"}, _DEFAULTS))
        assert errors == {}
        assert values["category"] == "repair"

    def test_valid_category_other(self):
        values, errors = validate_task_form(_merge({"category": "other"}, _DEFAULTS))
        assert errors == {}
        assert values["category"] == "other"

    def test_all_valid_categories(self):
        from app.models import TASK_CATEGORIES

        for cat in TASK_CATEGORIES:
            values, errors = validate_task_form(_merge({"category": cat}, _DEFAULTS))
            assert errors == {}, f"Category '{cat}' should be valid"
            assert values["category"] == cat

    def test_invalid_category(self):
        values, errors = validate_task_form(_merge({"category": "invalid"}, _DEFAULTS))
        assert "category" in errors
        assert values["category"] == "invalid"

    def test_empty_category(self):
        values, errors = validate_task_form(_merge({"category": ""}, _DEFAULTS))
        assert "category" in errors
        assert values["category"] == ""


class TestValidateUrgency:
    """Urgency must be in TASK_URGENCIES."""

    def test_valid_urgency_critical(self):
        values, errors = validate_task_form(_merge({"urgency": "critical"}, _DEFAULTS))
        assert errors == {}
        assert values["urgency"] == "critical"

    def test_valid_urgency_low(self):
        values, errors = validate_task_form(_merge({"urgency": "low"}, _DEFAULTS))
        assert errors == {}
        assert values["urgency"] == "low"

    def test_all_valid_urgencies(self):
        from app.models import TASK_URGENCIES

        for urg in TASK_URGENCIES:
            values, errors = validate_task_form(_merge({"urgency": urg}, _DEFAULTS))
            assert errors == {}, f"Urgency '{urg}' should be valid"
            assert values["urgency"] == urg

    def test_invalid_urgency(self):
        values, errors = validate_task_form(_merge({"urgency": "extreme"}, _DEFAULTS))
        assert "urgency" in errors
        assert values["urgency"] == "extreme"

    def test_empty_urgency(self):
        values, errors = validate_task_form(_merge({"urgency": ""}, _DEFAULTS))
        assert "urgency" in errors
        assert values["urgency"] == ""


class TestValidateDeadline:
    """Deadline: empty or YYYY-MM-DD."""

    def test_empty_deadline(self):
        values, errors = validate_task_form(_merge({"deadline": ""}, _DEFAULTS))
        assert errors == {}
        assert values["deadline"] is None

    def test_valid_deadline(self):
        values, errors = validate_task_form(_merge({"deadline": "2026-06-15"}, _DEFAULTS))
        assert errors == {}
        assert values["deadline"] == date(2026, 6, 15)

    def test_invalid_deadline_format(self):
        values, errors = validate_task_form(_merge({"deadline": "15/06/2026"}, _DEFAULTS))
        assert "deadline" in errors
        assert values["deadline"] == "15/06/2026"

    def test_invalid_deadline_gibberish(self):
        values, errors = validate_task_form(_merge({"deadline": "not-a-date"}, _DEFAULTS))
        assert "deadline" in errors

    def test_none_deadline(self):
        values, errors = validate_task_form(_merge({"deadline": None}, _DEFAULTS))
        assert errors == {}
        assert values["deadline"] is None

    def test_deadline_with_whitespace_stripped(self):
        values, errors = validate_task_form(_merge({"deadline": "  2026-03-01  "}, _DEFAULTS))
        assert errors == {}
        assert values["deadline"] == date(2026, 3, 1)


class TestValidateObjectId:
    """object_id: empty or existing garden_object id."""

    def test_empty_object_id(self):
        values, errors = validate_task_form(
            _merge({"object_id": ""}, _DEFAULTS), object_ids=[1, 2, 3]
        )
        assert errors == {}
        assert values["object_id"] is None

    def test_none_object_id(self):
        values, errors = validate_task_form(
            _merge({"object_id": None}, _DEFAULTS), object_ids=[1, 2, 3]
        )
        assert errors == {}
        assert values["object_id"] is None

    def test_valid_object_id(self):
        values, errors = validate_task_form(
            _merge({"object_id": "2"}, _DEFAULTS), object_ids=[1, 2, 3]
        )
        assert errors == {}
        assert values["object_id"] == 2

    def test_invalid_object_id_not_in_list(self):
        values, errors = validate_task_form(
            _merge({"object_id": "99"}, _DEFAULTS), object_ids=[1, 2, 3]
        )
        assert "object_id" in errors
        assert values["object_id"] is None

    def test_non_integer_object_id(self):
        values, errors = validate_task_form(
            _merge({"object_id": "abc"}, _DEFAULTS), object_ids=[1, 2, 3]
        )
        assert "object_id" in errors
        assert values["object_id"] is None

    def test_no_object_ids_filter_allows_any_int(self):
        values, errors = validate_task_form(_merge({"object_id": "42"}, _DEFAULTS))
        assert errors == {}
        assert values["object_id"] == 42

    def test_whitespace_stripped(self):
        values, errors = validate_task_form(
            _merge({"object_id": " 3 "}, _DEFAULTS), object_ids=[1, 2, 3]
        )
        assert errors == {}
        assert values["object_id"] == 3


class TestValidateFormValid:
    """Whole form with valid data produces no errors."""

    def test_all_fields_valid(self):
        form = {
            "title": "Fix the fence",
            "notes": "Use wire and wooden posts",
            "category": "repair",
            "urgency": "high",
            "deadline": "2026-06-01",
            "object_id": "1",
        }
        values, errors = validate_task_form(form, object_ids=[1, 2])
        assert errors == {}
        assert values["title"] == "Fix the fence"
        assert values["category"] == "repair"
        assert values["urgency"] == "high"
        assert values["deadline"] == date(2026, 6, 1)
        assert values["object_id"] == 1


class TestValidateFormMultipleErrors:
    """Multiple invalid fields produce multiple errors."""

    def test_all_fields_invalid(self):
        form = {
            "title": "",
            "notes": None,
            "category": "bad",
            "urgency": "bad",
            "deadline": "xyz",
            "object_id": "999",
        }
        values, errors = validate_task_form(form, object_ids=[1, 2])
        assert "title" in errors
        assert "category" in errors
        assert "urgency" in errors
        assert "deadline" in errors
        assert "object_id" in errors
        assert len(errors) == 5

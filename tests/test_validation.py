"""Tests for the checks on JSON sent to the API (app/services/validation.py)."""

import pytest

from app.services.validation import (
    validate_assignee,
    validate_comment,
    validate_new_ticket,
    validate_status_change,
)


def valid_ticket(**overrides):
    data = {
        "title": "Cannot log in",
        "description": "The login page shows an error.",
        "category": "Account Access",
        "priority": "High",
    }
    data.update(overrides)
    return data


# ---------- new ticket ----------
def test_valid_ticket_passes_and_is_trimmed():
    clean, errors = validate_new_ticket(valid_ticket(title="  Cannot log in  "))

    assert errors == {}
    assert clean["title"] == "Cannot log in"


def test_empty_ticket_reports_every_required_field():
    clean, errors = validate_new_ticket({})

    assert set(errors) == {"title", "description", "category"}  # priority has a default


@pytest.mark.parametrize(
    "title, ok",
    [("ab", False), ("abc", True), ("x" * 120, True), ("x" * 121, False)],
)
def test_title_length_boundaries(title, ok):
    _, errors = validate_new_ticket(valid_ticket(title=title))

    assert ("title" not in errors) is ok


@pytest.mark.parametrize(
    "description, ok",
    [("x" * 9, False), ("x" * 10, True), ("x" * 5000, True), ("x" * 5001, False)],
)
def test_description_length_boundaries(description, ok):
    _, errors = validate_new_ticket(valid_ticket(description=description))

    assert ("description" not in errors) is ok


def test_spaces_only_title_counts_as_missing():
    _, errors = validate_new_ticket(valid_ticket(title="     "))

    assert errors["title"] == "Title is required."


def test_title_must_be_text():
    _, errors = validate_new_ticket(valid_ticket(title=12345))

    assert errors["title"] == "Title must be text."


def test_bad_category_and_priority_are_both_reported():
    _, errors = validate_new_ticket(valid_ticket(category="Banana", priority="Mega"))

    assert "category" in errors
    assert "priority" in errors


def test_priority_defaults_to_medium():
    data = valid_ticket()
    del data["priority"]

    clean, errors = validate_new_ticket(data)

    assert errors == {}
    assert clean["priority"] == "Medium"


# ---------- comments ----------
def test_valid_comment_is_trimmed():
    clean, errors = validate_comment({"body": "  Thanks!  "})

    assert errors == {}
    assert clean["body"] == "Thanks!"


@pytest.mark.parametrize("data", [{}, {"body": ""}, {"body": "   "}])
def test_blank_comment_is_rejected(data):
    _, errors = validate_comment(data)

    assert "body" in errors


@pytest.mark.parametrize("length, ok", [(2000, True), (2001, False)])
def test_comment_length_limit(length, ok):
    _, errors = validate_comment({"body": "x" * length})

    assert ("body" not in errors) is ok


# ---------- status change ----------
def test_valid_status_change():
    clean, errors = validate_status_change({"status": "Resolved", "resolution_note": " Fixed. "})

    assert errors == {}
    assert clean == {"status": "Resolved", "resolution_note": "Fixed."}


def test_blank_note_becomes_none():
    clean, errors = validate_status_change({"status": "Open", "resolution_note": "   "})

    assert errors == {}
    assert clean["resolution_note"] is None


def test_note_must_be_text():
    _, errors = validate_status_change({"status": "Open", "resolution_note": 123})

    assert "resolution_note" in errors


def test_note_too_long():
    _, errors = validate_status_change({"status": "Open", "resolution_note": "x" * 2001})

    assert "resolution_note" in errors


def test_unknown_status_value():
    _, errors = validate_status_change({"status": "Banana"})

    assert "status" in errors


# ---------- assignee ----------
def test_assignee_key_is_required():
    _, errors = validate_assignee({})

    assert "assignee_id" in errors


def test_assignee_null_is_allowed():
    clean, errors = validate_assignee({"assignee_id": None})

    assert errors == {}
    assert clean["assignee_id"] is None


def test_assignee_whole_number_is_allowed():
    clean, errors = validate_assignee({"assignee_id": 7})

    assert errors == {}
    assert clean["assignee_id"] == 7


@pytest.mark.parametrize("bad_value", [True, "1", 1.5])
def test_assignee_wrong_types_are_rejected(bad_value):
    _, errors = validate_assignee({"assignee_id": bad_value})

    assert "assignee_id" in errors
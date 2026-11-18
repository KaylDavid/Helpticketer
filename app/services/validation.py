"""Checks for data that arrives as JSON (the API).

Each function returns (clean_data, errors).
- errors is a dict like {"title": "Title is required."}
- If errors is empty, clean_data is safe to use.
"""

from ..models import CATEGORIES, PRIORITIES, STATUSES


def _text(data, field, label, min_len, max_len, errors):
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors[field] = f"{label} is required."
        return None
    if not isinstance(value, str):
        errors[field] = f"{label} must be text."
        return None
    value = value.strip()
    if len(value) < min_len or len(value) > max_len:
        errors[field] = f"{label} must be {min_len} to {max_len} characters."
        return None
    return value


def _choice(value, field, label, choices, errors):
    if value not in choices:
        errors[field] = f"{label} must be one of: {', '.join(choices)}."
        return None
    return value


def validate_new_ticket(data):
    errors = {}
    clean = {
        "title": _text(data, "title", "Title", 3, 120, errors),
        "description": _text(data, "description", "Description", 10, 5000, errors),
        "category": _choice(data.get("category"), "category", "Category", CATEGORIES, errors),
        # Priority is optional and defaults to Medium
        "priority": _choice(
            data.get("priority", "Medium"), "priority", "Priority", PRIORITIES, errors
        ),
    }
    return clean, errors


def validate_comment(data):
    errors = {}
    clean = {"body": _text(data, "body", "Comment", 1, 2000, errors)}
    return clean, errors


def validate_status_change(data):
    errors = {}
    status = _choice(data.get("status"), "status", "Status", STATUSES, errors)

    note = data.get("resolution_note")
    if note is not None:
        if not isinstance(note, str):
            errors["resolution_note"] = "Resolution note must be text."
            note = None
        else:
            note = note.strip() or None
            if note and len(note) > 2000:
                errors["resolution_note"] = "Resolution note must be 2000 characters or fewer."

    return {"status": status, "resolution_note": note}, errors


def validate_assignee(data):
    errors = {}
    if "assignee_id" not in data:
        errors["assignee_id"] = "assignee_id is required (use null to unassign)."
        return {"assignee_id": None}, errors

    value = data["assignee_id"]
    # bool is a kind of int in Python, so reject it explicitly
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        errors["assignee_id"] = "assignee_id must be a whole number or null."
        value = None
    return {"assignee_id": value}, errors
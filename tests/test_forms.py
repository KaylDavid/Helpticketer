"""Tests for the web forms: bad input, tampering, and unsafe text."""

import pytest

from app.models import Ticket


def page_text(response):
    return response.get_data(as_text=True)


def ticket_form(**overrides):
    data = {
        "title": "Cannot log in",
        "description": "The login page shows an error message.",
        "category": "Account Access",
        "priority": "High",
    }
    data.update(overrides)
    return data


def test_empty_ticket_form_shows_errors(client, user, login):
    login(user.email)

    response = client.post("/tickets/new", data={})

    text = page_text(response)
    assert response.status_code == 200
    assert "Please enter a title." in text
    assert "Please describe the problem." in text
    assert Ticket.query.count() == 0


def test_short_title_message(client, user, login):
    login(user.email)

    response = client.post("/tickets/new", data=ticket_form(title="Hi"))

    assert "Title must be 3 to 120 characters." in page_text(response)
    assert Ticket.query.count() == 0


def test_faked_dropdown_value_is_rejected(client, user, login):
    """Someone editing the HTML to send category=Banana must not get a ticket saved."""
    login(user.email)

    response = client.post("/tickets/new", data=ticket_form(category="Banana"))

    assert response.status_code == 200
    assert Ticket.query.count() == 0


def test_title_spaces_are_trimmed(client, user, login):
    login(user.email)

    client.post("/tickets/new", data=ticket_form(title="   Padded title   "))

    assert Ticket.query.one().title == "Padded title"


def test_script_in_ticket_title_is_shown_as_text(client, user, make_ticket, login):
    ticket = make_ticket(requester=user, title="<script>alert(1)</script>")
    login(user.email)

    text = page_text(client.get(f"/tickets/{ticket.id}"))

    assert "<script>alert(1)</script>" not in text  # would run in a browser
    assert "&lt;script&gt;" in text  # safe, escaped version


def test_script_in_comment_is_shown_as_text(client, user, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(user.email)

    client.post(f"/tickets/{ticket.id}/comments", data={"body": "<script>alert(2)</script>"})
    text = page_text(client.get(f"/tickets/{ticket.id}"))

    assert "<script>alert(2)</script>" not in text
    assert "&lt;script&gt;" in text


@pytest.mark.parametrize("bad_status", ["Banana", "Open"])
def test_status_form_only_accepts_legal_next_statuses(
    client, user, agent, make_ticket, login, reload, bad_status
):
    """A Resolved ticket may go to In Progress or Closed. Nothing else is accepted."""
    ticket = make_ticket(requester=user, status="Resolved", resolution_note="Fixed.")
    login(agent.email)

    response = client.post(f"/tickets/{ticket.id}/status", data={"status": bad_status})

    assert response.status_code == 200
    assert reload(Ticket, ticket.id).status == "Resolved"
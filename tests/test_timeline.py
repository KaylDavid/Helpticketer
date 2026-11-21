"""Tests for the ticket activity timeline and the events behind it."""

from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import Comment, Ticket, TicketEvent
from app.services.tickets import assign_ticket, change_status
from app.services.timeline import build_timeline


def page_text(response):
    return response.get_data(as_text=True)


# ---------- the timeline builder ----------
def test_new_ticket_timeline_starts_with_created(user, make_ticket):
    ticket = make_ticket(requester=user)

    items = build_timeline(ticket)

    assert len(items) == 1
    assert items[0]["kind"] == "created"
    assert items[0]["actor_name"] == user.name


def test_timeline_is_sorted_by_time(user, agent, make_ticket):
    ticket = make_ticket(requester=user)
    base = datetime(2026, 1, 1, 10, 0)
    ticket.created_at = base
    db.session.add_all(
        [
            TicketEvent(
                ticket=ticket, actor=agent, kind="status", detail="did a thing",
                created_at=base + timedelta(hours=1),
            ),
            Comment(
                ticket=ticket, author=user, body="hi",
                created_at=base + timedelta(minutes=30),
            ),
        ]
    )
    db.session.commit()

    kinds = [item["kind"] for item in build_timeline(ticket)]

    assert kinds == ["created", "comment", "status"]


def test_event_without_actor_is_shown_as_system(user, make_ticket):
    ticket = make_ticket(requester=user)

    change_status(ticket, "In Progress")  # no actor given

    last = build_timeline(ticket)[-1]
    assert last["actor_name"] == "System"


# ---------- events recorded by the service layer ----------
def test_assign_records_event(user, agent, admin, make_ticket):
    ticket = make_ticket(requester=user)

    assign_ticket(ticket, admin, actor=agent)

    event = TicketEvent.query.one()
    assert event.kind == "assigned"
    assert event.actor_id == agent.id
    assert "assigned this ticket to Adam Admin" in event.detail


def test_self_assign_reads_as_picked_up(user, agent, make_ticket):
    ticket = make_ticket(requester=user)

    assign_ticket(ticket, agent, actor=agent)

    assert TicketEvent.query.one().detail == "picked up this ticket"


def test_assigning_to_same_person_records_nothing_new(user, agent, make_ticket):
    ticket = make_ticket(requester=user)

    assign_ticket(ticket, agent, actor=agent)
    assign_ticket(ticket, agent, actor=agent)

    assert TicketEvent.query.count() == 1


def test_unassign_records_event(user, agent, make_ticket):
    ticket = make_ticket(requester=user, assignee=agent)

    assign_ticket(ticket, None, actor=agent)

    event = TicketEvent.query.one()
    assert event.detail == "removed the assignee"


def test_status_change_records_event(user, agent, make_ticket):
    ticket = make_ticket(requester=user)

    change_status(ticket, "In Progress", actor=agent)

    event = TicketEvent.query.one()
    assert event.kind == "status"
    assert event.actor_id == agent.id
    assert event.detail == "changed the status from Open to In Progress"


def test_rejected_changes_record_nothing(user, other_user, make_ticket):
    ticket = make_ticket(requester=user, status="In Progress")

    with pytest.raises(ValueError):
        change_status(ticket, "Resolved", "")  # note missing
    with pytest.raises(ValueError):
        assign_ticket(ticket, other_user)  # regular users cannot be assigned

    assert TicketEvent.query.count() == 0


# ---------- through the web page and the API ----------
def test_web_assignment_shows_in_timeline(client, user, agent, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(agent.email)

    client.post(f"/tickets/{ticket.id}/assign", data={"assignee": agent.id})
    text = page_text(client.get(f"/tickets/{ticket.id}"))

    assert 'data-testid="timeline"' in text
    assert "picked up this ticket" in text


def test_requester_can_see_the_timeline(client, user, agent, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(agent.email)
    client.post(f"/tickets/{ticket.id}/status", data={"status": "In Progress"})
    client.post("/logout")
    login(user.email)

    text = page_text(client.get(f"/tickets/{ticket.id}"))

    assert "changed the status from Open to In Progress" in text


def test_api_status_change_records_the_caller(client, user, agent, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    client.patch(
        f"/api/tickets/{ticket.id}/status",
        json={"status": "In Progress"},
        headers=basic_auth(agent.email),
    )

    events = reload(Ticket, ticket.id).events
    assert len(events) == 1
    assert events[0].actor_id == agent.id


def test_api_assignment_records_the_caller(client, user, agent, admin, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": admin.id},
        headers=basic_auth(agent.email),
    )

    events = reload(Ticket, ticket.id).events
    assert len(events) == 1
    assert events[0].actor_id == agent.id
    assert "Adam Admin" in events[0].detail
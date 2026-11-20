"""Tests for the business rules in app/services/tickets.py (no web requests)."""

import pytest

from app.models import STATUSES
from app.services.tickets import (
    STATUS_TRANSITIONS,
    add_comment,
    allowed_next_statuses,
    assign_ticket,
    change_status,
    visible_tickets_query,
)
from app.extensions import db

ALLOWED = [(old, new) for old, targets in STATUS_TRANSITIONS.items() for new in targets]
FORBIDDEN = [
    (old, new)
    for old in STATUSES
    for new in STATUSES
    if (old, new) not in ALLOWED
]


# ---------- the status workflow table ----------
def test_transition_table_only_uses_real_statuses():
    assert set(STATUS_TRANSITIONS.keys()) == set(STATUSES)
    for targets in STATUS_TRANSITIONS.values():
        assert set(targets) <= set(STATUSES)


@pytest.mark.parametrize("old, new", ALLOWED)
def test_allowed_transition_works(user, make_ticket, old, new):
    ticket = make_ticket(requester=user, status=old)

    change_status(ticket, new, "Done.")  # a note is always given, so Resolved is fine

    assert ticket.status == new


@pytest.mark.parametrize("old, new", FORBIDDEN)
def test_forbidden_transition_is_rejected(user, make_ticket, old, new):
    ticket = make_ticket(requester=user, status=old)

    with pytest.raises(ValueError, match="cannot move"):
        change_status(ticket, new, "Done.")

    assert ticket.status == old


def test_closed_is_final(user, make_ticket):
    ticket = make_ticket(requester=user, status="Closed")

    assert allowed_next_statuses(ticket) == ()


def test_unknown_status_is_rejected(user, make_ticket):
    ticket = make_ticket(requester=user)

    with pytest.raises(ValueError, match="Unknown status"):
        change_status(ticket, "Banana")


# ---------- resolution notes ----------
@pytest.mark.parametrize("note", [None, "", "   "])
def test_resolving_requires_a_real_note(user, make_ticket, note):
    ticket = make_ticket(requester=user, status="In Progress")

    with pytest.raises(ValueError, match="resolution note is required"):
        change_status(ticket, "Resolved", note)

    assert ticket.status == "In Progress"


def test_resolving_saves_the_note(user, make_ticket):
    ticket = make_ticket(requester=user, status="In Progress")

    change_status(ticket, "Resolved", "  Replaced the cable.  ")

    assert ticket.resolution_note == "Replaced the cable."  # spaces trimmed


def test_note_is_kept_when_a_ticket_is_reopened(user, make_ticket):
    ticket = make_ticket(
        requester=user, status="Resolved", resolution_note="Replaced the cable."
    )

    change_status(ticket, "In Progress")  # no new note given

    assert ticket.status == "In Progress"
    assert ticket.resolution_note == "Replaced the cable."


# ---------- assigning ----------
def test_assign_to_agent(user, agent, make_ticket):
    ticket = make_ticket(requester=user)

    assign_ticket(ticket, agent)

    assert ticket.assignee_id == agent.id


def test_assign_to_admin(user, admin, make_ticket):
    ticket = make_ticket(requester=user)

    assign_ticket(ticket, admin)

    assert ticket.assignee_id == admin.id


def test_unassign(user, agent, make_ticket):
    ticket = make_ticket(requester=user, assignee=agent)

    assign_ticket(ticket, None)

    assert ticket.assignee is None


def test_cannot_assign_to_regular_user(user, other_user, make_ticket):
    ticket = make_ticket(requester=user)

    with pytest.raises(ValueError, match="agent or admin"):
        assign_ticket(ticket, other_user)

    assert ticket.assignee is None


def test_cannot_assign_closed_ticket(user, agent, make_ticket):
    ticket = make_ticket(requester=user, status="Closed")

    with pytest.raises(ValueError, match="closed"):
        assign_ticket(ticket, agent)


# ---------- comments ----------
def test_closed_ticket_rejects_comment(user, make_ticket):
    ticket = make_ticket(requester=user, status="Closed")

    with pytest.raises(ValueError, match="closed"):
        add_comment(ticket, user, "Hello?")

    assert len(ticket.comments) == 0


def test_comment_is_saved_and_trimmed(user, make_ticket):
    ticket = make_ticket(requester=user)

    comment = add_comment(ticket, user, "  Still broken.  ")

    assert comment.body == "Still broken."
    assert comment.author_id == user.id


# ---------- who sees which tickets ----------
def test_visible_query_for_regular_user(user, other_user, make_ticket):
    make_ticket(requester=user, title="Mine")
    make_ticket(requester=other_user, title="Not mine")

    tickets = db.session.scalars(visible_tickets_query(user)).all()

    assert [t.title for t in tickets] == ["Mine"]


def test_visible_query_for_staff(user, other_user, agent, make_ticket):
    make_ticket(requester=user)
    make_ticket(requester=other_user)

    tickets = db.session.scalars(visible_tickets_query(agent)).all()

    assert len(tickets) == 2
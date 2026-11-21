from ..extensions import db
from ..models import STATUSES, Comment, Ticket, TicketEvent, User

# The status workflow: each status lists the statuses it is allowed to move to.
STATUS_TRANSITIONS = {
    "Open": ("In Progress", "Resolved", "Closed"),
    "In Progress": ("Open", "Resolved", "Closed"),
    "Resolved": ("In Progress", "Closed"),
    "Closed": (),  # Closed is final
}


def create_ticket(requester, title, description, category, priority):
    """Create a ticket for the given requester and save it."""
    ticket = Ticket(
        title=title.strip(),
        description=description.strip(),
        category=category,
        priority=priority,
        status="Open",
        requester=requester,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def visible_tickets_query(user):
    """Build the database query for the tickets this user is allowed to see.

    - Staff (agent/admin): every ticket
    - Regular user: only tickets they created
    Newest tickets come first.
    """
    query = db.select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
    if not user.is_staff:
        query = query.where(Ticket.requester_id == user.id)
    return query


def can_comment(ticket):
    """Business rule: a Closed ticket does not accept new comments."""
    return ticket.status != "Closed"


def add_comment(ticket, author, body):
    """Add a comment to a ticket. Raises ValueError if the ticket is closed."""
    if not can_comment(ticket):
        raise ValueError("This ticket is closed, so new comments are not allowed.")
    comment = Comment(ticket=ticket, author=author, body=body.strip())
    db.session.add(comment)
    db.session.commit()
    return comment


def staff_users():
    """All agents and admins (the people a ticket can be assigned to)."""
    query = db.select(User).where(User.role.in_(("agent", "admin"))).order_by(User.name)
    return db.session.scalars(query).all()


def allowed_next_statuses(ticket):
    """The statuses this ticket is allowed to move to from where it is now."""
    return STATUS_TRANSITIONS.get(ticket.status, ())


def record_event(ticket, actor, kind, detail):
    """Add one line of history to a ticket. The caller commits."""
    db.session.add(TicketEvent(ticket=ticket, actor=actor, kind=kind, detail=detail))


def assign_ticket(ticket, assignee, actor=None):
    """Assign a ticket to a staff member (or pass None to unassign it).

    `actor` is who is doing it (used for the history). Raises ValueError if the
    rules are broken. Assigning to the person who already has it changes nothing.
    """
    if ticket.status == "Closed":
        raise ValueError("This ticket is closed, so it cannot be reassigned.")
    if assignee is not None and not assignee.is_staff:
        raise ValueError("Tickets can only be assigned to an agent or admin.")

    new_id = assignee.id if assignee else None
    if ticket.assignee_id == new_id:
        return ticket  # nothing changed, so nothing to record

    ticket.assignee = assignee
    if assignee is None:
        detail = "removed the assignee"
    elif actor is not None and actor.id == assignee.id:
        detail = "picked up this ticket"
    else:
        detail = f"assigned this ticket to {assignee.name}"
    record_event(ticket, actor, "assigned", detail)
    db.session.commit()
    return ticket


def change_status(ticket, new_status, resolution_note=None, actor=None):
    """Move a ticket to a new status, following the workflow rules.

    Raises ValueError if the move is not allowed or a required note is missing.
    """
    if new_status not in STATUSES:
        raise ValueError("Unknown status.")
    if new_status not in allowed_next_statuses(ticket):
        raise ValueError(f"A ticket cannot move from {ticket.status} to {new_status}.")

    note = (resolution_note or "").strip()
    if new_status == "Resolved" and not note:
        raise ValueError("A resolution note is required when resolving a ticket.")

    old_status = ticket.status
    ticket.status = new_status
    if note:
        ticket.resolution_note = note
    record_event(ticket, actor, "status", f"changed the status from {old_status} to {new_status}")
    db.session.commit()
    return ticket
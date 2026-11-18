from ..extensions import db
from ..models import Ticket


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
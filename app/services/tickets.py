from ..extensions import db
from ..models import Comment, Ticket


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
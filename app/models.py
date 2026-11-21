from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

# Allowed values live in one place so forms, the API, and tests can all reuse them.
ROLES = ("user", "agent", "admin")
STATUSES = ("Open", "In Progress", "Resolved", "Closed")
PRIORITIES = ("Low", "Medium", "High", "Urgent")
CATEGORIES = ("Hardware", "Software", "Network", "Account Access", "Other")


def utcnow():
    """Current time in UTC. Used as the default for created_at / updated_at."""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Tickets this person created / tickets assigned to this person
    tickets_created = db.relationship(
        "Ticket", foreign_keys="Ticket.requester_id", back_populates="requester"
    )
    tickets_assigned = db.relationship(
        "Ticket", foreign_keys="Ticket.assignee_id", back_populates="assignee"
    )
    comments = db.relationship("Comment", back_populates="author")

    def set_password(self, password):
        """Hash the password and store the hash (never the real password)."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True if the given password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_staff(self):
        """True for agents and admins (people who can handle tickets)."""
        return self.role in ("agent", "admin")

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this on each request to turn the session's user id into a User."""
    return db.session.get(User, int(user_id))


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(20), nullable=False, default="Open", index=True)
    resolution_note = db.Column(db.Text)  # filled in by an agent when resolving

    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # empty until assigned

    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    requester = db.relationship(
        "User", foreign_keys=[requester_id], back_populates="tickets_created"
    )
    assignee = db.relationship(
        "User", foreign_keys=[assignee_id], back_populates="tickets_assigned"
    )
    comments = db.relationship(
        "Comment",
        back_populates="ticket",
        order_by="Comment.created_at",
        cascade="all, delete-orphan",
    )
    events = db.relationship(
        "TicketEvent",
        back_populates="ticket",
        order_by="TicketEvent.created_at",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Ticket #{self.id} {self.status}>"


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    ticket = db.relationship("Ticket", back_populates="comments")
    author = db.relationship("User", back_populates="comments")

    def __repr__(self):
        return f"<Comment #{self.id} on ticket {self.ticket_id}>"


class TicketEvent(db.Model):
    """One line of ticket history: an assignment or a status change."""

    __tablename__ = "ticket_events"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False)  # "assigned" or "status"
    detail = db.Column(db.String(255), nullable=False)  # e.g. "picked up this ticket"
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # empty = done by the system

    ticket = db.relationship("Ticket", back_populates="events")
    actor = db.relationship("User")

    def __repr__(self):
        return f"<TicketEvent #{self.id} {self.kind} on ticket {self.ticket_id}>"
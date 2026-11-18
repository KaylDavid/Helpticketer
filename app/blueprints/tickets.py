from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import CommentForm, TicketForm
from ..models import Ticket
from ..permissions import can_view_ticket
from ..services.tickets import (
    add_comment,
    can_comment,
    create_ticket,
    visible_tickets_query,
)

bp = Blueprint("tickets", __name__, url_prefix="/tickets")


def get_ticket_or_404(ticket_id):
    """Load a ticket, or stop with 404 if it is missing OR the person may not see it.

    Using 404 for both cases means we never reveal that a hidden ticket exists.
    """
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None or not can_view_ticket(current_user, ticket):
        abort(404)
    return ticket


@bp.route("/")
@login_required
def index():
    """List the tickets this person is allowed to see."""
    tickets = db.session.scalars(visible_tickets_query(current_user)).all()
    return render_template("tickets/list.html", tickets=tickets)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    """Show the 'create ticket' form and save the ticket."""
    form = TicketForm()
    if form.validate_on_submit():
        create_ticket(
            requester=current_user,  # set by the server, never by the form
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            priority=form.priority.data,
        )
        flash("Ticket submitted! Our team will take a look.", "success")
        return redirect(url_for("tickets.index"))

    return render_template("tickets/new.html", form=form)


@bp.route("/<int:ticket_id>")
@login_required
def detail(ticket_id):
    """Show one ticket with its comments."""
    ticket = get_ticket_or_404(ticket_id)
    form = CommentForm()
    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        form=form,
        can_comment=can_comment(ticket),
    )


@bp.route("/<int:ticket_id>/comments", methods=["POST"])
@login_required
def post_comment(ticket_id):
    """Save a new comment on a ticket."""
    ticket = get_ticket_or_404(ticket_id)

    if not can_comment(ticket):
        flash("This ticket is closed, so new comments are not allowed.", "error")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    form = CommentForm()
    if form.validate_on_submit():
        add_comment(ticket, author=current_user, body=form.body.data)
        flash("Comment added.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    # Validation failed: show the same page again with the error messages
    return render_template(
        "tickets/detail.html", ticket=ticket, form=form, can_comment=True
    )
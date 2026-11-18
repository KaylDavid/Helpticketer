from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import AssignForm, CommentForm, StatusForm, TicketForm
from ..models import Ticket, User
from ..permissions import can_view_ticket, staff_required
from ..services.tickets import (
    add_comment,
    allowed_next_statuses,
    assign_ticket,
    can_comment,
    change_status,
    create_ticket,
    staff_users,
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


def build_assign_form(ticket):
    """Make the assign form with a dropdown of staff members."""
    form = AssignForm()
    form.assignee.choices = [(0, "Unassigned")] + [
        (user.id, f"{user.name} ({user.role})") for user in staff_users()
    ]
    return form


def build_status_form(ticket):
    """Make the status form with only the statuses this ticket may move to."""
    form = StatusForm()
    form.status.choices = [(status, status) for status in allowed_next_statuses(ticket)]
    return form


def render_detail(ticket, comment_form=None, assign_form=None, status_form=None):
    """Show the ticket page. Staff also get the assign and status forms."""
    if comment_form is None:
        comment_form = CommentForm()

    if current_user.is_staff:
        if assign_form is None:
            assign_form = build_assign_form(ticket)
            assign_form.assignee.data = ticket.assignee_id or 0
        if status_form is None:
            status_form = build_status_form(ticket)
    else:
        assign_form = None
        status_form = None

    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        form=comment_form,
        assign_form=assign_form,
        status_form=status_form,
        can_comment=can_comment(ticket),
        can_edit=ticket.status != "Closed",
    )


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
    return render_detail(ticket)


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
    return render_detail(ticket, comment_form=form)


@bp.route("/<int:ticket_id>/assign", methods=["POST"])
@staff_required
def assign(ticket_id):
    """Assign a ticket to an agent/admin (staff only)."""
    ticket = get_ticket_or_404(ticket_id)
    form = build_assign_form(ticket)

    if form.validate_on_submit():
        assignee = db.session.get(User, form.assignee.data) if form.assignee.data else None
        try:
            assign_ticket(ticket, assignee)
        except ValueError as error:
            flash(str(error), "error")
        else:
            if assignee:
                flash(f"Ticket assigned to {assignee.name}.", "success")
            else:
                flash("Ticket is now unassigned.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    return render_detail(ticket, assign_form=form)


@bp.route("/<int:ticket_id>/status", methods=["POST"])
@staff_required
def update_status(ticket_id):
    """Change a ticket's status and optionally save a resolution note (staff only)."""
    ticket = get_ticket_or_404(ticket_id)
    form = build_status_form(ticket)

    if form.validate_on_submit():
        old_status = ticket.status
        try:
            change_status(ticket, form.status.data, form.resolution_note.data)
        except ValueError as error:
            # Show the page again so the typed note is not lost
            flash(str(error), "error")
            return render_detail(ticket, status_form=form)
        flash(f"Status changed from {old_status} to {ticket.status}.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    return render_detail(ticket, status_form=form)
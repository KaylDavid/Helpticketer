from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import TicketForm
from ..services.tickets import create_ticket, visible_tickets_query

bp = Blueprint("tickets", __name__, url_prefix="/tickets")


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
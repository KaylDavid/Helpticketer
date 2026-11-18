from datetime import timezone
from functools import wraps

from flask import Blueprint, g, jsonify, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from ..extensions import db
from ..models import CATEGORIES, PRIORITIES, STATUSES, Ticket, User
from ..permissions import can_view_ticket
from ..services.tickets import (
    add_comment,
    assign_ticket,
    change_status,
    create_ticket,
    visible_tickets_query,
)
from ..services.validation import (
    validate_assignee,
    validate_comment,
    validate_new_ticket,
    validate_status_change,
)

bp = Blueprint("api", __name__, url_prefix="/api")

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


# ---------- helpers ----------
def error_response(message, status, fields=None):
    """Every API error has the same shape."""
    return jsonify(error=message, fields=fields or {}), status


def get_api_user():
    """Work out who is calling the API, or return None.

    1. Basic Auth (email + password) works for every method.
    2. A browser login session works for read-only (GET) requests only.
    """
    if request.headers.get("Authorization"):
        auth = request.authorization
        if auth is None or auth.type != "basic":
            return None
        email = (auth.username or "").strip().lower()
        user = db.session.scalar(db.select(User).filter_by(email=email))
        if user and user.check_password(auth.password or ""):
            return user
        return None

    if current_user.is_authenticated and request.method in SAFE_METHODS:
        return current_user._get_current_object()
    return None


def api_auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_api_user()
        if user is None:
            return error_response(
                "Authentication required. Send your email and password with Basic Auth.", 401
            )
        g.api_user = user
        return view(*args, **kwargs)

    return wrapped


def api_staff_required(view):
    @wraps(view)
    @api_auth_required
    def wrapped(*args, **kwargs):
        if not g.api_user.is_staff:
            return error_response("Only agents and admins can do this.", 403)
        return view(*args, **kwargs)

    return wrapped


def read_json_object():
    """Return (data, None) or (None, error_response)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error_response(
            "Request body must be a JSON object. Send the header Content-Type: application/json.",
            400,
        )
    return data, None


def load_ticket(ticket_id):
    """Return the ticket, or None if it is missing OR the caller may not see it."""
    ticket = db.session.get(Ticket, ticket_id)
    if ticket is None or not can_view_ticket(g.api_user, ticket):
        return None
    return ticket


def int_arg(name, default, minimum, maximum, errors):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        errors[name] = f"{name} must be a whole number."
        return default
    if value < minimum or value > maximum:
        errors[name] = f"{name} must be between {minimum} and {maximum}."
        return default
    return value


# ---------- turning database objects into JSON ----------
def iso(moment):
    """Dates as ISO text in UTC, e.g. 2026-11-18T09:30:00+00:00."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.isoformat()


def user_to_dict(user, with_email=False):
    data = {"id": user.id, "name": user.name, "role": user.role}
    if with_email:
        data["email"] = user.email
    return data


def comment_to_dict(comment):
    return {
        "id": comment.id,
        "body": comment.body,
        "author": user_to_dict(comment.author),
        "created_at": iso(comment.created_at),
    }


def ticket_to_dict(ticket, include_comments=False):
    data = {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "resolution_note": ticket.resolution_note,
        "requester": user_to_dict(ticket.requester),
        "assignee": user_to_dict(ticket.assignee) if ticket.assignee else None,
        "created_at": iso(ticket.created_at),
        "updated_at": iso(ticket.updated_at),
    }
    if include_comments:
        data["comments"] = [comment_to_dict(c) for c in ticket.comments]
    return data


# ---------- endpoints ----------
@bp.route("/me")
@api_auth_required
def me():
    """Who am I? Handy for checking your Postman login."""
    return jsonify(user=user_to_dict(g.api_user, with_email=True))


@bp.route("/tickets")
@api_auth_required
def list_tickets():
    """List tickets this caller may see. Supports filters and paging."""
    errors = {}
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")

    if status and status not in STATUSES:
        errors["status"] = f"status must be one of: {', '.join(STATUSES)}."
    if priority and priority not in PRIORITIES:
        errors["priority"] = f"priority must be one of: {', '.join(PRIORITIES)}."
    if category and category not in CATEGORIES:
        errors["category"] = f"category must be one of: {', '.join(CATEGORIES)}."

    page = int_arg("page", 1, 1, 1_000_000, errors)
    per_page = int_arg("per_page", 10, 1, 50, errors)

    if errors:
        return error_response("Invalid query parameters.", 422, errors)

    query = visible_tickets_query(g.api_user)
    if status:
        query = query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
    if category:
        query = query.where(Ticket.category == category)

    search = request.args.get("q", "").strip()
    if search:
        query = query.where(
            or_(
                Ticket.title.icontains(search, autoescape=True),
                Ticket.description.icontains(search, autoescape=True),
            )
        )

    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify(
        tickets=[ticket_to_dict(t) for t in pagination.items],
        page=pagination.page,
        per_page=pagination.per_page,
        total=pagination.total,
        pages=pagination.pages,
    )


@bp.route("/tickets", methods=["POST"])
@api_auth_required
def create_ticket_endpoint():
    data, problem = read_json_object()
    if problem:
        return problem

    clean, errors = validate_new_ticket(data)
    if errors:
        return error_response("Validation failed.", 422, errors)

    ticket = create_ticket(
        requester=g.api_user,  # set by the server, never by the request body
        title=clean["title"],
        description=clean["description"],
        category=clean["category"],
        priority=clean["priority"],
    )
    response = jsonify(ticket=ticket_to_dict(ticket, include_comments=True))
    response.status_code = 201
    response.headers["Location"] = url_for("api.get_ticket", ticket_id=ticket.id)
    return response


@bp.route("/tickets/<int:ticket_id>")
@api_auth_required
def get_ticket(ticket_id):
    ticket = load_ticket(ticket_id)
    if ticket is None:
        return error_response("Ticket not found.", 404)
    return jsonify(ticket=ticket_to_dict(ticket, include_comments=True))


@bp.route("/tickets/<int:ticket_id>/comments", methods=["POST"])
@api_auth_required
def post_comment(ticket_id):
    ticket = load_ticket(ticket_id)
    if ticket is None:
        return error_response("Ticket not found.", 404)

    data, problem = read_json_object()
    if problem:
        return problem

    clean, errors = validate_comment(data)
    if errors:
        return error_response("Validation failed.", 422, errors)

    try:
        comment = add_comment(ticket, author=g.api_user, body=clean["body"])
    except ValueError as error:
        return error_response(str(error), 409)

    response = jsonify(comment=comment_to_dict(comment))
    response.status_code = 201
    return response


@bp.route("/tickets/<int:ticket_id>/status", methods=["PATCH"])
@api_staff_required
def update_status(ticket_id):
    ticket = load_ticket(ticket_id)
    if ticket is None:
        return error_response("Ticket not found.", 404)

    data, problem = read_json_object()
    if problem:
        return problem

    clean, errors = validate_status_change(data)
    if errors:
        return error_response("Validation failed.", 422, errors)

    try:
        change_status(ticket, clean["status"], clean["resolution_note"])
    except ValueError as error:
        return error_response(str(error), 409)

    return jsonify(ticket=ticket_to_dict(ticket, include_comments=True))


@bp.route("/tickets/<int:ticket_id>/assignee", methods=["PATCH"])
@api_staff_required
def update_assignee(ticket_id):
    ticket = load_ticket(ticket_id)
    if ticket is None:
        return error_response("Ticket not found.", 404)

    data, problem = read_json_object()
    if problem:
        return problem

    clean, errors = validate_assignee(data)
    if errors:
        return error_response("Validation failed.", 422, errors)

    assignee = None
    if clean["assignee_id"] is not None:
        assignee = db.session.get(User, clean["assignee_id"])
        if assignee is None:
            return error_response(
                "Validation failed.", 422, {"assignee_id": "No user with that id."}
            )

    try:
        assign_ticket(ticket, assignee)
    except ValueError as error:
        return error_response(str(error), 409)

    return jsonify(ticket=ticket_to_dict(ticket, include_comments=True))

# ---------- dashboard statistics ----------
from ..services.stats import ticket_stats  # noqa: E402


@bp.route("/stats")
@api_auth_required
def stats():
    """Ticket counts for the dashboard (only counts tickets this caller may see)."""
    return jsonify(stats=ticket_stats(g.api_user))
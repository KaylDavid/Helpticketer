from flask import Blueprint, render_template
from flask_login import login_required

from ..models import CATEGORIES, PRIORITIES, STATUSES

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def home():
    """The dashboard page. Its data is loaded by JavaScript from the API."""
    return render_template(
        "dashboard/home.html",
        statuses=STATUSES,
        priorities=PRIORITIES,
        categories=CATEGORIES,
    )
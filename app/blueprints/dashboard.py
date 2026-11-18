from flask import Blueprint, render_template
from flask_login import login_required

from ..permissions import admin_required, staff_required

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("dashboard/home.html")


# ---- TEMPORARY routes to test role checks (we will delete these later) ----
@bp.route("/staff-area")
@staff_required
def staff_area():
    return "Staff area: agents and admins only."


@bp.route("/admin-area")
@admin_required
def admin_area():
    return "Admin area: admins only."
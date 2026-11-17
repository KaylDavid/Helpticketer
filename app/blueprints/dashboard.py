from flask import Blueprint

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def home():
    return "Helpticketer is running!"
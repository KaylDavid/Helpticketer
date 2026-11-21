from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import LoginForm, RegistrationForm
from ..models import User
from ..services.seed import DEMO_PASSWORD, DEMO_USERS

bp = Blueprint("auth", __name__)

# One demo account per role is enough for a visitor to try the app.
DEMO_LOGIN_EMAILS = ("user@demo.com", "agent@demo.com", "admin@demo.com")


def is_safe_redirect(target):
    """Only allow redirects to paths inside our own site (blocks open redirects)."""
    if not target:
        return False
    return target.startswith("/") and not target.startswith("//") and "\\" not in target


def demo_accounts():
    """The accounts to show in the "Try the demo" box, or None when it is switched off."""
    if not current_app.config.get("SHOW_DEMO_LOGINS"):
        return None
    accounts = [user for user in DEMO_USERS if user[1] in DEMO_LOGIN_EMAILS]
    return {"password": DEMO_PASSWORD, "accounts": accounts}


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.strip().lower(),
            role="user",  # always "user"; the role is never taken from the form
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.scalar(db.select(User).filter_by(email=email))

        if user is None or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "error")
        else:
            login_user(user)
            next_page = request.args.get("next")
            if is_safe_redirect(next_page):
                return redirect(next_page)
            return redirect(url_for("dashboard.home"))

    return render_template("auth/login.html", form=form, demo=demo_accounts())


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
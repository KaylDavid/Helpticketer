import os

import click
from flask import Flask, jsonify, render_template, request

from .config import config_by_name
from .extensions import csrf, db, login_manager


def create_app(config_name=None):
    """Build and return a configured Flask app."""
    if config_name is None:
        config_name = os.environ.get("APP_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Attach the extensions to this app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Where to send people who need to log in first
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to see that page."
    login_manager.login_message_category = "error"

    # Import models so SQLAlchemy knows which tables exist
    from . import models  # noqa: F401

    # Register blueprints (groups of routes)
    from .blueprints.api import bp as api_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.tickets import bp as tickets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(api_bp)

    # The API has no CSRF tokens. This is safe because write requests must use
    # Basic Auth, which browsers never send automatically (see api.py).
    csrf.exempt(api_bp)

    # Friendly error pages (JSON for /api/ URLs, HTML pages for everything else)
    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found.", fields={}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Method not allowed.", fields={}), 405
        return error

    @app.errorhandler(500)
    def server_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Something went wrong on the server.", fields={}), 500
        return error

    # Custom command: flask --app wsgi init-db
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables."""
        db.create_all()
        print("Database tables created.")

    # Custom command: flask --app wsgi create-user NAME EMAIL PASSWORD --role agent
    @app.cli.command("create-user")
    @click.argument("name")
    @click.argument("email")
    @click.argument("password")
    @click.option("--role", default="user", help="user, agent, or admin")
    def create_user(name, email, password, role):
        """Create a user with a specific role (used for agents and admins)."""
        from .models import ROLES, User

        email = email.strip().lower()
        if role not in ROLES:
            print(f"Role must be one of: {', '.join(ROLES)}")
            return
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            return
        if db.session.scalar(db.select(User).filter_by(email=email)):
            print(f"A user with {email} already exists.")
            return

        user = User(name=name.strip(), email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Created {role}: {email}")

    # Custom command: flask --app wsgi seed-demo
    @app.cli.command("seed-demo")
    def seed_demo():
        """Load demo data, but only if the database has no users yet."""
        from .services.seed import seed_if_empty

        if seed_if_empty():
            print("Demo data loaded.")
        else:
            print("Database already has users, so nothing was added.")

    # Custom command: flask --app wsgi reset-demo
    @app.cli.command("reset-demo")
    @click.option("--yes", is_flag=True, help="Skip the confirmation question.")
    def reset_demo_command(yes):
        """DELETE all data and reload the fake demo data."""
        from .services.seed import DEMO_PASSWORD, reset_demo

        if not yes and not click.confirm(
            "This DELETES all tickets and users and loads demo data. Continue?"
        ):
            print("Cancelled. Nothing was changed.")
            return

        users, tickets, comments = reset_demo()
        print(f"Demo data loaded: {users} users, {tickets} tickets, {comments} comments.")
        print(f"Demo accounts: user@demo.com, agent@demo.com, admin@demo.com (password: {DEMO_PASSWORD})")

    return app
import os

import click
from flask import Flask, render_template

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
    from .blueprints.auth import bp as auth_bp
    from .blueprints.dashboard import bp as dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    # Friendly error pages
    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

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

    return app
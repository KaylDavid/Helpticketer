import os

from flask import Flask

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

    # Import models so SQLAlchemy knows which tables exist
    from . import models  # noqa: F401

    # Register blueprints (groups of routes)
    from .blueprints.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)

    # Custom command: flask --app wsgi init-db
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables."""
        db.create_all()
        print("Database tables created.")

    return app
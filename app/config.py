import os


class Config:
    """Settings shared by every environment."""

    # Used to sign session cookies and CSRF tokens.
    # In production we will set a real secret in an environment variable.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # SQLite file. Flask-SQLAlchemy stores it inside the "instance" folder.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///helpticketer.db")

    # Show the "Try the demo" box on the login page? Off unless an environment turns it on.
    SHOW_DEMO_LOGINS = False


class DevelopmentConfig(Config):
    DEBUG = True
    SHOW_DEMO_LOGINS = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    # A database that lives only in memory, so every test starts fresh.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Tests submit forms without CSRF tokens.
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    # A public demo site sets SHOW_DEMO_LOGINS=1. A real deployment leaves it unset.
    SHOW_DEMO_LOGINS = os.environ.get("SHOW_DEMO_LOGINS") == "1"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
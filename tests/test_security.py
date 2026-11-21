"""Tests for production settings and security headers."""

import pytest

from app import create_app
from app.config import ProductionConfig

UNSAFE_KEY = "dev-only-change-me"


def test_production_refuses_the_default_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", UNSAFE_KEY)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_production_starts_with_a_real_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 40)

    app = create_app("production")

    assert app.config["SECRET_KEY"] == "x" * 40
    assert app.debug is False


def test_production_cookies_are_locked_down():
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True
    assert ProductionConfig.SESSION_COOKIE_SAMESITE == "Lax"


def test_security_headers_are_sent(client, app):
    response = client.get("/login")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_api_errors_also_get_security_headers(client, app):
    response = client.get("/api/tickets")

    assert response.status_code == 401
    assert response.headers["X-Content-Type-Options"] == "nosniff"
"""Shared test setup. pytest loads this file automatically."""

import base64

import pytest

from app import create_app
from app.extensions import db
from app.models import Ticket, User

PASSWORD = "password123"  # every test account uses this fake password


@pytest.fixture
def app():
    """A fresh app with an empty in-memory database for every single test."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A fake browser that can send requests to the app."""
    return app.test_client()


def _make_user(name, email, role):
    user = User(name=name, email=email, role=role)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def user(app):
    return _make_user("Una User", "user@test.com", "user")


@pytest.fixture
def other_user(app):
    return _make_user("Ben User", "ben@test.com", "user")


@pytest.fixture
def agent(app):
    return _make_user("Amy Agent", "agent@test.com", "agent")


@pytest.fixture
def admin(app):
    return _make_user("Adam Admin", "admin@test.com", "admin")


@pytest.fixture
def make_ticket(app):
    """Returns a function that creates a ticket. Tests can override any detail."""

    def _make(
        requester,
        title="Printer is broken",
        description="The printer on floor 2 will not print.",
        category="Hardware",
        priority="Medium",
        status="Open",
        assignee=None,
        resolution_note=None,
    ):
        ticket = Ticket(
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            requester=requester,
            assignee=assignee,
            resolution_note=resolution_note,
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket

    return _make


@pytest.fixture
def login(client):
    """Returns a function that logs the fake browser in through the real login form."""

    def _login(email, password=PASSWORD):
        return client.post("/login", data={"email": email, "password": password})

    return _login


@pytest.fixture
def basic_auth():
    """Returns a function that builds the Basic Auth header the REST API expects."""

    def _basic_auth(email, password=PASSWORD):
        token = base64.b64encode(f"{email}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    return _basic_auth


@pytest.fixture
def reload():
    """Returns a function that re-reads a row from the database.

    Requests run in their own database session, so the objects we created in
    the test can be out of date. This forces a fresh read.
    """

    def _reload(model, primary_key):
        db.session.expire_all()
        return db.session.get(model, primary_key)

    return _reload
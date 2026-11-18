from app.models import User


def register(client, **overrides):
    """Send the registration form. Tests can change any field."""
    data = {
        "name": "New Person",
        "email": "newperson@example.com",
        "password": "password123",
        "confirm_password": "password123",
    }
    data.update(overrides)
    return client.post("/register", data=data)


def page_text(response):
    return response.get_data(as_text=True)


def test_register_creates_regular_user(client, app):
    response = register(client)

    assert response.status_code == 302  # redirected to the login page
    assert "/login" in response.headers["Location"]
    created = User.query.filter_by(email="newperson@example.com").one()
    assert created.role == "user"


def test_register_ignores_role_field(client, app):
    """Someone editing the HTML to add role=admin must not become an admin."""
    register(client, role="admin")

    created = User.query.filter_by(email="newperson@example.com").one()
    assert created.role == "user"


def test_register_duplicate_email_rejected(client, user):
    # Same email as the `user` fixture, typed in capitals
    response = register(client, email="USER@test.com")

    assert response.status_code == 200
    assert "That email is already registered." in page_text(response)
    assert User.query.filter_by(email="user@test.com").count() == 1


def test_register_password_mismatch(client, app):
    response = register(client, confirm_password="different123")

    assert response.status_code == 200
    assert "Passwords do not match." in page_text(response)
    assert User.query.count() == 0


def test_register_short_password(client, app):
    response = register(client, password="short", confirm_password="short")

    assert response.status_code == 200
    assert "Password must be 8 to 128 characters." in page_text(response)
    assert User.query.count() == 0


def test_register_empty_form_shows_errors(client, app):
    response = client.post("/register", data={})

    assert response.status_code == 200
    text = page_text(response)
    assert "Please enter your name." in text
    assert "Please enter your email." in text


def test_login_success(client, user, login):
    response = login(user.email)

    assert response.status_code == 302
    assert client.get("/").status_code == 200  # the dashboard now opens


def test_login_wrong_password(client, user, login):
    response = login(user.email, password="wrong-password")

    assert response.status_code == 200
    assert "Incorrect email or password." in page_text(response)
    assert client.get("/").status_code == 302  # still logged out


def test_login_unknown_email_gives_same_message(client, app, login):
    """The error must not reveal whether an email is registered."""
    response = login("nobody@example.com")

    assert response.status_code == 200
    assert "Incorrect email or password." in page_text(response)


def test_protected_page_redirects_anonymous(client, app):
    response = client.get("/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logout(client, user, login):
    login(user.email)
    assert client.get("/").status_code == 200

    response = client.post("/logout")

    assert response.status_code == 302
    assert client.get("/").status_code == 302  # logged out again


def test_login_blocks_open_redirect(client, user):
    """A crafted ?next= link must never send people to another website."""
    response = client.post(
        "/login?next=https://evil.example.com",
        data={"email": user.email, "password": "password123"},
    )

    assert response.status_code == 302
    assert "evil.example.com" not in response.headers["Location"]


def test_login_allows_safe_next(client, user):
    response = client.post(
        "/login?next=/tickets/",
        data={"email": user.email, "password": "password123"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tickets/")


def test_password_is_hashed(user):
    assert user.password_hash != "password123"
    assert user.check_password("password123") is True
    assert user.check_password("wrong") is False
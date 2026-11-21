"""Tests for the auth page polish, demo box, empty states, and dark theme."""

from app.config import DevelopmentConfig, TestingConfig


def page_text(response):
    return response.get_data(as_text=True)


# ---------- theme ----------
def test_login_page_has_theme_toggle_and_early_theme_script(client, app):
    text = page_text(client.get("/login"))

    assert "data-theme-toggle" in text
    assert "helpticketer-theme" in text
    # The theme script must run before the stylesheet loads, or the page flashes
    assert text.index("helpticketer-theme") < text.index("styles.css")


def test_register_page_has_theme_toggle(client, app):
    assert "data-theme-toggle" in page_text(client.get("/register"))


def test_dashboard_has_theme_toggle(client, user, login):
    login(user.email)

    assert "data-theme-toggle" in page_text(client.get("/"))


def test_dark_theme_and_scripts_are_served(client, app):
    css = client.get("/static/css/styles.css")

    assert '[data-theme="dark"]' in css.get_data(as_text=True)
    assert client.get("/static/js/theme.js").status_code == 200
    assert client.get("/static/js/auth.js").status_code == 200


# ---------- demo accounts box ----------
def test_demo_accounts_hidden_by_default(client, app):
    text = page_text(client.get("/login"))

    assert 'data-testid="demo-accounts"' not in text
    assert "Demo1234!" not in text


def test_demo_accounts_shown_when_enabled(client, app):
    app.config["SHOW_DEMO_LOGINS"] = True

    text = page_text(client.get("/login"))

    assert 'data-testid="demo-accounts"' in text
    for email in ("user@demo.com", "agent@demo.com", "admin@demo.com"):
        assert email in text
    assert "sam@demo.com" not in text  # only one account per role is shown


def test_demo_fill_buttons_have_accessible_names(client, app):
    app.config["SHOW_DEMO_LOGINS"] = True

    text = page_text(client.get("/login"))

    for role in ("user", "agent", "admin"):
        assert f'aria-label="Fill in the {role} demo account"' in text


def test_demo_accounts_not_on_register_page(client, app):
    app.config["SHOW_DEMO_LOGINS"] = True

    assert 'data-testid="demo-accounts"' not in page_text(client.get("/register"))


def test_config_flags_for_demo_box():
    assert DevelopmentConfig.SHOW_DEMO_LOGINS is True
    assert TestingConfig.SHOW_DEMO_LOGINS is False


# ---------- auth pages keep their test ids ----------
def test_auth_pages_keep_form_test_ids(client, app):
    login_text = page_text(client.get("/login"))
    register_text = page_text(client.get("/register"))

    for testid in ("login-form", "login-email", "login-password", "login-submit"):
        assert f'data-testid="{testid}"' in login_text
    for testid in ("register-form", "register-name", "register-email",
                   "register-password", "register-confirm-password", "register-submit"):
        assert f'data-testid="{testid}"' in register_text


# ---------- empty states ----------
def test_new_user_sees_friendly_empty_state(client, user, login):
    login(user.email)

    text = page_text(client.get("/tickets/"))

    assert 'data-testid="no-tickets"' in text
    assert 'class="empty"' in text
    assert "Submit your first ticket" in text


def test_list_with_tickets_has_no_empty_state(client, user, make_ticket, login):
    make_ticket(requester=user)
    login(user.email)

    assert 'class="empty"' not in page_text(client.get("/tickets/"))
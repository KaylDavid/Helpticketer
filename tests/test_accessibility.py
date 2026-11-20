"""Accessibility checks that can be automated (HTML structure, not looks)."""

import re
from collections import Counter

import pytest

PUBLIC_PAGES = ["/login", "/register"]
SIGNED_IN_PAGES = ["/", "/tickets/", "/tickets/new"]


def page_text(response):
    return response.get_data(as_text=True)


def check_inputs_have_labels(text):
    """Every visible form control needs a <label for="..."> that points at it."""
    for tag, attrs in re.findall(r"<(input|select|textarea)\b([^>]*)>", text):
        if 'type="hidden"' in attrs or 'type="submit"' in attrs:
            continue
        match = re.search(r'\bid="([^"]+)"', attrs)
        assert match, f"A form control has no id, so it cannot have a label: <{tag}{attrs}>"
        assert f'for="{match.group(1)}"' in text, f"No label for #{match.group(1)}"


# ---------- page structure ----------
@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_have_lang_skip_link_and_main(client, app, path):
    text = page_text(client.get(path))

    assert '<html lang="en">' in text
    assert 'class="skip-link" href="#main"' in text
    assert 'id="main"' in text


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_have_exactly_one_h1(client, app, path):
    assert page_text(client.get(path)).count("<h1") == 1


@pytest.mark.parametrize("path", SIGNED_IN_PAGES)
def test_signed_in_pages_have_exactly_one_h1(client, user, login, path):
    login(user.email)

    assert page_text(client.get(path)).count("<h1") == 1


# ---------- labels ----------
@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_form_controls_have_labels(client, app, path):
    check_inputs_have_labels(page_text(client.get(path)))


@pytest.mark.parametrize("path", SIGNED_IN_PAGES)
def test_signed_in_form_controls_have_labels(client, user, login, path):
    login(user.email)

    check_inputs_have_labels(page_text(client.get(path)))


def test_staff_ticket_page_controls_have_labels(client, user, agent, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(agent.email)

    check_inputs_have_labels(page_text(client.get(f"/tickets/{ticket.id}")))


def test_staff_ticket_page_has_no_duplicate_ids(client, user, agent, make_ticket, login):
    """HTML requires every id to be unique on a page."""
    ticket = make_ticket(requester=user)
    login(agent.email)

    text = page_text(client.get(f"/tickets/{ticket.id}"))

    ids = re.findall(r'\bid="([^"]+)"', text)
    duplicates = [name for name, count in Counter(ids).items() if count > 1]
    assert duplicates == []


# ---------- messages ----------
def test_error_message_uses_alert_role(client, user, login):
    """Errors are announced right away by screen readers (role=alert)."""
    text = page_text(login(user.email, "wrong-password"))

    assert 'flash-error" role="alert"' in text


def test_success_message_uses_status_role(client, app):
    response = client.post(
        "/register",
        data={
            "name": "New Person",
            "email": "newperson@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    assert 'flash-success" role="status"' in page_text(response)


def test_invalid_fields_are_linked_to_their_errors(client, app):
    text = page_text(client.post("/register", data={}))

    assert 'aria-invalid="true"' in text
    assert 'aria-describedby="name-errors"' in text
    assert 'id="name-errors"' in text


def test_valid_fields_are_not_marked_invalid(client, app):
    assert "aria-invalid" not in page_text(client.get("/register"))
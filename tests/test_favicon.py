"""Tests for the favicon and the page head."""

import pytest


def page_text(response):
    return response.get_data(as_text=True)


def test_favicon_svg_is_served(client, app):
    response = client.get("/static/favicon.svg")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert "#c8472a" in response.get_data(as_text=True)  # the logo's coral
    response.close()


def test_favicon_ico_redirects_to_the_svg_without_login(client, app):
    """Browsers ask for /favicon.ico on their own, before anyone logs in."""
    response = client.get("/favicon.ico")

    assert response.status_code in (301, 302)
    assert response.headers["Location"].endswith("/static/favicon.svg")


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_public_pages_link_the_icon(client, app, path):
    text = page_text(client.get(path))

    assert 'rel="icon"' in text
    assert "favicon.svg" in text


def test_signed_in_page_links_the_icon(client, user, login):
    login(user.email)

    assert 'rel="icon"' in page_text(client.get("/"))


def test_pages_have_a_meta_description(client, app):
    assert 'name="description"' in page_text(client.get("/login"))
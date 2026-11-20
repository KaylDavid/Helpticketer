"""Tests for the quick-filter API options and the dashboard chips."""

import pytest


def titles(response):
    return {t["title"] for t in response.get_json()["tickets"]}


# ---------- assigned=me ----------
def test_assigned_me_returns_only_my_tickets(client, user, agent, admin, make_ticket, basic_auth):
    make_ticket(requester=user, title="Mine", assignee=agent)
    make_ticket(requester=user, title="Admins", assignee=admin)
    make_ticket(requester=user, title="Nobody")

    response = client.get("/api/tickets?assigned=me", headers=basic_auth(agent.email))

    assert response.status_code == 200
    assert titles(response) == {"Mine"}


def test_assigned_me_for_regular_user_is_empty(client, user, agent, make_ticket, basic_auth):
    """Regular users can never be assignees, so nothing is assigned to them."""
    make_ticket(requester=user, title="Mine", assignee=agent)

    response = client.get("/api/tickets?assigned=me", headers=basic_auth(user.email))

    assert response.status_code == 200
    assert response.get_json()["total"] == 0


def test_assigned_only_accepts_me(client, agent, basic_auth):
    response = client.get("/api/tickets?assigned=banana", headers=basic_auth(agent.email))

    assert response.status_code == 422
    assert "assigned" in response.get_json()["fields"]


# ---------- unassigned=true ----------
def test_unassigned_means_active_tickets_with_nobody_assigned(
    client, user, agent, make_ticket, basic_auth
):
    make_ticket(requester=user, title="Waiting open", status="Open")
    make_ticket(requester=user, title="Waiting progress", status="In Progress")
    make_ticket(requester=user, title="Resolved none", status="Resolved")
    make_ticket(requester=user, title="Closed none", status="Closed")
    make_ticket(requester=user, title="Taken", status="Open", assignee=agent)

    response = client.get("/api/tickets?unassigned=true", headers=basic_auth(agent.email))

    assert response.status_code == 200
    assert titles(response) == {"Waiting open", "Waiting progress"}


@pytest.mark.parametrize("value", ["false", "yes", ""])
def test_unassigned_only_accepts_true(client, agent, basic_auth, value):
    response = client.get(f"/api/tickets?unassigned={value}", headers=basic_auth(agent.email))

    assert response.status_code == 422
    assert "unassigned" in response.get_json()["fields"]


def test_assigned_and_unassigned_together_is_rejected(client, agent, basic_auth):
    response = client.get(
        "/api/tickets?assigned=me&unassigned=true", headers=basic_auth(agent.email)
    )

    assert response.status_code == 422
    assert "unassigned" in response.get_json()["fields"]


def test_unassigned_combines_with_other_filters(client, user, agent, make_ticket, basic_auth):
    make_ticket(requester=user, title="Urgent waiting", priority="Urgent")
    make_ticket(requester=user, title="Low waiting", priority="Low")

    response = client.get(
        "/api/tickets?unassigned=true&priority=Urgent", headers=basic_auth(agent.email)
    )

    assert titles(response) == {"Urgent waiting"}


# ---------- statistics ----------
def test_stats_include_assigned_to_me(client, user, agent, admin, make_ticket, basic_auth):
    make_ticket(requester=user, assignee=agent)
    make_ticket(requester=user, assignee=agent, status="In Progress")
    make_ticket(requester=user, assignee=admin)

    response = client.get("/api/stats", headers=basic_auth(agent.email))

    assert response.get_json()["stats"]["assigned_to_me"] == 2


# ---------- dashboard chips ----------
def test_staff_dashboard_has_staff_chips(client, agent, login):
    login(agent.email)

    text = client.get("/").get_data(as_text=True)

    assert 'data-chip="mine"' in text
    assert 'data-chip="unassigned"' in text
    assert 'data-chip="urgent"' in text


def test_user_dashboard_has_status_chips_only(client, user, login):
    login(user.email)

    text = client.get("/").get_data(as_text=True)

    assert 'data-chip="open"' in text
    assert 'data-chip="resolved"' in text
    assert 'data-chip="mine"' not in text
    assert 'data-chip="unassigned"' not in text
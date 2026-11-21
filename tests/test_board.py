"""Tests for the dashboard Board view and the API requests it relies on."""

from app.models import STATUSES


def page_text(response):
    return response.get_data(as_text=True)


# ---------- the page structure ----------
def test_agent_dashboard_has_view_toggle(client, agent, login):
    login(agent.email)

    text = page_text(client.get("/"))

    assert 'data-testid="view-table"' in text
    assert 'data-testid="view-board"' in text


def test_user_dashboard_has_view_toggle(client, user, login):
    login(user.email)

    text = page_text(client.get("/"))

    assert 'data-testid="view-table"' in text
    assert 'data-testid="view-board"' in text


def test_board_has_four_columns_in_workflow_order(client, user, login):
    login(user.email)

    text = page_text(client.get("/"))

    positions = [text.index(f'data-col="{status}"') for status in STATUSES]
    assert positions == sorted(positions)


def test_board_is_hidden_until_chosen(client, user, login):
    """Without JavaScript the table stays the default view."""
    login(user.email)

    text = page_text(client.get("/"))

    assert 'id="board-view" hidden' in text
    assert 'id="table-view" hidden' not in text


# ---------- the requests the board makes ----------
def test_board_columns_add_up_to_the_total(client, user, agent, make_ticket, basic_auth):
    make_ticket(requester=user, status="Open")
    make_ticket(requester=user, status="Open")
    make_ticket(requester=user, status="In Progress")
    make_ticket(requester=user, status="Resolved", resolution_note="Done.")
    make_ticket(requester=user, status="Closed", resolution_note="Done.")
    headers = basic_auth(agent.email)

    total = client.get("/api/tickets", headers=headers).get_json()["total"]
    column_totals = [
        client.get(f"/api/tickets?status={status}&per_page=50", headers=headers).get_json()["total"]
        for status in STATUSES
    ]

    assert total == 5
    assert sum(column_totals) == total


def test_board_requests_only_see_own_tickets_for_users(
    client, user, other_user, make_ticket, basic_auth
):
    make_ticket(requester=user, status="Open", title="Mine")
    make_ticket(requester=other_user, status="Open", title="Not mine")

    response = client.get("/api/tickets?status=Open&per_page=50", headers=basic_auth(user.email))

    data = response.get_json()
    assert data["total"] == 1
    assert data["tickets"][0]["title"] == "Mine"
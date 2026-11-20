"""Tests for the REST API (everything under /api/)."""

import pytest

from app.models import Ticket


def new_ticket_data(**overrides):
    """A valid JSON body for creating a ticket. Tests can change any field."""
    data = {
        "title": "API test ticket",
        "description": "Created from an automated test.",
        "category": "Software",
        "priority": "High",
    }
    data.update(overrides)
    return data


# =====================================================================
# Authentication
# =====================================================================
def test_api_requires_authentication(client, app):
    response = client.get("/api/tickets")

    assert response.status_code == 401
    assert response.is_json
    assert "Authentication required" in response.get_json()["error"]
    assert response.get_json()["fields"] == {}


def test_api_rejects_wrong_password(client, user, basic_auth):
    response = client.get("/api/tickets", headers=basic_auth(user.email, "wrong-password"))

    assert response.status_code == 401


def test_api_rejects_unknown_email(client, app, basic_auth):
    response = client.get("/api/tickets", headers=basic_auth("nobody@example.com"))

    assert response.status_code == 401


def test_api_me_returns_the_caller(client, agent, basic_auth):
    response = client.get("/api/me", headers=basic_auth(agent.email))

    assert response.status_code == 200
    data = response.get_json()["user"]
    assert data["email"] == agent.email
    assert data["role"] == "agent"


def test_api_rejects_non_basic_auth_scheme(client, user):
    response = client.get("/api/tickets", headers={"Authorization": "Bearer abc123"})

    assert response.status_code == 401


def test_session_cookie_works_for_get(client, user, login):
    login(user.email)

    assert client.get("/api/tickets").status_code == 200


def test_session_cookie_is_rejected_for_post(client, user, login):
    """A browser cookie must not be able to change data through the API."""
    login(user.email)

    response = client.post("/api/tickets", json=new_ticket_data())

    assert response.status_code == 401
    assert Ticket.query.count() == 0


def test_wrong_basic_auth_does_not_fall_back_to_cookie(client, user, login, basic_auth):
    login(user.email)

    response = client.get("/api/tickets", headers=basic_auth(user.email, "wrong-password"))

    assert response.status_code == 401


def test_ticket_json_does_not_leak_emails_or_hashes(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user, assignee=agent)

    response = client.get(f"/api/tickets/{ticket.id}", headers=basic_auth(agent.email))
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert user.email not in text
    assert agent.email not in text
    assert "password" not in text
    assert "hash" not in text


# =====================================================================
# Listing, filtering, searching, paging
# =====================================================================
def test_user_lists_only_own_tickets(client, user, other_user, make_ticket, basic_auth):
    make_ticket(requester=user, title="Una ticket")
    make_ticket(requester=other_user, title="Ben ticket")

    response = client.get("/api/tickets", headers=basic_auth(user.email))

    data = response.get_json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["tickets"][0]["title"] == "Una ticket"


def test_agent_lists_all_tickets(client, user, other_user, agent, make_ticket, basic_auth):
    make_ticket(requester=user)
    make_ticket(requester=other_user)

    response = client.get("/api/tickets", headers=basic_auth(agent.email))

    assert response.get_json()["total"] == 2


def test_filter_by_status(client, user, agent, make_ticket, basic_auth):
    make_ticket(requester=user, title="Open one", status="Open")
    make_ticket(requester=user, title="Closed one", status="Closed")

    response = client.get("/api/tickets?status=Closed", headers=basic_auth(agent.email))

    data = response.get_json()
    assert data["total"] == 1
    assert data["tickets"][0]["title"] == "Closed one"


def test_filters_combine(client, user, agent, make_ticket, basic_auth):
    make_ticket(requester=user, title="A", status="Open", priority="High", category="Network")
    make_ticket(requester=user, title="B", status="Open", priority="Low", category="Network")
    make_ticket(requester=user, title="C", status="Closed", priority="High", category="Network")
    make_ticket(requester=user, title="D", status="Open", priority="High", category="Hardware")

    response = client.get(
        "/api/tickets?status=Open&priority=High&category=Network",
        headers=basic_auth(agent.email),
    )

    data = response.get_json()
    assert data["total"] == 1
    assert data["tickets"][0]["title"] == "A"


def test_search_matches_title_and_description(client, user, agent, make_ticket, basic_auth):
    make_ticket(requester=user, title="Wi-Fi is down", description="Nothing connects at all.")
    make_ticket(requester=user, title="Printer jam", description="Paper is stuck inside.")
    make_ticket(requester=user, title="Cannot print", description="Maybe a WI-FI problem?")

    response = client.get("/api/tickets?q=wi-fi", headers=basic_auth(agent.email))

    titles = {t["title"] for t in response.get_json()["tickets"]}
    assert titles == {"Wi-Fi is down", "Cannot print"}  # search ignores capital letters


def test_search_treats_percent_sign_as_plain_text(client, user, agent, make_ticket, basic_auth):
    """In SQL, % means 'match anything'. A search for '%' must not match everything."""
    make_ticket(requester=user, title="Printer jam")
    make_ticket(requester=user, title="Cannot log in")

    response = client.get("/api/tickets?q=%25", headers=basic_auth(agent.email))  # %25 is '%'

    assert response.status_code == 200
    assert response.get_json()["total"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "status=Banana",
        "priority=Nope",
        "category=Nope",
        "page=abc",
        "page=0",
        "per_page=0",
        "per_page=51",
    ],
)
def test_invalid_query_values_return_422(client, agent, basic_auth, query):
    response = client.get(f"/api/tickets?{query}", headers=basic_auth(agent.email))

    assert response.status_code == 422
    field = query.split("=")[0]
    assert field in response.get_json()["fields"]


def test_pagination(client, user, agent, make_ticket, basic_auth):
    for number in range(3):
        make_ticket(requester=user, title=f"Ticket {number}")

    response = client.get("/api/tickets?per_page=2&page=2", headers=basic_auth(agent.email))

    data = response.get_json()
    assert len(data["tickets"]) == 1  # 3 tickets, 2 per page -> 1 left on page 2
    assert data["total"] == 3
    assert data["pages"] == 2
    assert data["page"] == 2
    assert data["per_page"] == 2


def test_page_beyond_the_end_is_empty_not_an_error(client, user, make_ticket, basic_auth):
    make_ticket(requester=user)

    response = client.get("/api/tickets?page=5", headers=basic_auth(user.email))

    data = response.get_json()
    assert response.status_code == 200
    assert data["tickets"] == []
    assert data["total"] == 1


def test_list_is_newest_first(client, user, make_ticket, basic_auth):
    first = make_ticket(requester=user, title="First")
    second = make_ticket(requester=user, title="Second")
    third = make_ticket(requester=user, title="Third")

    response = client.get("/api/tickets", headers=basic_auth(user.email))

    ids = [t["id"] for t in response.get_json()["tickets"]]
    assert ids == [third.id, second.id, first.id]


# =====================================================================
# Creating tickets
# =====================================================================
def test_create_ticket_success(client, user, basic_auth):
    response = client.post("/api/tickets", json=new_ticket_data(), headers=basic_auth(user.email))

    assert response.status_code == 201
    data = response.get_json()["ticket"]
    assert data["title"] == "API test ticket"
    assert data["requester"]["id"] == user.id
    assert data["status"] == "Open"
    assert data["assignee"] is None
    assert data["comments"] == []
    assert response.headers["Location"].endswith(f"/api/tickets/{data['id']}")
    assert Ticket.query.count() == 1


def test_create_ignores_fake_requester_and_status(client, user, other_user, basic_auth):
    """The server decides the requester and the starting status, never the request body."""
    response = client.post(
        "/api/tickets",
        json=new_ticket_data(requester_id=other_user.id, status="Closed"),
        headers=basic_auth(user.email),
    )

    data = response.get_json()["ticket"]
    assert response.status_code == 201
    assert data["requester"]["id"] == user.id
    assert data["status"] == "Open"


def test_create_priority_defaults_to_medium(client, user, basic_auth):
    body = new_ticket_data()
    del body["priority"]

    response = client.post("/api/tickets", json=body, headers=basic_auth(user.email))

    assert response.status_code == 201
    assert response.get_json()["ticket"]["priority"] == "Medium"


def test_create_empty_body_lists_every_problem(client, user, basic_auth):
    response = client.post("/api/tickets", json={}, headers=basic_auth(user.email))

    assert response.status_code == 422
    fields = response.get_json()["fields"]
    assert "title" in fields
    assert "description" in fields
    assert "category" in fields
    assert Ticket.query.count() == 0


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("title", "Hi"),
        ("description", "short"),
        ("category", "Banana"),
        ("priority", "Mega"),
        ("title", 12345),
    ],
)
def test_create_rejects_invalid_values(client, user, basic_auth, field, bad_value):
    response = client.post(
        "/api/tickets", json=new_ticket_data(**{field: bad_value}), headers=basic_auth(user.email)
    )

    assert response.status_code == 422
    assert field in response.get_json()["fields"]
    assert Ticket.query.count() == 0


def test_create_with_non_json_body_returns_400(client, user, basic_auth):
    response = client.post(
        "/api/tickets", data="this is not json", content_type="text/plain",
        headers=basic_auth(user.email),
    )

    assert response.status_code == 400
    assert "JSON object" in response.get_json()["error"]


def test_create_with_json_list_returns_400(client, user, basic_auth):
    response = client.post("/api/tickets", json=[1, 2, 3], headers=basic_auth(user.email))

    assert response.status_code == 400


# =====================================================================
# Reading one ticket
# =====================================================================
def test_get_own_ticket_includes_comments(client, user, make_ticket, basic_auth):
    ticket = make_ticket(requester=user, title="My ticket")

    response = client.get(f"/api/tickets/{ticket.id}", headers=basic_auth(user.email))

    data = response.get_json()["ticket"]
    assert response.status_code == 200
    assert data["title"] == "My ticket"
    assert data["comments"] == []


def test_get_someone_elses_ticket_is_404(client, user, other_user, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.get(f"/api/tickets/{ticket.id}", headers=basic_auth(other_user.email))

    assert response.status_code == 404  # 404, so the ticket's existence is not revealed


def test_staff_can_get_any_ticket(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.get(f"/api/tickets/{ticket.id}", headers=basic_auth(agent.email))

    assert response.status_code == 200


def test_get_missing_ticket_is_404(client, user, basic_auth):
    response = client.get("/api/tickets/9999", headers=basic_auth(user.email))

    assert response.status_code == 404
    assert response.get_json()["error"] == "Ticket not found."


# =====================================================================
# Comments
# =====================================================================
def test_post_comment_success(client, user, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    response = client.post(
        f"/api/tickets/{ticket.id}/comments",
        json={"body": "Posted from the API."},
        headers=basic_auth(user.email),
    )

    assert response.status_code == 201
    data = response.get_json()["comment"]
    assert data["body"] == "Posted from the API."
    assert data["author"]["id"] == user.id
    assert len(reload(Ticket, ticket.id).comments) == 1


@pytest.mark.parametrize("body", [{}, {"body": ""}, {"body": "   "}])
def test_post_empty_comment_returns_422(client, user, make_ticket, basic_auth, body):
    ticket = make_ticket(requester=user)

    response = client.post(
        f"/api/tickets/{ticket.id}/comments", json=body, headers=basic_auth(user.email)
    )

    assert response.status_code == 422
    assert "body" in response.get_json()["fields"]


def test_post_too_long_comment_returns_422(client, user, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.post(
        f"/api/tickets/{ticket.id}/comments",
        json={"body": "x" * 2001},
        headers=basic_auth(user.email),
    )

    assert response.status_code == 422


def test_post_comment_on_closed_ticket_returns_409(client, user, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user, status="Closed")

    response = client.post(
        f"/api/tickets/{ticket.id}/comments", json={"body": "Hello?"}, headers=basic_auth(user.email)
    )

    assert response.status_code == 409
    assert "closed" in response.get_json()["error"]
    assert len(reload(Ticket, ticket.id).comments) == 0


def test_post_comment_on_someone_elses_ticket_is_404(
    client, user, other_user, make_ticket, basic_auth, reload
):
    ticket = make_ticket(requester=user)

    response = client.post(
        f"/api/tickets/{ticket.id}/comments",
        json={"body": "I should not be here."},
        headers=basic_auth(other_user.email),
    )

    assert response.status_code == 404
    assert len(reload(Ticket, ticket.id).comments) == 0


def test_staff_can_comment_on_any_ticket(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.post(
        f"/api/tickets/{ticket.id}/comments",
        json={"body": "Looking into it."},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 201
    assert response.get_json()["comment"]["author"]["role"] == "agent"


# =====================================================================
# Changing status
# =====================================================================
def test_user_cannot_patch_status(client, user, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/status", json={"status": "Closed"}, headers=basic_auth(user.email)
    )

    assert response.status_code == 403
    assert reload(Ticket, ticket.id).status == "Open"


def test_anonymous_cannot_patch_status(client, user, make_ticket):
    ticket = make_ticket(requester=user)

    response = client.patch(f"/api/tickets/{ticket.id}/status", json={"status": "Closed"})

    assert response.status_code == 401


def test_agent_changes_status(client, user, agent, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/status",
        json={"status": "In Progress"},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 200
    assert response.get_json()["ticket"]["status"] == "In Progress"
    assert reload(Ticket, ticket.id).status == "In Progress"


def test_resolving_without_note_returns_409(client, user, agent, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user, status="In Progress")

    response = client.patch(
        f"/api/tickets/{ticket.id}/status",
        json={"status": "Resolved"},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 409
    assert "resolution note is required" in response.get_json()["error"]
    assert reload(Ticket, ticket.id).status == "In Progress"


def test_resolving_with_note_works(client, user, agent, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user, status="In Progress")

    response = client.patch(
        f"/api/tickets/{ticket.id}/status",
        json={"status": "Resolved", "resolution_note": "Fixed via API."},
        headers=basic_auth(agent.email),
    )

    data = response.get_json()["ticket"]
    assert response.status_code == 200
    assert data["status"] == "Resolved"
    assert data["resolution_note"] == "Fixed via API."


def test_closed_ticket_cannot_move_to_another_status(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user, status="Closed")

    response = client.patch(
        f"/api/tickets/{ticket.id}/status",
        json={"status": "In Progress"},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 409
    assert "cannot move" in response.get_json()["error"]


def test_unknown_status_value_returns_422(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/status", json={"status": "Banana"}, headers=basic_auth(agent.email)
    )

    assert response.status_code == 422
    assert "status" in response.get_json()["fields"]


def test_missing_status_returns_422(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/status", json={}, headers=basic_auth(agent.email)
    )

    assert response.status_code == 422
    assert "status" in response.get_json()["fields"]


def test_patch_status_on_missing_ticket_is_404(client, agent, basic_auth):
    response = client.patch(
        "/api/tickets/9999/status", json={"status": "Closed"}, headers=basic_auth(agent.email)
    )

    assert response.status_code == 404


# =====================================================================
# Assigning
# =====================================================================
def test_agent_assigns_ticket_to_self(client, user, agent, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": agent.id},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 200
    assert response.get_json()["ticket"]["assignee"]["id"] == agent.id
    assert reload(Ticket, ticket.id).assignee_id == agent.id


def test_cannot_assign_to_regular_user(client, user, other_user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": other_user.id},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 409
    assert "agent or admin" in response.get_json()["error"]


def test_unassign_with_null(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user, assignee=agent)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": None},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 200
    assert response.get_json()["ticket"]["assignee"] is None


def test_assign_to_unknown_user_returns_422(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": 9999},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 422
    assert "assignee_id" in response.get_json()["fields"]


@pytest.mark.parametrize("bad_value", ["1", True, 1.5])
def test_assign_rejects_wrong_types(client, user, agent, make_ticket, basic_auth, bad_value):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": bad_value},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 422
    assert "assignee_id" in response.get_json()["fields"]


def test_assign_requires_the_assignee_id_key(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee", json={}, headers=basic_auth(agent.email)
    )

    assert response.status_code == 422


def test_cannot_assign_closed_ticket(client, user, agent, make_ticket, basic_auth):
    ticket = make_ticket(requester=user, status="Closed")

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": agent.id},
        headers=basic_auth(agent.email),
    )

    assert response.status_code == 409


def test_user_cannot_assign(client, user, agent, make_ticket, basic_auth, reload):
    ticket = make_ticket(requester=user)

    response = client.patch(
        f"/api/tickets/{ticket.id}/assignee",
        json={"assignee_id": agent.id},
        headers=basic_auth(user.email),
    )

    assert response.status_code == 403
    assert reload(Ticket, ticket.id).assignee_id is None


# =====================================================================
# Dashboard statistics
# =====================================================================
def test_stats_for_staff_count_everything(client, user, agent, make_ticket, basic_auth):
    make_ticket(requester=user, status="Open", priority="High")  # unassigned, active
    make_ticket(requester=user, status="Open", priority="Low")  # unassigned, active
    make_ticket(requester=user, status="In Progress", priority="Medium", assignee=agent)
    make_ticket(requester=user, status="Resolved", priority="Low", assignee=agent)
    make_ticket(requester=user, status="Closed", priority="Urgent", assignee=agent)
    make_ticket(requester=user, status="Closed", priority="Low")  # unassigned but Closed

    response = client.get("/api/stats", headers=basic_auth(agent.email))

    stats = response.get_json()["stats"]
    assert response.status_code == 200
    assert stats["total"] == 6
    assert stats["by_status"] == {"Open": 2, "In Progress": 1, "Resolved": 1, "Closed": 2}
    assert stats["by_priority"] == {"Low": 3, "Medium": 1, "High": 1, "Urgent": 1}
    assert stats["unassigned"] == 2  # only Open / In Progress tickets with nobody assigned


def test_stats_for_user_count_only_own_tickets(client, user, other_user, make_ticket, basic_auth):
    make_ticket(requester=user)
    make_ticket(requester=other_user)
    make_ticket(requester=other_user)

    response = client.get("/api/stats", headers=basic_auth(user.email))

    assert response.get_json()["stats"]["total"] == 1


def test_stats_require_authentication(client, app):
    assert client.get("/api/stats").status_code == 401


def test_stats_with_no_tickets_are_all_zero(client, agent, basic_auth):
    response = client.get("/api/stats", headers=basic_auth(agent.email))

    stats = response.get_json()["stats"]
    assert stats["total"] == 0
    assert stats["unassigned"] == 0
    assert stats["by_status"] == {"Open": 0, "In Progress": 0, "Resolved": 0, "Closed": 0}
    assert stats["by_priority"] == {"Low": 0, "Medium": 0, "High": 0, "Urgent": 0}


# =====================================================================
# Errors look the same everywhere
# =====================================================================
def test_unknown_api_url_returns_json_404(client, app):
    response = client.get("/api/nonsense")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "Not found."


def test_wrong_http_method_returns_json_405(client, user, basic_auth):
    response = client.delete("/api/tickets/1", headers=basic_auth(user.email))

    assert response.status_code == 405
    assert response.is_json
    assert response.get_json()["error"] == "Method not allowed."


def test_all_api_errors_share_one_shape(client, user, basic_auth):
    headers = basic_auth(user.email)
    responses = [
        client.get("/api/tickets"),  # 401
        client.get("/api/tickets/9999", headers=headers),  # 404
        client.post("/api/tickets", json={}, headers=headers),  # 422
        client.post("/api/tickets", data="x", content_type="text/plain", headers=headers),  # 400
        client.delete("/api/tickets/1", headers=headers),  # 405
    ]

    assert [r.status_code for r in responses] == [401, 404, 422, 400, 405]
    for response in responses:
        assert set(response.get_json().keys()) == {"error", "fields"}
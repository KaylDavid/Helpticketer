from app.extensions import db
from app.models import Ticket
from app.permissions import can_view_ticket


def page_text(response):
    return response.get_data(as_text=True)


# ---------- who may see which ticket ----------
def test_can_view_ticket_rules(user, other_user, agent, admin, make_ticket):
    ticket = make_ticket(requester=user)

    assert can_view_ticket(user, ticket) is True  # the owner
    assert can_view_ticket(other_user, ticket) is False  # another regular user
    assert can_view_ticket(agent, ticket) is True  # staff see everything
    assert can_view_ticket(admin, ticket) is True


def test_user_list_shows_only_own_tickets(client, user, other_user, make_ticket, login):
    make_ticket(requester=user, title="Una printer problem")
    make_ticket(requester=other_user, title="Ben VPN problem")
    login(user.email)

    text = page_text(client.get("/tickets/"))

    assert "Una printer problem" in text
    assert "Ben VPN problem" not in text


def test_staff_list_shows_all_tickets(client, user, other_user, agent, make_ticket, login):
    make_ticket(requester=user, title="Una printer problem")
    make_ticket(requester=other_user, title="Ben VPN problem")
    login(agent.email)

    text = page_text(client.get("/tickets/"))

    assert "Una printer problem" in text
    assert "Ben VPN problem" in text


def test_user_cannot_open_someone_elses_ticket(client, user, other_user, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(other_user.email)

    # 404, not 403, so we never confirm that the ticket exists
    assert client.get(f"/tickets/{ticket.id}").status_code == 404


def test_missing_ticket_is_404(client, user, login):
    login(user.email)

    assert client.get("/tickets/9999").status_code == 404


def test_user_can_open_own_ticket(client, user, make_ticket, login):
    ticket = make_ticket(requester=user, title="My own ticket")
    login(user.email)

    response = client.get(f"/tickets/{ticket.id}")

    assert response.status_code == 200
    assert "My own ticket" in page_text(response)


def test_anonymous_cannot_open_ticket(client, user, make_ticket):
    ticket = make_ticket(requester=user)

    response = client.get(f"/tickets/{ticket.id}")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------- staff-only tools ----------
def test_user_does_not_see_staff_panel(client, user, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(user.email)

    text = page_text(client.get(f"/tickets/{ticket.id}"))

    assert 'data-testid="staff-panel"' not in text


def test_agent_sees_staff_panel(client, user, agent, make_ticket, login):
    ticket = make_ticket(requester=user)
    login(agent.email)

    text = page_text(client.get(f"/tickets/{ticket.id}"))

    assert 'data-testid="staff-panel"' in text


def test_user_cannot_assign_ticket(client, user, agent, make_ticket, login, reload):
    ticket = make_ticket(requester=user)
    login(user.email)

    # Hiding the form is not security, so a hand-made request must be refused too
    response = client.post(f"/tickets/{ticket.id}/assign", data={"assignee": agent.id})

    assert response.status_code == 403
    assert reload(Ticket, ticket.id).assignee_id is None


def test_user_cannot_change_status(client, user, make_ticket, login, reload):
    ticket = make_ticket(requester=user)
    login(user.email)

    response = client.post(f"/tickets/{ticket.id}/status", data={"status": "Closed"})

    assert response.status_code == 403
    assert reload(Ticket, ticket.id).status == "Open"


def test_agent_can_assign(client, user, agent, make_ticket, login, reload):
    ticket = make_ticket(requester=user)
    login(agent.email)

    response = client.post(f"/tickets/{ticket.id}/assign", data={"assignee": agent.id})

    assert response.status_code == 302
    assert reload(Ticket, ticket.id).assignee_id == agent.id


def test_cannot_assign_to_regular_user(client, user, other_user, agent, make_ticket, login, reload):
    ticket = make_ticket(requester=user)
    login(agent.email)

    response = client.post(f"/tickets/{ticket.id}/assign", data={"assignee": other_user.id})

    assert response.status_code == 200  # the form is shown again with an error
    assert reload(Ticket, ticket.id).assignee_id is None


def test_agent_can_change_status(client, user, agent, make_ticket, login, reload):
    ticket = make_ticket(requester=user)
    login(agent.email)

    response = client.post(f"/tickets/{ticket.id}/status", data={"status": "In Progress"})

    assert response.status_code == 302
    assert reload(Ticket, ticket.id).status == "In Progress"


def test_resolving_requires_note(client, user, agent, make_ticket, login, reload):
    ticket = make_ticket(requester=user, status="In Progress")
    login(agent.email)

    response = client.post(
        f"/tickets/{ticket.id}/status", data={"status": "Resolved", "resolution_note": ""}
    )

    assert response.status_code == 200
    assert "resolution note is required" in page_text(response)
    assert reload(Ticket, ticket.id).status == "In Progress"


def test_closed_ticket_rejects_comments(client, user, make_ticket, login, reload):
    ticket = make_ticket(requester=user, status="Closed")
    login(user.email)

    response = client.post(f"/tickets/{ticket.id}/comments", data={"body": "Hello?"})

    assert response.status_code == 302
    assert len(reload(Ticket, ticket.id).comments) == 0


def test_requester_is_set_by_server(client, user, other_user, login):
    """A fake requester_id in the form must be ignored."""
    login(user.email)

    response = client.post(
        "/tickets/new",
        data={
            "title": "Cannot log in",
            "description": "The login page shows an error message.",
            "category": "Account Access",
            "priority": "High",
            "requester_id": other_user.id,
        },
    )

    assert response.status_code == 302
    ticket = db.session.scalars(db.select(Ticket)).one()
    assert ticket.requester_id == user.id
    assert ticket.status == "Open"
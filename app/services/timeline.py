"""Builds the activity timeline shown on a ticket page."""

from datetime import timezone


def _naive_utc(moment):
    """SQLite gives back times without a timezone, Python makes them with one.
    Make them all the same kind so they can be sorted together."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _person(user):
    if user is None:
        return "System", None
    return user.name, user.role


def build_timeline(ticket):
    """Return one list of entries (oldest first) from the ticket, its events and comments."""
    name, role = _person(ticket.requester)
    items = [
        {
            "kind": "created",
            "when": _naive_utc(ticket.created_at),
            "actor_name": name,
            "actor_role": role,
            "text": "opened this ticket",
            "body": None,
        }
    ]

    for event in ticket.events:
        name, role = _person(event.actor)
        items.append(
            {
                "kind": event.kind,
                "when": _naive_utc(event.created_at),
                "actor_name": name,
                "actor_role": role,
                "text": event.detail,
                "body": None,
            }
        )

    for comment in ticket.comments:
        name, role = _person(comment.author)
        items.append(
            {
                "kind": "comment",
                "when": _naive_utc(comment.created_at),
                "actor_name": name,
                "actor_role": role,
                "text": "commented",
                "body": comment.body,
            }
        )

    items.sort(key=lambda item: item["when"])  # stable: ties keep the order above
    return items
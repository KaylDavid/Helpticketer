from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def roles_required(*roles):
    """Decorator: only let logged-in users with one of these roles open the route.

    - Not logged in  -> sent to the login page
    - Wrong role     -> 403 Forbidden
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        # login_required runs first, so anonymous visitors go to the login page
        return login_required(wrapped)

    return decorator


# Ready-made shortcuts we will reuse on many routes
staff_required = roles_required("agent", "admin")
admin_required = roles_required("admin")


def can_view_ticket(user, ticket):
    """Object-level rule: staff can see any ticket; a user only their own."""
    return user.is_staff or ticket.requester_id == user.id
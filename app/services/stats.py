from sqlalchemy import func

from ..extensions import db
from ..models import PRIORITIES, STATUSES
from .tickets import visible_tickets_query

# Tickets that still need work. "Unassigned" only matters for these.
ACTIVE_STATUSES = ("Open", "In Progress")


def _count_by(base, column_name, labels):
    """Count tickets per value of one column, with 0 for values that have none."""
    column = base.c[column_name]
    rows = db.session.execute(db.select(column, func.count()).group_by(column)).all()
    counts = {value: count for value, count in rows}
    return {label: counts.get(label, 0) for label in labels}


def ticket_stats(user):
    """Numbers for the dashboard, counting only tickets this user may see."""
    # Reuse the visibility rule from Step 6 (order_by(None) removes sorting we don't need)
    base = visible_tickets_query(user).order_by(None).subquery()

    total = db.session.scalar(db.select(func.count()).select_from(base))
    unassigned_active = db.session.scalar(
        db.select(func.count())
        .select_from(base)
        .where(
            base.c.assignee_id.is_(None),
            base.c.status.in_(ACTIVE_STATUSES),
        )
    )
    assigned_to_me = db.session.scalar(
        db.select(func.count()).select_from(base).where(base.c.assignee_id == user.id)
    )

    return {
        "total": total,
        "by_status": _count_by(base, "status", STATUSES),
        "by_priority": _count_by(base, "priority", PRIORITIES),
        "unassigned": unassigned_active,
        "assigned_to_me": assigned_to_me,
    }
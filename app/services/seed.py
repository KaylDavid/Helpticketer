"""Fake demo data. Everything here is made up. Never put real data in this file."""

import random
from datetime import timedelta

from sqlalchemy import func

from ..extensions import db
from ..models import Comment, Ticket, User, utcnow

DEMO_PASSWORD = "Demo1234!"

# (name, email, role)
DEMO_USERS = [
    ("Dana Demo", "user@demo.com", "user"),
    ("Alex Agent", "agent@demo.com", "agent"),
    ("Ada Admin", "admin@demo.com", "admin"),
    ("Sam Support", "sam@demo.com", "agent"),
    ("Mia Santos", "mia@demo.com", "user"),
    ("Leo Reyes", "leo@demo.com", "user"),
    ("Nina Cruz", "nina@demo.com", "user"),
]

# (title, description, category, priority, status)
DEMO_TICKETS = [
    # ---- Open (10) ----
    ("Cannot connect to office Wi-Fi", "My laptop does not see the office network since this morning.", "Network", "High", "Open"),
    ("Laptop will not turn on", "The laptop shows no lights at all, even when plugged in.", "Hardware", "Urgent", "Open"),
    ("Request access to shared drive", "I need access to the Finance shared drive for my new project.", "Account Access", "Medium", "Open"),
    ("Printer on 2nd floor offline", "The printer shows as offline and nobody can print.", "Hardware", "Low", "Open"),
    ("Outlook keeps asking for password", "Outlook asks for my password every few minutes.", "Software", "Medium", "Open"),
    ("VPN disconnects every few minutes", "Working from home, the VPN drops about every five minutes.", "Network", "High", "Open"),
    ("Need Zoom installed", "Please install Zoom on my work computer for client calls.", "Software", "Low", "Open"),
    ("Monitor flickering", "My second monitor flickers when I open spreadsheets.", "Hardware", "Medium", "Open"),
    ("Locked out after password change", "I changed my password and now my account is locked.", "Account Access", "Urgent", "Open"),
    ("Slow internet in meeting room", "Video calls freeze in meeting room B during the afternoon.", "Network", "Medium", "Open"),
    # ---- In Progress (8) ----
    ("Excel crashes on large file", "Excel closes by itself when I open the monthly report file.", "Software", "High", "In Progress"),
    ("New hire laptop setup", "A new teammate starts Monday and needs a laptop ready.", "Hardware", "Medium", "In Progress"),
    ("Shared mailbox missing", "The support shared mailbox disappeared from my Outlook.", "Account Access", "Medium", "In Progress"),
    ("Wi-Fi drops in warehouse", "The signal keeps dropping near the loading area.", "Network", "High", "In Progress"),
    ("Keyboard keys not working", "The E and R keys on my keyboard do not respond.", "Hardware", "Low", "In Progress"),
    ("Antivirus popup warnings", "A security popup appears every time I start my computer.", "Software", "Urgent", "In Progress"),
    ("Cannot access HR portal", "The HR portal says my account has no permission.", "Account Access", "High", "In Progress"),
    ("Webcam not detected", "My computer cannot find the webcam during meetings.", "Hardware", "Medium", "In Progress"),
    # ---- Resolved (7) ----
    ("Forgot my password", "I cannot remember my password and need a reset.", "Account Access", "Medium", "Resolved"),
    ("Software license expired", "The design software says my license has expired.", "Software", "High", "Resolved"),
    ("Mouse not responding", "The wireless mouse stopped moving the cursor.", "Hardware", "Low", "Resolved"),
    ("Cannot print to network printer", "Print jobs stay in the queue and never print.", "Network", "Medium", "Resolved"),
    ("Teams notifications not showing", "I miss messages because Teams does not notify me.", "Software", "Low", "Resolved"),
    ("Email signature broken", "My email signature shows strange symbols.", "Software", "Low", "Resolved"),
    ("VPN setup on personal phone", "I would like to read work email on my phone safely.", "Network", "Medium", "Resolved"),
    # ---- Closed (5) ----
    ("Ethernet port dead at desk 14", "The network cable at desk 14 gives no connection.", "Network", "Medium", "Closed"),
    ("Request second monitor", "I would like a second monitor to work faster.", "Hardware", "Low", "Closed"),
    ("Old account still active", "A former teammate still has an active account.", "Account Access", "High", "Closed"),
    ("Browser homepage changed", "My browser homepage changed to a strange website.", "Software", "Urgent", "Closed"),
    ("Question about IT policy", "Can I use my personal USB drive at work?", "Other", "Low", "Closed"),
]

RESOLUTION_NOTES = {
    "Hardware": "Replaced the faulty part and tested it with the user.",
    "Software": "Reinstalled the application and confirmed it works.",
    "Network": "Reset the connection settings and confirmed a stable link.",
    "Account Access": "Updated the account permissions and confirmed access.",
    "Other": "Answered the question and shared the IT policy document.",
}

STAFF_COMMENTS = [
    "Thanks for reporting this. I am looking into it now.",
    "I have started checking the settings on my side.",
    "Could you tell me when this first started happening?",
    "I will update you as soon as I have more information.",
]

USER_REPLIES = [
    "It started yesterday afternoon. Thank you for the quick reply!",
    "Still happening this morning, nothing has changed.",
    "I tried restarting and it did not help.",
]


def seed_demo_data():
    """Add the fake users, tickets, and comments. Returns (users, tickets, comments)."""
    rng = random.Random(42)  # fixed seed -> the same demo data every time
    now = utcnow()

    users = []
    for name, email, role in DEMO_USERS:
        user = User(name=name, email=email, role=role)
        user.set_password(DEMO_PASSWORD)
        users.append(user)
    db.session.add_all(users)

    requesters = [u for u in users if u.role == "user"]
    agents = [u for u in users if u.role == "agent"]

    comment_count = 0
    open_seen = 0
    for index, (title, description, category, priority, status) in enumerate(DEMO_TICKETS):
        requester = requesters[index % len(requesters)]

        # Open tickets: every third one is assigned. All other statuses are assigned.
        if status == "Open":
            assignee = agents[open_seen % len(agents)] if open_seen % 3 == 0 else None
            open_seen += 1
        else:
            assignee = agents[index % len(agents)]

        created = now - timedelta(
            days=rng.randint(1, 30), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        if status == "Open" and assignee is None:
            updated = created
        else:
            updated = min(now, created + timedelta(hours=rng.randint(4, 72)))

        ticket = Ticket(
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            resolution_note=RESOLUTION_NOTES[category] if status in ("Resolved", "Closed") else None,
            requester=requester,
            assignee=assignee,
            created_at=created,
            updated_at=updated,
        )
        db.session.add(ticket)

        if assignee:
            first = created + timedelta(hours=1)
            db.session.add(
                Comment(ticket=ticket, author=assignee, body=rng.choice(STAFF_COMMENTS), created_at=first)
            )
            comment_count += 1
            if rng.random() < 0.6:
                db.session.add(
                    Comment(
                        ticket=ticket,
                        author=requester,
                        body=rng.choice(USER_REPLIES),
                        created_at=first + timedelta(hours=2),
                    )
                )
                comment_count += 1

    db.session.commit()
    return len(users), len(DEMO_TICKETS), comment_count


def reset_demo():
    """DELETE everything, rebuild the tables, and load the demo data."""
    db.drop_all()
    db.create_all()
    return seed_demo_data()


def seed_if_empty():
    """Load demo data only if there are no users yet. Returns True if it seeded."""
    db.create_all()
    if db.session.scalar(db.select(func.count()).select_from(User)) == 0:
        seed_demo_data()
        return True
    return False
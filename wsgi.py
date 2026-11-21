import os

from app import create_app

app = create_app()

# On a demo host the database starts empty after every restart.
# AUTO_SEED_DEMO=1 loads the fake demo data, but only if there are no users yet.
if os.environ.get("AUTO_SEED_DEMO") == "1":
    with app.app_context():
        from app.services.seed import seed_if_empty

        seed_if_empty()
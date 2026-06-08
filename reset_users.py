"""Delete all users and related data for a clean start."""
from app import create_app, db
from app.models import User, ActivityLog

app = create_app()
with app.app_context():
    # Delete in reverse FK order
    ac = ActivityLog.query.delete()
    uc = User.query.delete()
    db.session.commit()
    print(f"Deleted {uc} users and {ac} activity logs.")
    print("Database is clean. Register a new account at /auth/register")

"""Check supplier accounts and test login credentials."""
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    print("=== ALL USERS ===")
    users = User.query.all()
    if not users:
        print("No users found in database!")
    for u in users:
        print(f"  ID={u.id} | username={u.username} | email={u.email}")
        print(f"      role={u.role!r} | is_deleted={u.is_deleted} | is_locked={u.is_locked}")
        print(f"      failed_attempts={u.failed_login_attempts} | locked_until={u.locked_until}")

    print()
    print("=== SUPPLIERS ONLY ===")
    suppliers = User.query.filter_by(role='supplier').all()
    if not suppliers:
        print("NO SUPPLIERS FOUND. This is why login fails!")
        print("You need to register a supplier account first.")
    for s in suppliers:
        print(f"  ID={s.id} | {s.username} | {s.email}")
        print(f"      is_deleted={s.is_deleted} | is_locked={s.is_locked} | attempts={s.failed_login_attempts}")
        if s.is_deleted:
            print(f"      ⚠ This account is SOFT-DELETED! Undelete it in admin DB.")
        if s.is_locked:
            print(f"      ⚠ This account is LOCKED! Unlock it.")

"""Fix admin login issues - unlock accounts, verify passwords, and display working credentials."""
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    print("=" * 60)
    print("  ADMIN LOGIN FIX - DIAGNOSTIC REPORT")
    print("=" * 60)

    admins = User.query.filter(User.role.in_(['admin', 'user'])).all()
    if not admins:
        print("\n  No admin/user accounts found!")
    else:
        for u in admins:
            print(f"\n  Account: {u.email}")
            print(f"  Username: {u.username}")
            print(f"  Role: {u.role}")
            print(f"  Locked: {u.is_locked} (attempts: {u.failed_login_attempts})")
            print(f"  Deleted: {u.is_deleted}")

            # Check known passwords
            known_pws = ['Fav123bright@?', 'BrightFav123@?']
            for pw in known_pws:
                if u.check_password(pw):
                    print(f"  >>> CORRECT PASSWORD: {pw}")

            # Reset lockout
            if u.is_locked:
                u.reset_failed_logins()
                print(f"  ** UNLOCKED ACCOUNT (was locked) **")

            # Reset failed attempts regardless
            if u.failed_login_attempts > 0:
                u.reset_failed_logins()
                print(f"  ** RESET {u.failed_login_attempts} failed attempts **")

    # Summary
    print("\n" + "=" * 60)
    print("  WORKING ADMIN CREDENTIALS:")
    for u in User.query.filter(User.role.in_(['admin', 'user'])).all():
        for pw in ['Fav123bright@?', 'BrightFav123@?']:
            if u.check_password(pw):
                print(f"    URL: http://localhost:5000/auth/login/admin")
                print(f"    Email: {u.email}")
                print(f"    Password: {pw}")
                print()
                break
    print("=" * 60)

"""Unlock and check admin accounts."""
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admin1 = User.query.filter_by(email='bright12@gmail.com').first()
    if admin1:
        admin1.reset_failed_logins()
        print(f"Unlocked bright12@gmail.com (ID={admin1.id})")
        print(f"  username={admin1.username}")
        print(f"  role={admin1.role}")
        for pw in ['BrightFav123@', 'admin123', 'password']:
            print(f"  check_password('{pw}') = {admin1.check_password(pw)}")

    admin2 = User.query.filter_by(email='brightfav12@gmail.com').first()
    if admin2:
        print(f"\nAdmin 2: brightfav12@gmail.com (ID={admin2.id})")
        print(f"  username={admin2.username}")
        print(f"  role={admin2.role}")
        for pw in ['BrightFav123@', 'admin123', 'password']:
            print(f"  check_password('{pw}') = {admin2.check_password(pw)}")

"""Check if a specific user exists."""
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    email = 'studykelly7@gmail.com'
    u = User.query.filter_by(email=email).first()
    if u:
        print(f"FOUND: ID={u.id} | username={u.username} | email={u.email}")
        print(f"  role={u.role} | is_deleted={u.is_deleted} | is_locked={u.is_locked}")
        print(f"  failed_attempts={u.failed_login_attempts} | locked_until={u.locked_until}")
        for pw in ['BrightFav123@', 'Kelly7@', 'password', 'studykelly7', 'Kelly123@']:
            print(f"  check_password('{pw}') = {u.check_password(pw)}")
    else:
        print(f"USER NOT FOUND: {email}")
        print("Searching for similar emails...")
        similar = User.query.filter(User.email.like('%kelly%')).all()
        for s in similar:
            print(f"  Similar: ID={s.id} | {s.email} | role={s.role}")

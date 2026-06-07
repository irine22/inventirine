"""Set known password on both admin accounts."""
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    u = User.query.filter_by(email='bright12@gmail.com').first()
    if u:
        u.set_password('BrightFav123@')
        db.session.commit()
        print(f"Password set for {u.email} (ID={u.id})")
        print(f"  Verify: check_password('BrightFav123@') = {u.check_password('BrightFav123@')}")
    else:
        print("bright12@gmail.com not found")

    u2 = User.query.filter_by(email='brightfav12@gmail.com').first()
    if u2:
        u2.set_password('BrightFav123@')
        db.session.commit()
        print(f"Password set for {u2.email} (ID={u2.id})")
        print(f"  Verify: check_password('BrightFav123@') = {u2.check_password('BrightFav123@')}")

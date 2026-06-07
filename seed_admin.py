from app import create_app, db
from app.models import User

app = create_app()

def seed_admin():
    with app.app_context():
        db.create_all()
        # Check if user exists
        admin = User.query.filter_by(email='bright12@gmail.com').first()
        if not admin:
            admin = User(
                username='Bright Favor',
                email='brightfav12@gmail.com',
                role='admin'
            )
            # ⚠ Change this password immediately after first login
            admin.set_password('BrightFav123@')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully.")
        else:
            print("Admin user already exists.")

if __name__ == '__main__':
    seed_admin()

from app import create_app, db
from app.models import User
from sqlalchemy import text

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='bright12@gmail.com').first()
    if not user:
        user = User(username='admin_bright12', email='bright12@gmail.com', role='admin')
        user.set_password('Fav123bright@?')
        db.session.add(user)
        print("Created new admin user.")
    else:
        user.role = 'admin'
        user.set_password('Fav123bright@?')
        user.locked_until = None
        user.failed_login_attempts = 0
        print("Updated existing admin user.")
    
    try:
        db.session.execute(text('ALTER TABLE "order" ADD COLUMN destination VARCHAR(100);'))
        print("Added destination column to order table.")
    except Exception as e:
        print("destination column error:", e)
        db.session.rollback()

    try:
        db.session.execute(text('ALTER TABLE "order" ADD COLUMN delivery_date DATE;'))
        print("Added delivery_date column to order table.")
    except Exception as e:
        print("delivery_date column error:", e)
        db.session.rollback()
        
    db.session.commit()

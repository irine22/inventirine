from app import create_app, db
from sqlalchemy import text
app = create_app()
with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN phone_otp VARCHAR(10);'))
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN phone_otp_expiry TIMESTAMP;'))
        db.session.commit()
        print('Added columns successfully.')
    except Exception as e:
        db.session.rollback()
        print(f'Error (might already exist): {e}')

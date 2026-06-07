from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE "order" ADD COLUMN destination VARCHAR(100);'))
        db.session.commit()
        print("Successfully added destination column.")
    except Exception as e:
        print("Error adding destination (might already exist):", e)
        db.session.rollback()

    try:
        db.session.execute(text('ALTER TABLE "order" ADD COLUMN delivery_date DATE;'))
        db.session.commit()
        print("Successfully added delivery_date column.")
    except Exception as e:
        print("Error adding delivery_date (might already exist):", e)
        db.session.rollback()

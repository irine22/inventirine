"""Add reset_password_token columns to user table."""
from app import create_app, db
from sqlalchemy import text

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        statements = [
            'ALTER TABLE "user" ADD COLUMN reset_password_token VARCHAR(128)',
            'ALTER TABLE "user" ADD COLUMN reset_password_token_expiry TIMESTAMP',
        ]
        for sql in statements:
            try:
                conn.execute(text(sql))
                print(f"OK: {sql}")
            except Exception as e:
                print(f"SKIP (already exists?): {e}")
        conn.commit()
    print("Migration complete.")

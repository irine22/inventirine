"""One-time migration script: add auth security columns to the user table."""
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        statements = [
            'ALTER TABLE "user" ADD COLUMN created_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "user" ADD COLUMN last_seen TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "user" ADD COLUMN failed_login_attempts INTEGER DEFAULT 0',
            'ALTER TABLE "user" ADD COLUMN locked_until TIMESTAMP',
        ]
        for sql in statements:
            try:
                conn.execute(text(sql))
                print(f"OK: {sql}")
            except Exception as e:
                print(f"SKIP (already exists?): {e}")
        conn.commit()
    print("\nMigration complete.")

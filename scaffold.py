import os

base_dir = r"c:\Users\Administrator\Desktop\invent"

dirs = [
    "app",
    "app/auth",
    "app/inventory",
    "app/api",
    "app/templates",
    "app/templates/auth",
    "app/templates/inventory",
    "app/static",
    "app/static/css",
    "app/static/js"
]

for d in dirs:
    os.makedirs(os.path.join(base_dir, d), exist_ok=True)

# requirements.txt
with open(os.path.join(base_dir, "requirements.txt"), "w") as f:
    f.write("""Flask==3.0.3
Flask-Login==0.6.3
Flask-WTF==1.2.1
WTForms==3.1.2
Werkzeug==3.0.3
bleach==6.1.0
Flask-SQLAlchemy==3.1.1
Flask-Limiter==3.8.0
PyJWT==2.8.0
python-dotenv==1.0.1
gunicorn==22.0.0
email-validator==2.1.1
psycopg[binary]==3.3.4
""")

# .env
with open(os.path.join(base_dir, ".env"), "w") as f:
    f.write("""SECRET_KEY=supersecretrandomkeyhere
DATABASE_URL=sqlite:///inventory.db
FLASK_ENV=development
DEBUG=True
JWT_SECRET=anothersecretkey
""")

# config.py
with open(os.path.join(base_dir, "config.py"), "w") as f:
    f.write("""import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'inventory.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session config
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False # Set to True in production with HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # Uploads
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 # 2MB
""")

# run.py
with open(os.path.join(base_dir, "run.py"), "w") as f:
    f.write("""from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
""")

# app/__init__.py
with open(os.path.join(base_dir, "app", "__init__.py"), "w") as f:
    f.write("""from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Blueprints
    from app.auth.routes import auth_bp
    from app.inventory.routes import inventory_bp
    from app.api.routes import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    return app
""")

print("Scaffold complete.")

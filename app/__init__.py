import os
import logging
from flask import Flask, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

logging.basicConfig(filename='error.log', level=logging.DEBUG)

# ── Core extensions (initialised without app, bound in create_app) ───────────
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page. Your session may have expired.'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Bind extensions to app ───────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # ── Blueprints ───────────────────────────────────────────────────────────
    from app.auth.routes import auth_bp
    from app.inventory.routes import inventory_bp
    from app.api.routes import api_bp
    from app.supplier_routes import supplier_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(supplier_bp)

    # ── Security Headers ─────────────────────────────────────────────────────
    @app.after_request
    def set_secure_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:;"
        )
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        return response

    # Ensure tables exist when the app starts, including in production WSGI/Gunicorn mode.
    with app.app_context():
        db.create_all()

    return app

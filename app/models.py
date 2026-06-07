from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user and not user.is_deleted:
        return user
    return None

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    role = db.Column(db.String(20), default='user')
    is_deleted = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Security / lockout fields
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    # Password reset token
    reset_password_token = db.Column(db.String(128), nullable=True, index=True)
    reset_password_token_expiry = db.Column(db.DateTime, nullable=True)
    
    # SMS OTP fields
    phone_otp = db.Column(db.String(10), nullable=True)
    phone_otp_expiry = db.Column(db.DateTime, nullable=True)

    # Supplier specific fields
    company_name = db.Column(db.String(100))
    country = db.Column(db.String(100))
    business_id = db.Column(db.String(100))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    logo_path = db.Column(db.String(255))

    # ── Password hashing (scrypt via werkzeug) ──────────────────────
    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256:600000', salt_length=16
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # ── Account lockout helpers ─────────────────────────────────────
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    @property
    def is_locked(self):
        if self.locked_until:
            now = datetime.now(timezone.utc)
            locked_until_compare = self.locked_until
            if locked_until_compare.tzinfo is None:
                now = now.replace(tzinfo=None)
            if locked_until_compare > now:
                return True
        return False

    def record_failed_login(self):
        # If lockout has expired, reset counter before recording a new attempt
        if self.locked_until and not self.is_locked:
            self.failed_login_attempts = 0
            self.locked_until = None

        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = datetime.now(timezone.utc) + self.LOCKOUT_DURATION
        db.session.commit()

    def reset_failed_logins(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        db.session.commit()

    def update_last_seen(self):
        self.last_seen = datetime.now(timezone.utc)
        db.session.commit()

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(20))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reorder_threshold = db.Column(db.Integer, default=10)
    location = db.Column(db.String(100), default='Main Warehouse')
    is_deleted = db.Column(db.Boolean, default=False)
    is_available = db.Column(db.Boolean, default=True)
    image_path = db.Column(db.String(255), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Changed from supplier.id to user.id because suppliers are now in User table
    sales = db.relationship('Sale', backref='product', lazy=True)
    movements = db.relationship('InventoryMovement', backref='product', lazy=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    sale_price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class InventoryMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    movement_type = db.Column(db.String(50), nullable=False) # purchase, sale, transfer, return, adjustment
    quantity_change = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    notes = db.Column(db.Text)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship('User', backref='activities', lazy=True)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    field_name = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default='pending') # pending, processing, fulfilled, cancelled, rejected, shipped
    note = db.Column(db.String(500))
    tracking_number = db.Column(db.String(40))
    destination = db.Column(db.String(100))
    delivery_date = db.Column(db.Date)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    product = db.relationship('Product', backref='orders')
    supplier = db.relationship('User', backref='supplier_orders', foreign_keys=[supplier_id])

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')


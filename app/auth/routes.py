import logging
import os
from functools import wraps
from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.auth.forms import LoginForm, RegistrationForm, ChangePasswordForm, ResetPasswordRequestForm, ResetPasswordConfirmForm, UpdateProfileForm, SmsResetRequestForm, SmsOtpVerifyForm
from app import db, limiter
from app.utils import process_and_save_image, log_audit

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# ── Role Selection Entry ─────────────────────────────────────────────────────
@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))
    return redirect(url_for('auth.role_select'))

@auth_bp.route('/role-select')
def role_select():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))
    return render_template('auth/role_select.html', title='Choose Portal')


def _handle_login(form, role_label, role_filter, login_route):
    """Shared login handler for admin and supplier portals."""
    if form.validate_on_submit():
        # Normalize email before database lookup
        normalized_email = form.email.data.strip().lower()
        user = User.query.filter_by(email=normalized_email).first()

        logger.info("Login attempt: email=%s user_found=%s role_label=%s",
                     normalized_email, user is not None, role_label)

        # Account lockout check
        if user and user.is_locked:
            logger.warning("Login rejected (locked): email=%s locked_until=%s",
                           normalized_email, user.locked_until)
            flash('Invalid email or password. Please try again later.', 'danger')
            return redirect(url_for(login_route))

        if user and user.check_password(form.password.data):
            # Verify the user belongs to the chosen portal
            if not role_filter(user):
                logger.warning("Login rejected (role mismatch): email=%s role=%s expected=%s",
                               normalized_email, user.role, role_label)
                flash('Invalid email or password. Please try again.', 'danger')
                return redirect(url_for('auth.role_select'))

            # Suspended (soft-deleted) account
            if user.is_deleted:
                logger.warning("Login rejected (deleted): email=%s", normalized_email)
                flash('Your account has been suspended.', 'danger')
                return redirect(url_for(login_route))

            # Successful login — reset lockout counters
            user.reset_failed_logins()
            user.update_last_seen()

            # Prevent session fixation by clearing the session before logging in
            session.clear()

            login_user(user, remember=form.remember_me.data)

            # Mark session as permanent so PERMANENT_SESSION_LIFETIME applies
            session.permanent = True

            # Log to ActivityLog
            from app.models import ActivityLog
            log = ActivityLog(user_id=user.id, action=f"User logged in via {role_label} portal")
            db.session.add(log)
            db.session.commit()

            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('inventory.dashboard')
            return redirect(next_page)
        else:
            # Record the failed attempt
            if user:
                logger.warning("Login rejected (bad password): email=%s", normalized_email)
                user.record_failed_login()
            else:
                logger.warning("Login rejected (user not found): email=%s", normalized_email)
            flash('Invalid email or password. Please try again.', 'danger')
        return None

    # ── Form validation failed – show WHY ──────────────────────────────────────
    if request.method == 'POST':
        # Check CSRF token explicitly
        csrf_token = request.form.get('csrf_token')
        if not csrf_token:
            logger.warning("Login form validation failed: CSRF token missing (email=%s)",
                           request.form.get('email', 'unknown'))
            flash('Session expired or missing security token. Please reload the page and try again.', 'danger')
        elif form.csrf_token.errors:
            logger.warning("Login form validation failed: CSRF errors=%s (email=%s)",
                           form.csrf_token.errors, request.form.get('email', 'unknown'))
            flash('Security token validation failed. Please reload the page and try again.', 'danger')
        else:
            for field_name, errors in form.errors.items():
                for err in errors:
                    label = getattr(getattr(form, field_name, None), 'label', None)
                    field_label = label.text if label else field_name
                    logger.warning("Login form validation failed: %s=%s", field_label, err)
                    flash(f'{field_label}: {err}', 'danger')
    return None


# ── Admin Login ──────────────────────────────────────────────────────────────
@auth_bp.route('/login/admin', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))
    form = LoginForm()
    # Normalize role to avoid mismatches from capitalization or trailing spaces
    result = _handle_login(form, 'Admin', lambda u: (getattr(u, 'role', '') or '').strip().lower() in ('admin', 'user'), 'auth.admin_login')
    if result:
        return result
    return render_template('auth/login_admin.html', title='Admin Login', form=form)


# ── Supplier Login ───────────────────────────────────────────────────────────
@auth_bp.route('/login/supplier', methods=['GET', 'POST'])
def supplier_login():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))
    form = LoginForm()
    # Accept role values with varied casing/whitespace
    result = _handle_login(form, 'Supplier', lambda u: (getattr(u, 'role', '') or '').strip().lower() == 'supplier', 'auth.supplier_login')
    if result:
        return result
    return render_template('auth/login_supplier.html', title='Supplier Login', form=form)


# ── Logout ───────────────────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    # Log to ActivityLog
    from app.models import ActivityLog
    log = ActivityLog(user_id=current_user.id, action="User logged out")
    db.session.add(log)
    db.session.commit()

    logout_user()
    # Fully clear all session data (admin_verified, etc.)
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))


# ── Registration ─────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour", override_defaults=True)
def register():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        # Normalize email before storage
        normalized_email = form.email.data.strip().lower()
        user = User(
            username=form.username.data,
            email=normalized_email,
            role=form.role.data,
            company_name=form.company_name.data if form.role.data == 'supplier' else None,
            country=form.country.data if form.role.data == 'supplier' else None,
            business_id=form.business_id.data if form.role.data == 'supplier' else None
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        # Log to ActivityLog
        from app.models import ActivityLog
        log = ActivityLog(user_id=user.id, action=f"New user registered: {user.username}")
        db.session.add(log)
        db.session.commit()

        # Auto-login the newly registered user
        login_user(user)
        session.permanent = True
        flash('Registration successful — you are now logged in!', 'success')

        # Redirect to the appropriate dashboard based on role
        if user.role == 'supplier':
            return redirect(url_for('supplier.products'))
        return redirect(url_for('inventory.dashboard'))
    return render_template('auth/register.html', title='Register', form=form)


# ── Profile ──────────────────────────────────────────────────────────────────
@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role == 'admin':
        from datetime import datetime, timezone, timedelta
        verified_until = session.get('admin_verified_until')
        if not verified_until:
            return redirect(url_for('auth.admin_verify', next=request.url))
        try:
            expiry = datetime.fromisoformat(verified_until)
            if expiry <= datetime.now(timezone.utc):
                session.pop('admin_verified', None)
                session.pop('admin_verified_until', None)
                return redirect(url_for('auth.admin_verify', next=request.url))
        except (ValueError, TypeError):
            session.pop('admin_verified', None)
            session.pop('admin_verified_until', None)
            return redirect(url_for('auth.admin_verify', next=request.url))
            
        if not session.get('admin_verified'):
            return redirect(url_for('auth.admin_verify', next=request.url))
            
        session['admin_verified_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    if current_user.role == 'supplier':
        from datetime import datetime, timezone, timedelta
        verified_until = session.get('supplier_verified_until')
        if not verified_until:
            return redirect(url_for('auth.supplier_verify', next=request.url))
        try:
            expiry = datetime.fromisoformat(verified_until)
            if expiry <= datetime.now(timezone.utc):
                session.pop('supplier_verified', None)
                session.pop('supplier_verified_until', None)
                return redirect(url_for('auth.supplier_verify', next=request.url))
        except (ValueError, TypeError):
            session.pop('supplier_verified', None)
            session.pop('supplier_verified_until', None)
            return redirect(url_for('auth.supplier_verify', next=request.url))

        if not session.get('supplier_verified'):
            return redirect(url_for('auth.supplier_verify', next=request.url))

        session['supplier_verified_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    form = UpdateProfileForm()
    if form.validate_on_submit():
        # Normalize email before storage
        normalized_email = form.email.data.strip().lower()
        # Log audit trails for changed fields
        log_audit('user', current_user.id, 'company_name', current_user.company_name, form.company_name.data, current_user.id)
        log_audit('user', current_user.id, 'email', current_user.email, normalized_email, current_user.id)
        log_audit('user', current_user.id, 'phone', current_user.phone, form.phone.data, current_user.id)
        log_audit('user', current_user.id, 'address', current_user.address, form.address.data, current_user.id)
        
        current_user.company_name = form.company_name.data
        current_user.email = normalized_email
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        
        if form.avatar.data:
            upload_folder = os.path.join(current_app.root_path, 'static/uploads')
            filename = process_and_save_image(form.avatar.data, upload_folder)
            if filename:
                current_user.logo_path = filename
            else:
                flash('Invalid image format (must be PNG/JPG).', 'danger')
                
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    elif request.method == 'GET':
        form.company_name.data = current_user.company_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        
    return render_template('profile.html', title='User Profile', form=form)


# ── Change Password ─────────────────────────────────────────────────────────
@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per hour", override_defaults=True)
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()

            # Log to ActivityLog
            from app.models import ActivityLog
            log = ActivityLog(user_id=current_user.id, action="Password changed")
            db.session.add(log)
            db.session.commit()

            flash('Your password has been updated.', 'success')
            return redirect(url_for('auth.profile'))
    return render_template('auth/change_password.html', title='Change Password', form=form)


# ── Password Reset (Token-protected) ─────────────────────────────────────────
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))

    # Check SMTP configuration before attempting email-based password reset.
    mail_user = current_app.config.get('MAIL_USERNAME')
    mail_pass = current_app.config.get('MAIL_PASSWORD')
    smtp_configured = bool(mail_user and mail_pass and mail_user != 'your_gmail@gmail.com')

    form = ResetPasswordRequestForm()
    if smtp_configured and form.validate_on_submit():
        normalized_email = form.email.data.strip().lower()
        user = User.query.filter_by(email=normalized_email).first()
        if not user:
            flash('If an account exists with that email, a reset link has been sent.', 'success')
            return redirect(url_for('auth.login'))

        # ── Generate secure time-limited reset token ─────────────────────────
        import secrets
        import hashlib
        from datetime import timedelta

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        user.reset_password_token = token_hash
        user.reset_password_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.session.commit()

        # ── Build reset link ───────────────────────────────────────────────────
        reset_url = url_for('auth.reset_password_confirm', token=token, _external=True)

        # ── Send email with token ─────────────────────────────────────────────
        from app.email_utils import _send_email_smtp
        subject = "[IMS] Password Reset Request"
        html_body = f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="background:#0b0c10;font-family:sans-serif;padding:30px;">
<div style="max-width:500px;margin:auto;background:#1f2833;border-radius:12px;padding:32px;border:1px solid #2e3d4f;">
<h2 style="color:#66fcf1;">Password Reset</h2>
<p style="color:#c5c6c7;">You requested a password reset. Click the button below to proceed. This link expires in 15 minutes.</p>
<a href="{reset_url}" style="display:inline-block;background:#66fcf1;color:#0b0c10;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin:16px 0;">Reset Password</a>
<p style="color:#8b9cac;font-size:13px;">If you did not request this, ignore this email.</p>
</div></body></html>
"""
        plain_body = f"Password Reset Link (expires 15 min): {reset_url}"
        _send_email_smtp(subject, html_body, plain_body, None)

        from app.models import ActivityLog
        log = ActivityLog(user_id=user.id, action='Password reset token sent')
        db.session.add(log)
        db.session.commit()

        flash('A password reset link has been sent to your email. It expires in 15 minutes.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', title='Reset Password', form=form, smtp_configured=smtp_configured)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm(token):
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))

    import hashlib
    from datetime import datetime, timezone
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user = User.query.filter_by(reset_password_token=token_hash).first()
    if not user:
        flash('Invalid or expired reset token. Please request a new one.', 'danger')
        return redirect(url_for('auth.reset_password'))

    if user.reset_password_token_expiry and user.reset_password_token_expiry.replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None):
        flash('Reset token has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.reset_password'))

    form = ResetPasswordConfirmForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_password_token = None
        user.reset_password_token_expiry = None
        db.session.commit()

        from app.models import ActivityLog
        log = ActivityLog(user_id=user.id, action='Password reset completed via email link')
        db.session.add(log)
        db.session.commit()

        flash('Your password has been reset successfully. Please login with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_confirm.html', token=token, form=form)


# ── Admin Verification Gate ──────────────────────────────────────────────────
def admin_password_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            flash('You do not have permission to access this resource.', 'danger')
            return redirect(url_for('inventory.dashboard'))

        # Re-verify if timeout expired
        from datetime import datetime, timezone, timedelta
        verified_until = session.get('admin_verified_until')
        if verified_until:
            try:
                expiry = datetime.fromisoformat(verified_until)
                if expiry <= datetime.now(timezone.utc):
                    session.pop('admin_verified', None)
                    session.pop('admin_verified_until', None)
                    return redirect(url_for('auth.admin_verify', next=request.url))
            except (ValueError, TypeError):
                session.pop('admin_verified', None)
                session.pop('admin_verified_until', None)
                return redirect(url_for('auth.admin_verify', next=request.url))
        else:
            session.pop('admin_verified', None)
            return redirect(url_for('auth.admin_verify', next=request.url))

        if not session.get('admin_verified'):
            return redirect(url_for('auth.admin_verify', next=request.url))

        # Refresh the timeout on each request
        session['admin_verified_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/admin-verify', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def admin_verify():
    if current_user.role != 'admin':
        flash('You do not have permission to access this resource.', 'danger')
        return redirect(url_for('inventory.dashboard'))

    # Check existing verified session with expiry (5 minute timeout)
    from datetime import datetime, timezone, timedelta
    verified_until = session.get('admin_verified_until')
    if verified_until:
        try:
            expiry = datetime.fromisoformat(verified_until)
            if expiry > datetime.now(timezone.utc):
                return redirect(url_for('inventory.dashboard'))
        except (ValueError, TypeError):
            pass
    session.pop('admin_verified', None)
    session.pop('admin_verified_until', None)

    if request.method == 'POST':
        password = request.form.get('password')
        if current_user.check_password(password):
            session['admin_verified'] = True
            # Expire after 5 minutes of inactivity
            session['admin_verified_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('inventory.dashboard')
            return redirect(next_page)
        else:
            flash('Incorrect password. Access denied.', 'danger')

    return render_template('auth/admin_verify.html', title='Admin Verification')

# ── Supplier Verification Gate ──────────────────────────────────────────────
def supplier_password_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'supplier':
            flash('You do not have permission to access this resource.', 'danger')
            return redirect(url_for('inventory.dashboard'))

        from datetime import datetime, timezone, timedelta
        verified_until = session.get('supplier_verified_until')
        if verified_until:
            try:
                expiry = datetime.fromisoformat(verified_until)
                if expiry <= datetime.now(timezone.utc):
                    session.pop('supplier_verified', None)
                    session.pop('supplier_verified_until', None)
                    return redirect(url_for('auth.supplier_verify', next=request.url))
            except (ValueError, TypeError):
                session.pop('supplier_verified', None)
                session.pop('supplier_verified_until', None)
                return redirect(url_for('auth.supplier_verify', next=request.url))
        else:
            session.pop('supplier_verified', None)
            return redirect(url_for('auth.supplier_verify', next=request.url))

        if not session.get('supplier_verified'):
            return redirect(url_for('auth.supplier_verify', next=request.url))

        session['supplier_verified_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/supplier-verify', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per minute")
def supplier_verify():
    if current_user.role != 'supplier':
        flash('You do not have permission to access this resource.', 'danger')
        return redirect(url_for('inventory.dashboard'))

    from datetime import datetime, timezone, timedelta
    verified_until = session.get('supplier_verified_until')
    if verified_until:
        try:
            expiry = datetime.fromisoformat(verified_until)
            if expiry > datetime.now(timezone.utc):
                return redirect(url_for('inventory.dashboard'))
        except (ValueError, TypeError):
            pass
    session.pop('supplier_verified', None)
    session.pop('supplier_verified_until', None)

    if request.method == 'POST':
        password = request.form.get('password')
        if current_user.check_password(password):
            session['supplier_verified'] = True
            session['supplier_verified_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('inventory.dashboard')
            return redirect(next_page)
        else:
            flash('Incorrect password. Access denied.', 'danger')

    return render_template('auth/supplier_verify.html', title='Supplier Verification')


@auth_bp.route('/api/verify-password', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def api_verify_password():
    data = request.get_json()
    if not data:
        return {"success": False, "message": "Invalid request."}

    password = data.get('password')

    if current_user.role != 'admin' or current_user.is_deleted:
        return {"success": False, "message": "Access denied."}

    if current_user.check_password(password):
        return {"success": True}
    return {"success": False, "message": "Incorrect password."}


# ── Update last_seen on every authenticated request ──────────────────────────
@auth_bp.before_app_request
def track_last_seen():
    if current_user.is_authenticated:
        current_user.update_last_seen()
# ── SMS Password Reset ─────────────────────────────────────────────────────────
@auth_bp.route('/reset-password-sms', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def reset_password_sms():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))

    form = SmsResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(phone=form.phone.data).first()
        if not user or user.role != 'supplier':
            flash('If a supplier account exists with that phone, an SMS has been sent.', 'success')
            return redirect(url_for('auth.login'))

        import random
        from datetime import timedelta, timezone, datetime
        
        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        user.phone_otp = otp
        user.phone_otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.session.commit()

        # Send simulated SMS
        from app.sms_utils import _send_sms_simulated
        _send_sms_simulated(user.phone, f"Your IMS password reset code is: {otp}. It expires in 10 minutes.")

        session['reset_phone'] = user.phone
        flash('An SMS with a 6-digit verification code has been sent to your phone.', 'success')
        return redirect(url_for('auth.verify_sms_otp'))

    return render_template('auth/reset_password_sms.html', form=form)

@auth_bp.route('/verify-sms-otp', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def verify_sms_otp():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))

    phone = session.get('reset_phone')
    if not phone:
        return redirect(url_for('auth.reset_password_sms'))

    form = SmsOtpVerifyForm()
    if form.validate_on_submit():
        from datetime import datetime, timezone
        user = User.query.filter_by(phone=phone, phone_otp=form.otp.data).first()
        
        if not user:
            flash('Invalid verification code.', 'danger')
            return render_template('auth/verify_sms_otp.html', form=form)
            
        if user.phone_otp_expiry and user.phone_otp_expiry.replace(tzinfo=None) < datetime.now(timezone.utc).replace(tzinfo=None):
            flash('Verification code has expired. Please request a new one.', 'danger')
            return redirect(url_for('auth.reset_password_sms'))

        # Code is valid
        user.phone_otp = None
        user.phone_otp_expiry = None
        db.session.commit()
        
        session['sms_verified_phone'] = phone
        session.pop('reset_phone', None)
        return redirect(url_for('auth.set_new_password_sms'))

    return render_template('auth/verify_sms_otp.html', form=form, phone=phone)

@auth_bp.route('/set-new-password-sms', methods=['GET', 'POST'])
@limiter.limit("5 per hour", override_defaults=True)
def set_new_password_sms():
    if current_user.is_authenticated:
        return redirect(url_for('inventory.dashboard'))

    phone = session.get('sms_verified_phone')
    if not phone:
        flash('Session expired or not verified.', 'danger')
        return redirect(url_for('auth.reset_password_sms'))

    form = ResetPasswordConfirmForm()
    if form.validate_on_submit():
        user = User.query.filter_by(phone=phone).first()
        if user:
            user.set_password(form.password.data)
            db.session.commit()
            
            from app.models import ActivityLog
            log = ActivityLog(user_id=user.id, action='Password reset completed via SMS')
            db.session.add(log)
            db.session.commit()
            
            session.pop('sms_verified_phone', None)
            flash('Your password has been successfully reset. Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/set_new_password_sms.html', form=form)

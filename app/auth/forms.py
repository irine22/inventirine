import re
import bleach
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User


def sanitize_html(text):
    """Sanitize input against HTML injection and XSS using bleach."""
    if text is None:
        return text
    return bleach.clean(text)


def normalize_email(text):
    """Normalize email values for login and registration."""
    if text is None:
        return text
    return text.strip().lower()


def strong_password(form, field):
    """Enforce password complexity rules."""
    pw = field.data
    errors = []
    if not re.search(r'[A-Z]', pw):
        errors.append('one uppercase letter')
    if not re.search(r'[a-z]', pw):
        errors.append('one lowercase letter')
    if not re.search(r'\d', pw):
        errors.append('one digit')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', pw):
        errors.append('one special character (!@#$%^&*…)')
    if errors:
        raise ValidationError(f'Password must contain at least: {", ".join(errors)}.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()], filters=[normalize_email])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)], filters=[sanitize_html])
    email = StringField('Email', validators=[DataRequired(), Email()], filters=[sanitize_html, normalize_email])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8), strong_password
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    role = SelectField('Register As', choices=[
        ('supplier', 'Supplier')
    ], validators=[DataRequired()])

    # Supplier specific fields
    company_name = StringField('Company Name', filters=[sanitize_html])
    country = StringField('Country', filters=[sanitize_html])
    business_id = StringField('Business Registration / Tax ID', filters=[sanitize_html])

    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Please use a different email address.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(), Length(min=8), strong_password
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Update Password')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()], filters=[sanitize_html, normalize_email])
    submit = SubmitField('Request Password Reset')

class ResetPasswordConfirmForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(), Length(min=8), strong_password
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Reset Password')

class UpdateProfileForm(FlaskForm):
    company_name = StringField('Company Name', filters=[sanitize_html])
    email = StringField('Contact Email', validators=[DataRequired(), Email()], filters=[sanitize_html, normalize_email])
    phone = StringField('Phone Number', filters=[sanitize_html])
    address = StringField('Address', filters=[sanitize_html])
    # File allowed limits file type to images. FileSize limits to 2MB (2 * 1024 * 1024 bytes)
    avatar = FileField('Update Company Logo', validators=[
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!'),
        FileSize(max_size=2 * 1024 * 1024, message='File must be under 2MB')
    ])
    submit = SubmitField('Update Profile')

    def validate_email(self, email):
        # We need access to current_user to check if email is taken by someone else
        from flask_login import current_user
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Please use a different email address.')

def validate_phone_format(form, field):
    import re
    if not re.match(r'^\+?[0-9\s\-\(\)]{7,20}$', field.data):
        raise ValidationError('Invalid phone number format.')

class SmsResetRequestForm(FlaskForm):
    phone = StringField('Phone Number', validators=[DataRequired(), validate_phone_format], filters=[sanitize_html])
    submit = SubmitField('Send SMS Code')

def validate_otp_digits(form, field):
    if not field.data.isdigit():
        raise ValidationError('OTP must contain only digits.')

class SmsOtpVerifyForm(FlaskForm):
    otp = StringField('6-Digit Code', validators=[DataRequired(), Length(min=6, max=6), validate_otp_digits])
    submit = SubmitField('Verify Code')


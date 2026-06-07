"""
Email configuration test script.

HOW TO USE:
  1. Generate an App Password at https://myaccount.google.com/apppasswords
  2. Edit .env and paste the 16-char App Password into MAIL_PASSWORD
  3. Run:  py test_email.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.email_utils import _send_email_smtp

app = create_app()
with app.app_context():
    mail_user = app.config.get('MAIL_USERNAME')
    mail_pass = app.config.get('MAIL_PASSWORD')
    admin_email = app.config.get('ADMIN_EMAIL')

    print(f"  Sender   : {mail_user}")
    print(f"  Password : {'***set***' if mail_pass and mail_pass != 'your_16_char_app_password_here' else 'NOT SET'}")

    if not mail_pass or mail_pass == 'your_16_char_app_password_here':
        print("\n❌ MAIL_PASSWORD is still the placeholder.")
        print("   Generate an App Password at https://myaccount.google.com/apppasswords")
        print("   Then paste it into .env and run this script again.")
        sys.exit(1)

    subject = "[IMS] Test Email"
    html = "<h1>Test</h1><p>Your email config is working!</p>"
    plain = "Your email config is working!"
    success = _send_email_smtp(subject, html, plain)

    if success:
        print(f"\n✅ Test email sent to {admin_email}!")
    else:
        print(f"\n❌ Failed. Check error.log for details.")

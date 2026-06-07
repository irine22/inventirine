import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import logging

def _send_email_smtp(subject, html_body, plain_body, recipient=None):
    try:
        mail_user = current_app.config.get('MAIL_USERNAME')
        mail_pass = current_app.config.get('MAIL_PASSWORD')
        mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
        mail_port = current_app.config.get('MAIL_PORT', 465)
        
        if not recipient:
            recipient = current_app.config.get('ADMIN_EMAIL')
            
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Inventory System <{mail_user}>"
        msg['To'] = recipient

        msg.attach(MIMEText(plain_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL(mail_server, mail_port) as server:
            server.login(mail_user, mail_pass)
            server.send_message(msg)
            
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

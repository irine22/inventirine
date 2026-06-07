#!/usr/bin/env python3
"""Utility to unlock user accounts locked by failed logins.

Usage:
  python unlock_user.py --email user@example.com
  python unlock_user.py --all
"""
import argparse
from app import create_app, db
from app.models import User


def unlock_by_email(email: str):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"No user found with email: {email}")
            return
        if not user.is_locked and (user.failed_login_attempts or 0) == 0:
            print(f"User {email} is not locked and has no failed attempts.")
            return
        user.reset_failed_logins()
        print(f"Unlocked user {email} (failed attempts reset).")


def unlock_all():
    app = create_app()
    with app.app_context():
        users = User.query.filter(User.locked_until.isnot(None)).all()
        if not users:
            print("No locked users found.")
            return
        for u in users:
            u.reset_failed_logins()
            print(f"Unlocked {u.email}")


def main():
    parser = argparse.ArgumentParser(description='Unlock locked user accounts')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--email', help='Email address of the user to unlock')
    group.add_argument('--all', action='store_true', help='Unlock all locked users')
    args = parser.parse_args()

    if args.all:
        unlock_all()
    else:
        unlock_by_email(args.email)


if __name__ == '__main__':
    main()

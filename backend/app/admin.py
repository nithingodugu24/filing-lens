"""Deliberate operator-only administrator setup, with no password in shell arguments."""

import argparse
from getpass import getpass

from passlib.hash import bcrypt
from sqlalchemy import select

from .config import get_settings
from .db import init_db, session_scope
from .models import User


def main():
    parser = argparse.ArgumentParser(description="Create an administrator deliberately before public signup")
    parser.add_argument("email")
    parser.add_argument("full_name")
    args = parser.parse_args()
    get_settings().validate_deployment()
    password = getpass("New administrator password: ")
    if len(password) < 14 or len(password.encode()) > 72:
        raise SystemExit("Use a password with at least 14 characters and at most 72 UTF-8 bytes")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords did not match")
    init_db()
    with session_scope() as db:
        email = args.email.strip().lower()
        if "@" not in email or db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("Email is invalid or already exists. Existing accounts are not changed.")
        db.add(
            User(
                email=email,
                full_name=args.full_name.strip(),
                password_hash=bcrypt.hash(password),
                role="admin",
            )
        )
    print("Administrator created. Existing reports and ownership are unchanged.")


if __name__ == "__main__":
    main()

"""Create the first administrator from explicitly supplied environment secrets."""

import re

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{2,80}$")


def main() -> None:
    """Create the first administrator, or safely skip an initialized database."""
    settings = get_settings()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            print("Database already has users; administrator bootstrap skipped")
            return
        username = settings.bootstrap_admin_username.strip().lower()
        password = settings.bootstrap_admin_password
        if not USERNAME_PATTERN.fullmatch(username):
            raise SystemExit("BOOTSTRAP_ADMIN_USERNAME must be 2-80 characters: letters, digits, dot, underscore or hyphen")
        if password is None or len(password.get_secret_value()) < 12:
            raise SystemExit("Set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD (at least 12 characters)")
        db.add(User(username=username, password_hash=hash_password(password.get_secret_value()), role=UserRole.ADMIN))
        db.commit()
    print(f"Initial administrator '{username}' created")


if __name__ == "__main__":
    main()
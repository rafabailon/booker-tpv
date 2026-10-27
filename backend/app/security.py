"""Password hashing and role-based authorization."""

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return an Argon2 password hash."""
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without exposing the stored hash."""
    return password_hash.verify(password, encoded_hash)
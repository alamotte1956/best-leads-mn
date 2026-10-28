"""Authentication helpers for the administrative dashboard."""

import os

from werkzeug.security import check_password_hash


def admin_auth_configured():
    """Check whether an administrator password hash is configured."""
    return bool(os.environ.get("ADMIN_PASSWORD_HASH", "").strip())


def verify_admin_password(password):
    """Verify a supplied password against the configured hash."""
    stored_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()

    if not stored_hash:
        return False

    if not isinstance(password, str) or not password:
        return False

    try:
        return check_password_hash(stored_hash, password)
    except (ValueError, TypeError):
        return False

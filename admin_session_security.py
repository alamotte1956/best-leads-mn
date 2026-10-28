"""Administrator session invalidation after password changes."""

import hashlib
import hmac
import os


def current_password_fingerprint():
    """Return a fingerprint of the configured admin password hash."""
    stored_hash = os.environ.get(
        "ADMIN_PASSWORD_HASH", ""
    ).strip()

    if not stored_hash:
        return None

    return hashlib.sha256(
        stored_hash.encode("utf-8")
    ).hexdigest()


def session_password_valid(saved_fingerprint):
    """Check whether the session matches the current password hash."""
    current = current_password_fingerprint()

    if not current or not isinstance(saved_fingerprint, str):
        return False

    return hmac.compare_digest(
        saved_fingerprint,
        current,
    )

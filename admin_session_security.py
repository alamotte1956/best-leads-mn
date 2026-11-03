"""Administrator session invalidation after password changes."""

import hashlib
import hmac
import os
import time


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


def admin_session_valid(state):
    at=state.get('admin_login_at')
    return (state.get('admin_authenticated') is True and not isinstance(at,bool)
            and isinstance(at,(int,float)) and 0<=time.time()-at<=3600
            and session_password_valid(state.get('admin_password_fingerprint')))


def safe_admin_destination(value):
    """Only existing same-site administrative GET pages may follow sign-in."""
    from urllib.parse import urlsplit
    from flask import current_app
    from werkzeug.exceptions import HTTPException
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<32 for c in value) or '\\' in value:
        return '/admin'
    try:
        parts=urlsplit(value)
    except ValueError:
        return '/admin'
    if (parts.scheme or parts.netloc or parts.fragment or not (parts.path=='/admin' or parts.path.startswith('/admin/'))
            or parts.path in ('/admin/login','/admin/logout')):
        return '/admin'
    try:
        current_app.url_map.bind('').match(parts.path,method='GET')
    except HTTPException:
        return '/admin'
    return value

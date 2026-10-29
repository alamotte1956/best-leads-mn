import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW_MINUTES = 15
LOCKOUT_MINUTES = 15


def account_key(email, secret):
    if not isinstance(email, str) or not email.strip():
        raise ValueError("Valid email required")
    if not isinstance(secret, str) or not secret:
        raise ValueError("Server-side secret required")

    normalized = email.strip().lower()
    return hmac.new(
        secret.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def normalize_now(now=None):
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def check_login_allowed(session, key, now=None):
    now = normalize_now(now)

    row = session.execute(
        text("""
            SELECT locked_until
            FROM contractor_login_attempts
            WHERE account_key_hash = :key
            FOR UPDATE
        """),
        {"key": key}
    ).first()

    return not (
        row is not None
        and row.locked_until is not None
        and row.locked_until > now
    )


def record_login_failure(session, key, now=None):
    now = normalize_now(now)

    session.execute(
        text("""
            INSERT INTO contractor_login_attempts (
                account_key_hash,
                failed_attempts,
                window_started_at,
                updated_at
            )
            VALUES (:key, 0, :now, :now)
            ON CONFLICT (account_key_hash) DO NOTHING
        """),
        {"key": key, "now": now}
    )

    row = session.execute(
        text("""
            SELECT failed_attempts, window_started_at, locked_until
            FROM contractor_login_attempts
            WHERE account_key_hash = :key
            FOR UPDATE
        """),
        {"key": key}
    ).first()

    if row.locked_until is not None and row.locked_until > now:
        return True

    window_expired = (
        row.window_started_at is None
        or row.window_started_at <= now - timedelta(
            minutes=ATTEMPT_WINDOW_MINUTES
        )
    )

    attempts = 1 if window_expired else row.failed_attempts + 1
    started = now if window_expired else row.window_started_at

    locked_until = (
        now + timedelta(minutes=LOCKOUT_MINUTES)
        if attempts >= MAX_FAILED_ATTEMPTS
        else None
    )

    session.execute(
        text("""
            UPDATE contractor_login_attempts
            SET failed_attempts = :attempts,
                window_started_at = :started,
                locked_until = :locked_until,
                updated_at = :now
            WHERE account_key_hash = :key
        """),
        {
            "key": key,
            "attempts": attempts,
            "started": started,
            "locked_until": locked_until,
            "now": now
        }
    )

    return locked_until is not None


def record_login_success(session, key):
    session.execute(
        text("""
            DELETE FROM contractor_login_attempts
            WHERE account_key_hash = :key
              AND (
                  locked_until IS NULL
                  OR locked_until <= clock_timestamp()
              )
        """),
        {"key": key}
    )

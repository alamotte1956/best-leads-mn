"""SQLite login accounting for local development; PostgreSQL retains advisory locks."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete

def utc(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

def allowed(session, key, now):
    from app import ContractorLoginAttempt as Attempt
    row = session.execute(select(Attempt).where(Attempt.account_key_hash == key)).scalar_one_or_none()
    return not (row and row.locked_until and utc(row.locked_until) > now)

def failure(session, key, now):
    from app import ContractorLoginAttempt as Attempt
    row = session.execute(select(Attempt).where(Attempt.account_key_hash == key)).scalar_one_or_none()
    if row is None:
        row = Attempt(account_key_hash=key, failed_attempts=0)
        session.add(row)
    if row.locked_until and utc(row.locked_until) > now:
        return True
    if row.window_started_at is None or utc(row.window_started_at) <= now - timedelta(minutes=15):
        row.failed_attempts = 0
        row.window_started_at = now
    row.failed_attempts += 1
    row.locked_until = now + timedelta(minutes=15) if row.failed_attempts >= 5 else None
    row.updated_at = now
    session.flush()
    return row.locked_until is not None

def success(session, key):
    from app import ContractorLoginAttempt as Attempt
    session.execute(delete(Attempt).where(Attempt.account_key_hash == key))

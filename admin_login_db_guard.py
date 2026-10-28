"""Persistent administrator login-attempt tracking."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, func, select

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 900


def _cutoff():
    return datetime.now(timezone.utc) - timedelta(
        seconds=LOCKOUT_SECONDS
    )


def is_locked(db, model, identifier):
    statement = (
        select(func.count())
        .select_from(model)
        .where(model.client_identifier == identifier)
        .where(model.attempted_at >= _cutoff())
    )

    count = db.session.execute(statement).scalar_one()
    return count >= MAX_ATTEMPTS


def record_failure(db, model, identifier):
    attempt = model(
        client_identifier=identifier,
        attempted_at=datetime.now(timezone.utc),
    )

    db.session.add(attempt)
    db.session.flush()

    return is_locked(db, model, identifier)


def clear_failures(db, model, identifier):
    statement = delete(model).where(
        model.client_identifier == identifier
    )

    db.session.execute(statement)
    db.session.flush()


def cleanup_expired(db, model):
    statement = delete(model).where(
        model.attempted_at < _cutoff()
    )

    result = db.session.execute(statement)
    db.session.commit()

    return result.rowcount

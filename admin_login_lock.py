"""Database transaction locking for administrator login protection."""

import hashlib
from sqlalchemy import text


def lock_identifier(db, identifier):
    """Acquire a PostgreSQL transaction-scoped advisory lock.

    Must be called inside the same database transaction that
    checks and updates login-attempt records.

    SQLite does not support PostgreSQL advisory locks.
    """

    dialect = db.session.get_bind().dialect.name

    if dialect != "postgresql":
        raise RuntimeError(
            "Advisory login locks require PostgreSQL."
        )

    digest = hashlib.sha256(
        identifier.encode("utf-8")
    ).digest()

    lock_key = int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=True,
    )

    db.session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key},
    )

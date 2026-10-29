"""Transaction-level PostgreSQL locking for lead matching."""

from sqlalchemy import text


def lock_lead_for_matching(db_session, lead_id):
    """Serialize matching operations for a single homeowner lead.

    Must run inside the same database transaction as offer creation.
    The lock is released automatically at commit or rollback.
    """
    if isinstance(lead_id, bool) or not isinstance(lead_id, int):
        raise ValueError("Lead ID must be an integer.")

    if lead_id <= 0:
        raise ValueError("Lead ID must be positive.")

    db_session.execute(
        text("""
            SELECT pg_advisory_xact_lock(
                726351,
                :lead_id
            )
        """),
        {"lead_id": lead_id},
    )

    return True

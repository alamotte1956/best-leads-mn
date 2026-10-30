"""Expire overdue contractor offers within a database transaction."""

from sqlalchemy import text

from sequential_matching_lock import lock_lead_for_matching


def expire_overdue_offers_for_lead(db_session, lead_id):
    """Expire overdue pending offers for one homeowner lead.

    Uses PostgreSQL server time. Caller must commit or roll back.
    """
    lock_lead_for_matching(db_session, lead_id)

    result = db_session.execute(
        text("""
            UPDATE lead_offers
            SET status = 'expired'
            WHERE lead_id = :lead_id
              AND status = 'pending'
              AND expires_at <= clock_timestamp()
            RETURNING id
        """),
        {"lead_id": lead_id},
    )

    return [row[0] for row in result.fetchall()]

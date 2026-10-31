"""Secure, atomic contractor offer decline.

The caller authenticates the contractor and controls commit/rollback.
No notifications, payments, or matching activation occur here.
"""

from sqlalchemy import text

from sequential_matching_lock import lock_lead_for_matching


DECLINE_OFFER_SQL = text("""
    UPDATE lead_offers
       SET status = 'declined',
           declined_at = clock_timestamp()
     WHERE id = :offer_id
       AND contractor_id = :contractor_id
       AND status = 'pending'
       AND expires_at > clock_timestamp()
       AND offered_at <= clock_timestamp()
       AND accepted_at IS NULL
       AND declined_at IS NULL
    RETURNING id, lead_id, contractor_id, declined_at
""")


def decline_contractor_offer(session, offer_id, contractor_id):
    """Decline an eligible offer within the caller's transaction."""

    if (
        not isinstance(offer_id, int)
        or isinstance(offer_id, bool)
        or offer_id <= 0
    ):
        raise ValueError("Invalid offer ID.")

    if (
        not isinstance(contractor_id, int)
        or isinstance(contractor_id, bool)
        or contractor_id <= 0
    ):
        raise ValueError("Invalid contractor ID.")

    lead_id = session.execute(
        text("""
            SELECT lead_id
            FROM lead_offers
            WHERE id = :offer_id
              AND contractor_id = :contractor_id
        """),
        {
            "offer_id": offer_id,
            "contractor_id": contractor_id,
        },
    ).scalar_one_or_none()

    if lead_id is None:
        return None

    lock_lead_for_matching(session, lead_id)

    result = session.execute(
        DECLINE_OFFER_SQL,
        {
            "offer_id": offer_id,
            "contractor_id": contractor_id,
        },
    ).mappings().first()

    return dict(result) if result is not None else None

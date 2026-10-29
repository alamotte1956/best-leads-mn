from sqlalchemy import text


ACCEPT_OFFER_SQL = text("""
    UPDATE lead_offers
       SET status = 'accepted',
           accepted_at = clock_timestamp()
     WHERE id = :offer_id
       AND contractor_id = :contractor_id
       AND status = 'pending'
       AND expires_at > clock_timestamp()
       AND offered_at <= clock_timestamp()
       AND accepted_at IS NULL
    RETURNING id, lead_id, contractor_id, accepted_at
""")


def accept_contractor_offer(session, offer_id, contractor_id):
    """
    Atomically accept an eligible offer.

    Caller must authenticate the contractor and supply
    the authenticated contractor's ID, not a client-provided ID.

    Caller controls the surrounding database transaction.
    This function does not commit or send notifications.
    """
    if not isinstance(offer_id, int) or isinstance(offer_id, bool):
        raise ValueError("Invalid offer ID.")

    if not isinstance(contractor_id, int) or isinstance(contractor_id, bool):
        raise ValueError("Invalid contractor ID.")

    if offer_id <= 0 or contractor_id <= 0:
        raise ValueError("IDs must be positive.")

    # Serialize acceptance with expiration and sequential matching.
    # This lookup does not change the offer.
    offer_lead_id = session.execute(
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

    if offer_lead_id is None:
        return None

    from sequential_matching_lock import lock_lead_for_matching

    lock_lead_for_matching(session, offer_lead_id)

    result = session.execute(
        ACCEPT_OFFER_SQL,
        {
            "offer_id": offer_id,
            "contractor_id": contractor_id,
        },
    ).mappings().first()

    if result is None:
        return None

    return dict(result)

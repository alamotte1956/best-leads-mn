"""Expire old offers and advance to the next eligible contractor."""

from datetime import datetime, timezone

from sqlalchemy import text

from contractor_offer_creation import create_next_sequential_offer
from contractor_offer_expiration import expire_overdue_offers_for_lead


def advance_sequential_offer(
    db_session,
    lead,
    contractors,
    lead_offer_model,
    additional_services_by_contractor=None,
):
    """Expire overdue offers and stage at most one next offer.

    Caller must commit or roll back the transaction.
    All acceptance paths must coordinate with the same lead lock.
    """
    # The expiration function acquires the per-lead PostgreSQL
    # transaction lock, held until commit or rollback.
    expired_ids = expire_overdue_offers_for_lead(
        db_session, lead.id
    )

    # Lock and recheck the current homeowner lead record.
    # This prevents a concurrent cancellation from being
    # overlooked while staging another contractor offer.
    current_status = db_session.execute(
        text("""
            SELECT status
            FROM leads
            WHERE id = :lead_id
            FOR UPDATE
        """),
        {"lead_id": lead.id},
    ).scalar_one_or_none()

    if current_status != "New":
        return {
            "expired_offer_ids": expired_ids,
            "new_offer": None,
        }

    # Make expiration updates visible to subsequent ORM queries.
    db_session.flush()

    new_offer = create_next_sequential_offer(
        db_session=db_session,
        lead=lead,
        contractors=contractors,
        lead_offer_model=lead_offer_model,
        additional_services_by_contractor=additional_services_by_contractor,
        now=datetime.now(timezone.utc),
    )

    return {
        "expired_offer_ids": expired_ids,
        "new_offer": new_offer,
    }

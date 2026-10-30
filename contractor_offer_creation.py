"""Create 15-minute contractor offers without sending notifications."""

from datetime import datetime, timezone, timedelta

from contractor_matching import contractor_matches


def create_offers_for_lead(
    db_session,
    lead,
    contractors,
    lead_offer_model,
    additional_services_by_contractor=None,
    now=None,
):
    """Stage eligible contractor offers in the current transaction.

    The caller must commit or roll back. No SMS or payment is initiated.
    """
    additional_services_by_contractor = (
        additional_services_by_contractor or {}
    )

    offered_at = now or datetime.now(timezone.utc)

    if offered_at.tzinfo is None:
        raise ValueError("Offer timestamp must be timezone-aware.")

    offered_at = offered_at.astimezone(timezone.utc)
    expires_at = offered_at + timedelta(minutes=15)

    created = []

    for contractor in contractors:
        services = additional_services_by_contractor.get(
            contractor.id, []
        )

        if not contractor_matches(contractor, lead, services):
            continue

        existing = db_session.query(lead_offer_model.id).filter(
            lead_offer_model.lead_id == lead.id,
            lead_offer_model.contractor_id == contractor.id,
        ).first()

        if existing is not None:
            continue

        offer = lead_offer_model(
            lead_id=lead.id,
            contractor_id=contractor.id,
            status="pending",
            offered_at=offered_at,
            expires_at=expires_at,
        )

        db_session.add(offer)
        created.append(offer)

    return created


def create_next_sequential_offer(
    db_session,
    lead,
    contractors,
    lead_offer_model,
    additional_services_by_contractor=None,
    now=None,
):
    """Stage at most one new offer for a lead.

    The caller must serialize concurrent matching attempts for this
    lead, commit or roll back, and arrange expiration processing.
    No SMS or payments are initiated.
    """
    additional_services_by_contractor = (
        additional_services_by_contractor or {}
    )

    offered_at = now or datetime.now(timezone.utc)

    if offered_at.tzinfo is None:
        raise ValueError("Offer timestamp must be timezone-aware.")

    offered_at = offered_at.astimezone(timezone.utc)

    previous_offers = db_session.query(
        lead_offer_model.contractor_id,
        lead_offer_model.status,
        lead_offer_model.expires_at,
    ).filter(
        lead_offer_model.lead_id == lead.id
    ).all()

    # An accepted offer permanently ends sequential matching.
    if any(row.status == "accepted" for row in previous_offers):
        return None

    # A pending offer blocks another offer, even if its deadline
    # has passed. Expiration must first be recorded explicitly.
    if any(row.status == "pending" for row in previous_offers):
        return None

    previously_offered_ids = {
        row.contractor_id for row in previous_offers
    }

    for contractor in contractors:
        if contractor.id in previously_offered_ids:
            continue

        services = additional_services_by_contractor.get(
            contractor.id, []
        )

        if not contractor_matches(contractor, lead, services):
            continue

        offer = lead_offer_model(
            lead_id=lead.id,
            contractor_id=contractor.id,
            status="pending",
            offered_at=offered_at,
            expires_at=offered_at + timedelta(minutes=15),
        )

        db_session.add(offer)
        return offer

    return None


def create_locked_sequential_offer(
    db_session,
    lead,
    contractors,
    lead_offer_model,
    additional_services_by_contractor=None,
    now=None,
):
    """Create at most one offer while holding a per-lead DB lock.

    Caller must use PostgreSQL, commit or roll back the same
    transaction, and ensure all matching paths use this function.
    """
    from sequential_matching_lock import lock_lead_for_matching

    lock_lead_for_matching(db_session, lead.id)

    # Flush staged ORM changes so this transaction's existing
    # offer query sees earlier work before creating another offer.
    db_session.flush()

    return create_next_sequential_offer(
        db_session=db_session,
        lead=lead,
        contractors=contractors,
        lead_offer_model=lead_offer_model,
        additional_services_by_contractor=additional_services_by_contractor,
        now=now,
    )

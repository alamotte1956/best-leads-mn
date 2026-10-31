from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_


CENTRAL = ZoneInfo("America/Chicago")


def central_day_bounds(now=None):
    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("Timezone-aware datetime required")

    local_date = now.astimezone(CENTRAL).date()

    start_local = datetime.combine(
        local_date,
        time.min,
        tzinfo=CENTRAL,
    )

    end_local = datetime.combine(
        local_date + timedelta(days=1),
        time.min,
        tzinfo=CENTRAL,
    )

    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )


def load_owner_dashboard_data(db, Lead, Contractor, LeadOffer):
    now = datetime.now(timezone.utc)
    start_utc, end_utc = central_day_bounds(now)

    leads_today = (
        db.session.query(func.count(Lead.id))
        .filter(
            Lead.submitted_at >= start_utc,
            Lead.submitted_at < end_utc,
        )
        .scalar()
    ) or 0

    pending_offers = (
        db.session.query(func.count(LeadOffer.id))
        .filter(
            LeadOffer.status == "pending",
            LeadOffer.expires_at > now,
        )
        .scalar()
    ) or 0

    accepted_offers = (
        db.session.query(func.count(LeadOffer.id))
        .filter(LeadOffer.status == "accepted")
        .scalar()
    ) or 0

    expired_offers = (
        db.session.query(func.count(LeadOffer.id))
        .filter(
            or_(
                LeadOffer.status == "expired",
                (
                    (LeadOffer.status == "pending")
                    & (LeadOffer.expires_at <= now)
                ),
            )
        )
        .scalar()
    ) or 0

    # Fetch the 200 most recent homeowners first.
    # Then select the most relevant offer for each homeowner.
    leads = (
        db.session.query(Lead)
        .order_by(Lead.id.desc())
        .limit(200)
        .all()
    )

    lead_ids = [lead.id for lead in leads]

    offers = (
        db.session.query(LeadOffer, Contractor)
        .outerjoin(
            Contractor,
            Contractor.id == LeadOffer.contractor_id,
        )
        .filter(LeadOffer.lead_id.in_(lead_ids))
        .order_by(LeadOffer.offered_at.desc(), LeadOffer.id.desc())
        .all()
    ) if lead_ids else []

    offers_by_lead = {}

    for offer, contractor in offers:
        offers_by_lead.setdefault(offer.lead_id, []).append(
            (offer, contractor)
        )

    lead_rows = []

    for lead in leads:
        candidates = offers_by_lead.get(lead.id, [])

        def offer_priority(item):
            offer, contractor = item

            if offer.status == "accepted":
                return 3

            if (
                offer.status == "pending"
                and offer.expires_at > now
            ):
                return 2

            return 1

        if candidates:
            offer, contractor = max(
                candidates,
                key=offer_priority,
            )
        else:
            offer, contractor = None, None
        status = offer.status if offer else None

        if (
            offer is not None
            and status == "pending"
            and offer.expires_at <= now
        ):
            status = "expired"

        lead_rows.append({
            "lead_id": lead.id,
            "service_needed": lead.service_needed,
            "zip_code": lead.zip_code,
            "submitted_at": lead.submitted_at,
            "contractor_name": (
                contractor.company_name if contractor else None
            ),
            "offer_status": status,
            "expires_at": (
                offer.expires_at if offer else None
            ),
        })

    metrics = {
        "leads_today": leads_today,
        "pending_offers": pending_offers,
        "accepted_offers": accepted_offers,
        "expired_offers": expired_offers,
        "paid_today_cents": None,
        "refunds_today_cents": None,
    }

    return {
        "metrics": metrics,
        "lead_rows": lead_rows,
        "server_now": now,
    }

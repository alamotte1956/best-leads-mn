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

    rows = (
        db.session.query(Lead, LeadOffer, Contractor)
        .outerjoin(LeadOffer, LeadOffer.lead_id == Lead.id)
        .outerjoin(
            Contractor,
            Contractor.id == LeadOffer.contractor_id,
        )
        .order_by(Lead.id.desc(), LeadOffer.offered_at.desc())
        .limit(200)
        .all()
    )

    lead_rows = []

    for lead, offer, contractor in rows:
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

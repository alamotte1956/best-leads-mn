"""Sequential matching worker. Live execution is disabled by default."""

import os
from datetime import datetime, timezone
from sqlalchemy import func

from contractor_offer_advancement import advance_sequential_offer


def process_matching_batch():
    """Process leads sequentially, committing each lead separately."""

    # worker-live-execution-guard
    if os.environ.get("ENABLE_LIVE_MATCHING") != "YES":
        raise RuntimeError("Live matching is disabled.")

    activation_text = os.environ.get(
        "MATCHING_ACTIVATION_UTC", ""
    ).strip()

    if not activation_text:
        raise RuntimeError(
            "MATCHING_ACTIVATION_UTC must be configured."
        )

    activation = datetime.fromisoformat(
        activation_text.replace("Z", "+00:00")
    )

    if activation.tzinfo is None:
        raise RuntimeError(
            "MATCHING_ACTIVATION_UTC must include a timezone."
        )

    activation = activation.astimezone(timezone.utc)

    from app import (
        app, db, Lead, LeadOffer,
        Contractor, ContractorService,
    )

    with app.app_context():
        leads = (
            db.session.query(Lead)
            .filter(
                Lead.submitted_at.isnot(None),
                Lead.submitted_at >= activation,
                Lead.status == "New",
                ~db.session.query(LeadOffer.id)
                .filter(
                    LeadOffer.lead_id == Lead.id,
                    LeadOffer.status == "accepted",
                )
                .exists()
            )
            .order_by(Lead.id)
            .all()
        )

        processed = 0
        created = 0
        expired = 0

        for lead in leads:
            try:
                contractors = (
                    db.session.query(Contractor)
                    .filter(
                        Contractor.active.is_(True),
                        Contractor.verified.is_(True),
                        Contractor.is_test.is_(False),
                    )
                    .order_by(Contractor.id)
                    .all()
                )

                services = (
                    db.session.query(ContractorService)
                    .all()
                )

                service_map = {}

                for service in services:
                    service_map.setdefault(
                        service.contractor_id, []
                    ).append(service.service_name)

                result = advance_sequential_offer(
                    db.session,
                    lead,
                    contractors,
                    LeadOffer,
                    additional_services_by_contractor=service_map,
                )

                db.session.commit()

                processed += 1
                expired += len(result["expired_offer_ids"])

                if result["new_offer"] is not None:
                    created += 1

            except Exception:
                db.session.rollback()
                app.logger.exception(
                    "Matching failed for lead %s", lead.id
                )

        return {
            "processed": processed,
            "created": created,
            "expired": expired,
        }


if __name__ == "__main__":
    if os.environ.get("ENABLE_LIVE_MATCHING") != "YES":
        print("MATCHING DISABLED")
        print("Set ENABLE_LIVE_MATCHING=YES only after approval.")
    else:
        print(process_matching_batch())

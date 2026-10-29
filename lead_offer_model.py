from datetime import datetime, timedelta, timezone


ACCEPTANCE_WINDOW_MINUTES = 15


def utc_now():
    return datetime.now(timezone.utc)


def define_lead_offer(db):
    class LeadOffer(db.Model):
        __tablename__ = "lead_offers"

        id = db.Column(db.BigInteger, primary_key=True)

        lead_id = db.Column(
            db.Integer,
            db.ForeignKey("leads.id"),
            nullable=False,
            index=True
        )

        contractor_id = db.Column(
            db.Integer,
            db.ForeignKey("contractors.id"),
            nullable=False,
            index=True
        )

        status = db.Column(
            db.String(30),
            nullable=False,
            default="pending"
        )

        offered_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False,
            default=utc_now
        )

        expires_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False
        )

        accepted_at = db.Column(db.DateTime(timezone=True))
        declined_at = db.Column(db.DateTime(timezone=True))

        created_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False,
            default=utc_now
        )

        @staticmethod
        def calculate_expiration(offered_at):
            if offered_at.tzinfo is None:
                raise ValueError("offered_at must be timezone-aware")
            return offered_at + timedelta(
                minutes=ACCEPTANCE_WINDOW_MINUTES
            )

    return LeadOffer

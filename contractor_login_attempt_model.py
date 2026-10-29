from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


def define_contractor_login_attempt(db):
    class ContractorLoginAttempt(db.Model):
        __tablename__ = "contractor_login_attempts"

        id = db.Column(db.BigInteger, primary_key=True)

        account_key_hash = db.Column(
            db.String(64),
            nullable=False,
            unique=True,
            index=True
        )

        failed_attempts = db.Column(
            db.Integer,
            nullable=False,
            default=0
        )

        window_started_at = db.Column(
            db.DateTime(timezone=True),
            nullable=True
        )

        locked_until = db.Column(
            db.DateTime(timezone=True),
            nullable=True
        )

        updated_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False,
            default=utc_now,
            onupdate=utc_now
        )

    return ContractorLoginAttempt

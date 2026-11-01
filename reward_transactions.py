"""Transactional reward primitives, intentionally disconnected from live prizes.

Call only after the trusted payment/free-entry verifier authorizes the source.
A business must be resolved by verified legal identity, never email/account ID.
"""
from datetime import datetime, timezone
from secrets import randbelow
from sqlalchemy import update


def define_rewards(db):
    class Business(db.Model):
        __tablename__ = 'reward_businesses'
        id = db.Column(db.Integer, primary_key=True)
        identity_digest = db.Column(db.String(64), unique=True, nullable=False)
        verified = db.Column(db.Boolean, nullable=False, default=False)

    class Credit(db.Model):
        __tablename__ = 'reward_credits'
        id = db.Column(db.Integer, primary_key=True)
        business_id = db.Column(db.Integer, db.ForeignKey('reward_businesses.id'), nullable=False)
        source = db.Column(db.String(200), unique=True, nullable=False)
        kind = db.Column(db.String(20), nullable=False)
        consumed = db.Column(db.Boolean, nullable=False, default=False)
        __table_args__ = (db.CheckConstraint("kind in ('purchase', 'free')"),)

    class Month(db.Model):
        __tablename__ = 'reward_months'
        business_id = db.Column(db.Integer, db.ForeignKey('reward_businesses.id'), primary_key=True)
        month = db.Column(db.String(7), primary_key=True)
        used = db.Column(db.Integer, nullable=False, default=0)
        __table_args__ = (db.CheckConstraint('used >= 0 AND used <= 10'),)

    class Spin(db.Model):
        __tablename__ = 'reward_spins'
        id = db.Column(db.Integer, primary_key=True)
        business_id = db.Column(db.Integer, db.ForeignKey('reward_businesses.id'), nullable=False)
        credit_id = db.Column(db.Integer, db.ForeignKey('reward_credits.id'), unique=True, nullable=False)
        prize_index = db.Column(db.Integer, nullable=False)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    return Business, Credit, Month, Spin


def issue_credit(db, models, business_id, source, kind):
    """Trusted internal boundary; source is a provider event or approved entry ID.

    Caller owns commit/rollback. Unique source rejects webhook replays globally.
    No public client may supply authorization to this function.
    """
    Business, Credit, _, _ = models
    business = db.session.get(Business, business_id)
    if not business or not business.verified or kind not in ('purchase', 'free') or not source:
        raise ValueError('Verified business and authorized source required')
    credit = Credit(business_id=business_id, source=source, kind=kind)
    db.session.add(credit)
    db.session.flush()
    return credit


def consume_credit(db, models, business_id, credit_id, now=None):
    """Atomic consumption with a combined UTC calendar-month cap.

    Caller must rollback on ANY failure, including unique-conflict retries.
    PostgreSQL/SQLite unique constraints serialize first-month creation.
    Returning a result does not commit it. Never redeem real prizes here.
    """
    Business, Credit, Month, Spin = models
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware server time required')
    business = db.session.get(Business, business_id)
    if not business or not business.verified:
        raise ValueError('Verified business required')
    month = now.astimezone(timezone.utc).strftime('%Y-%m')
    if db.session.get(Month, (business_id, month)) is None:
        db.session.add(Month(business_id=business_id, month=month, used=0))
        db.session.flush()
    changed = db.session.execute(update(Month).where(
        Month.business_id == business_id, Month.month == month, Month.used < 10
    ).values(used=Month.used + 1)).rowcount
    if changed != 1:
        raise ValueError('Monthly limit reached')
    changed = db.session.execute(update(Credit).where(
        Credit.id == credit_id, Credit.business_id == business_id,
        Credit.consumed.is_(False)
    ).values(consumed=True)).rowcount
    if changed != 1:
        raise ValueError('Credit unavailable')
    # Identical selection for both entry methods. Placeholder simulation only.
    spin = Spin(business_id=business_id, credit_id=credit_id,
                prize_index=randbelow(8), created_at=now)
    db.session.add(spin)
    db.session.flush()
    return spin

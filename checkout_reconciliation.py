"""Reconcile existing hosted checkouts without creating sessions or confirming payment.

Provider calls are opt-in. All updates preserve successful payment/refund history;
only signed payment webhooks can unlock homeowner contact details.
"""
import os
from datetime import datetime, timezone
from flask import abort
from sqlalchemy import update

MUTABLE_STATES = ('creating', 'open', 'awaiting_payment', 'awaiting_confirmation')


def define_checkout_history(db):
    class CheckoutQuoteHistory(db.Model):
        __tablename__ = 'checkout_quote_history'
        id = db.Column(db.Integer, primary_key=True)
        payment_id = db.Column(db.Integer, db.ForeignKey('lead_payments.id'), nullable=False, index=True)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False)
        quote_version = db.Column(db.Integer, nullable=False)
        amount_cents = db.Column(db.Integer, nullable=False)
        currency = db.Column(db.String(3), nullable=False)
        mode = db.Column(db.String(10), nullable=False)
        market_benchmark_id = db.Column(db.Integer, db.ForeignKey('market_lead_benchmarks.id'))
        quote_expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
        session_id = db.Column(db.String(150), unique=True)
        status = db.Column(db.String(30), nullable=False)
        archived_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        __table_args__ = (
            db.UniqueConstraint('payment_id','quote_version',name='checkout_history_payment_version'),
            db.CheckConstraint("status in ('unused','expired')",name='checkout_history_terminal_state'),
            db.CheckConstraint('quote_version > 0 AND amount_cents > 0',name='checkout_history_amount_version'),
        )
    return CheckoutQuoteHistory


def configuration():
    if os.environ.get('CHECKOUT_RECONCILIATION_ENABLED', '').lower() != 'true':
        abort(503, 'Checkout status reconciliation is not enabled.')
    mode = os.environ.get('STRIPE_MODE', 'test')
    key = os.environ.get('STRIPE_SECRET_KEY', '')
    prefixes = ('sk_test_', 'rk_test_') if mode == 'test' else ('sk_live_', 'rk_live_')
    if mode not in ('test', 'live') or not key.startswith(prefixes):
        abort(503, 'Stripe mode and credentials are not configured.')
    return key, mode


def validate_session(payment, value):
    """Never change an order using another account, quote or environment's session."""
    from billing import as_dict
    obj = as_dict(value)
    metadata = obj.get('metadata') or {}
    if not isinstance(metadata,dict):
        raise ValueError('Hosted checkout metadata is invalid.')
    if (obj.get('id') != payment.session_id or obj.get('mode') != 'payment'
            or type(obj.get('livemode')) is not bool
            or obj['livemode'] != (payment.mode == 'live')
            or obj.get('amount_total') != payment.amount_cents
            or obj.get('currency') != payment.currency
            or metadata.get('payment_id') != str(getattr(payment, 'payment_id', payment.id))
            or metadata.get('contractor_id') != str(payment.contractor_id)
            or metadata.get('quote_version', '1') != str(payment.quote_version)
            or (payment.market_benchmark_id and metadata.get('benchmark_id') != str(payment.market_benchmark_id))):
        raise ValueError('Hosted checkout does not match the stored order.')
    return obj


def expiration_reason(payment, now):
    from app import db, LeadOffer, Lead, Contractor
    from market_pricing import aware
    from national_coverage import market_eligible
    if os.environ.get('PAYMENTS_ENABLED', '').lower() != 'true':
        return 'payments_disabled'
    if payment.mode == 'live' and os.environ.get('STRIPE_LIVE_PAYMENTS_ENABLED', '').lower() != 'true':
        return 'live_payments_disabled'
    if not payment.quote_expires_at or aware(payment.quote_expires_at) <= now:
        return 'quote_expired'
    offer = db.session.get(LeadOffer, payment.offer_id)
    lead = db.session.get(Lead, offer.lead_id) if offer else None
    contractor = db.session.get(Contractor, payment.contractor_id)
    if not offer or offer.contractor_id != payment.contractor_id or offer.status != 'accepted' or not lead or lead.status != 'New':
        return 'request_unavailable'
    if not contractor or not market_eligible(contractor, lead):
        return 'coverage_unavailable'
    return None


def reconcile_payment(payment, *, api_key, now=None):
    """The caller commits. A provider timeout never means a session was expired."""
    import stripe
    from app import db, Payment
    from billing import retrieve_checkout, expire_checkout
    now = now or datetime.now(timezone.utc)
    previous = payment.status
    session_id = payment.session_id
    if payment.mode != os.environ.get('STRIPE_MODE', 'test'):
        raise ValueError('Order belongs to another Stripe environment.')
    if previous in ('paid', 'refunded'):
        return 'settled'
    if previous not in MUTABLE_STATES:
        return 'unchanged'
    if not session_id:
        # A create timeout may have left an unlinked hosted session. Never infer
        # that no charge is possible, issue a replacement, or use a new key.
        return 'unlinked'
    obj = validate_session(payment, retrieve_checkout(session_id, api_key=api_key))
    if obj.get('status') == 'open':
        if obj.get('payment_status') != 'unpaid':
            raise ValueError('Unexpected open checkout payment state.')
        if not expiration_reason(payment, now):
            return 'open'
        try:
            obj = validate_session(payment, expire_checkout(session_id, api_key=api_key))
        except stripe.InvalidRequestError:
            # Payment or another expiration may win the race. Retrieve the
            # actual outcome; do not convert an API error into local expiry.
            obj = validate_session(payment, retrieve_checkout(session_id, api_key=api_key))
    status = obj.get('status')
    if status == 'expired' and obj.get('payment_status') == 'unpaid':
        if previous in ('awaiting_payment', 'awaiting_confirmation'):
            return 'awaiting_confirmation'
        target = 'expired'
    elif status == 'complete' and obj.get('payment_status') in ('paid', 'unpaid', 'no_payment_required'):
        target = 'awaiting_confirmation' if obj.get('payment_status') == 'paid' else 'awaiting_payment'
        if previous == 'awaiting_confirmation':
            return 'awaiting_confirmation'
    elif status == 'open':
        return 'open'
    else:
        raise ValueError('Unrecognized hosted checkout state.')
    # Do not clobber a webhook that committed while the provider call was in
    # flight. Conditional writes protect SQLite as well as PostgreSQL.
    changed = db.session.execute(update(Payment).where(
        Payment.id == payment.id, Payment.session_id == session_id,
        Payment.status == previous,
    ).values(status=target), execution_options={'synchronize_session': False}).rowcount
    if changed != 1:
        db.session.expire(payment)
        return 'changed'
    return target


def reconcile_batch(*, limit=100, after_id=0):
    from app import db, Payment, app
    if type(limit) is not int or not 1 <= limit <= 500 or type(after_id) is not int or after_id < 0:
        raise ValueError('Use a batch limit from 1 to 500 and a nonnegative cursor.')
    key, mode = configuration()
    identifiers = [row[0] for row in db.session.query(Payment.id).filter(
        Payment.mode == mode, Payment.status.in_(MUTABLE_STATES),
        Payment.session_id.is_not(None), Payment.id > after_id,
    ).order_by(Payment.id).limit(limit).all()]
    results = {}
    for identifier in identifiers:
        try:
            payment = db.session.get(Payment, identifier, populate_existing=True)
            outcome = reconcile_payment(payment, api_key=key)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            # Avoid provider payloads, keys, URLs and customer details in logs.
            app.logger.warning('Checkout reconciliation failed for order %s (%s)', identifier, type(error).__name__)
            outcome = 'error'
        results[outcome] = results.get(outcome, 0) + 1
    return {'processed': len(identifiers), 'results': results,
            'next_after_id': identifiers[-1] if len(identifiers) == limit else None}

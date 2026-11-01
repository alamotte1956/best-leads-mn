"""Explicit Stripe Checkout and signed payment accounting. Rewards stay disabled."""
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from flask import Blueprint, abort, render_template, request, redirect
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from operations import contractor_required
from contractor_onboarding import require_csrf

billing = Blueprint('billing', __name__)

def as_dict(value):
    return value if isinstance(value,dict) else value.to_dict()

def payment_activation():
    try:
        value=datetime.fromisoformat(os.environ.get('PAYMENTS_ACTIVATION_UTC','').replace('Z','+00:00'))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except ValueError:
        return None



def stripe_configuration():
    key = os.environ.get('STRIPE_SECRET_KEY','')
    if os.environ.get('STRIPE_MODE','test') not in ('test','live'):
        abort(503,'Stripe mode is not configured.')
    live = os.environ.get('STRIPE_MODE','test') == 'live'
    if os.environ.get('PAYMENTS_ENABLED','').lower() != 'true':
        abort(503,'Payments are not enabled.')
    if live and os.environ.get('STRIPE_LIVE_PAYMENTS_ENABLED','').lower() != 'true':
        abort(503,'Live payments are not enabled.')
    if not key.startswith(('sk_live_','rk_live_') if live else ('sk_test_','rk_test_')):
        abort(503,'Stripe mode and credentials are not configured.')
    origin = os.environ.get('PUBLIC_SITE_URL','').rstrip('/')
    parts = urlsplit(origin)
    if parts.scheme != 'https' or not parts.netloc or parts.path or parts.query or parts.fragment or parts.username:
        abort(503,'Configure an HTTPS public site origin.')
    return key,origin


@billing.get('/contractor/billing')
@contractor_required
def overview(contractor):
    from app import db, Payment, LeadOffer, Lead, LeadPrice
    payments = Payment.query.filter_by(contractor_id=contractor.id).order_by(Payment.id.desc()).limit(100).all()
    offers = LeadOffer.query.filter_by(contractor_id=contractor.id,status='accepted').order_by(LeadOffer.id.desc()).limit(100).all()
    activation=payment_activation()
    configured_services={row.service_name for row in LeadPrice.query.filter_by(state_code='MN',mode=os.environ.get('STRIPE_MODE','test')).all()}
    paid_offers={p.offer_id for p in payments if p.status in ('paid','refunded')}
    offers=[offer for offer in offers if activation and offer.accepted_at and
            (offer.accepted_at.replace(tzinfo=timezone.utc) if offer.accepted_at.tzinfo is None else offer.accepted_at) >= activation
            and offer.id not in paid_offers and db.session.get(Lead,offer.lead_id).service_needed in configured_services]
    return render_template('billing.html',payments=payments,offers=offers,
        enabled=os.environ.get('PAYMENTS_ENABLED','').lower()=='true' and activation is not None)


@billing.post('/contractor/offers/<int:offer_id>/checkout')
@contractor_required
def checkout(contractor,offer_id):
    import stripe
    from app import db, Payment, LeadOffer, Lead, LeadPrice
    require_csrf()
    key,origin = stripe_configuration()
    activation=payment_activation()
    if activation is None:
        abort(503,'Configure a timezone-aware payment activation date.')
    offer = LeadOffer.query.filter_by(id=offer_id,contractor_id=contractor.id,status='accepted').first()
    if not offer:
        abort(404)
    accepted=offer.accepted_at
    if accepted and accepted.tzinfo is None:
        accepted=accepted.replace(tzinfo=timezone.utc)
    if not accepted or accepted < activation:
        abort(409,'This historical offer is not billable under the current activation policy.')
    payment = Payment.query.filter_by(offer_id=offer_id).first()
    if payment is None:
        lead=db.session.get(Lead,offer.lead_id)
        # All existing and currently accepted intake belongs to Minnesota.
        # New states stay disabled; do not infer their identity from client input.
        configured=LeadPrice.query.filter_by(state_code='MN',service_name=lead.service_needed,
            mode=os.environ.get('STRIPE_MODE','test')).first()
        if not configured:
            abort(503,'Pricing for this service and state is not configured.')
        price_id=configured.stripe_price_id
        price = as_dict(stripe.Price.retrieve(price_id,api_key=key))
        if price.get('currency') != 'usd' or not price.get('active') or price.get('type') != 'one_time' or type(price.get('unit_amount')) is not int or price['unit_amount'] <= 0:
            abort(503,'A fixed one-time lead price is required.')
        payment = Payment(offer_id=offer_id,contractor_id=contractor.id,
            amount_cents=price['unit_amount'],currency=price['currency'],price_id=price_id)
        db.session.add(payment)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback();payment=Payment.query.filter_by(offer_id=offer_id).one()
    if payment.status in ('paid','refunded'):
        abort(409,'This lead has already been paid.')
    if payment.session_id:
        existing = as_dict(stripe.checkout.Session.retrieve(payment.session_id,api_key=key))
        if existing.get('status') != 'open':
            abort(409,'This checkout is no longer open. Contact administration for reconciliation.')
        return redirect(existing['url'],code=303)
    created = stripe.checkout.Session.create(api_key=key,mode='payment',payment_method_types=['card'],
        line_items=[{'price':payment.price_id,'quantity':1}],client_reference_id=str(payment.id),
        metadata={'payment_id':str(payment.id),'contractor_id':str(contractor.id)},
        success_url=origin+'/contractor/billing?returned=1',cancel_url=origin+'/contractor/billing',
        idempotency_key=f'lead-payment:{payment.id}:v1')
    db.session.execute(update(Payment).where(Payment.id==payment.id,Payment.status=='creating',
        Payment.session_id.is_(None)).values(session_id=created['id'],status='open'))
    db.session.commit();db.session.refresh(payment)
    if payment.status in ('paid','refunded'):
        return redirect('/contractor/billing',code=303)
    return redirect(created['url'],code=303)


@billing.post('/webhooks/stripe')
def stripe_webhook():
    import stripe
    from app import db, Payment, ProviderEvent, Contractor
    from communications import queue_email
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET','')
    if not secret:
        abort(503)
    try:
        event = as_dict(stripe.Webhook.construct_event(request.get_data(),request.headers.get('Stripe-Signature',''),secret))
    except (ValueError,stripe.SignatureVerificationError):
        abort(400,'Invalid Stripe webhook signature.')
    if bool(event.get('livemode')) != (os.environ.get('STRIPE_MODE','test')=='live'):
        abort(400,'Stripe mode mismatch.')
    kind = event['type'];obj = event['data']['object']
    if kind not in ('checkout.session.completed','charge.refunded'):
        return '',204
    if db.session.get(ProviderEvent,event['id']):
        return '',204
    db.session.add(ProviderEvent(id=event['id']))
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        if db.session.get(ProviderEvent,event['id']):
            return '',204
        raise
    try:
        if kind == 'checkout.session.completed':
            payment = Payment.query.filter_by(session_id=obj['id']).with_for_update().first()
            if not payment:
                # A signed callback can arrive before the session-create response.
                reference=obj.get('metadata',{}).get('payment_id','')
                if isinstance(reference,str) and reference.isdigit() and len(reference)<12:
                    payment=Payment.query.filter_by(id=int(reference),session_id=None,status='creating').with_for_update().first()
            if not payment:
                abort(409,'Checkout has not been linked yet.')
            if (obj.get('payment_status') != 'paid' or obj.get('mode') != 'payment'
                or obj.get('amount_total') != payment.amount_cents or obj.get('currency') != payment.currency
                or obj.get('metadata',{}).get('payment_id') != str(payment.id)
                or obj.get('metadata',{}).get('contractor_id') != str(payment.contractor_id)):
                abort(400,'Payment details do not match the stored order.')
            if payment.status not in ('paid','refunded'):
                payment.session_id=obj['id']
                payment.status='paid';payment.paid_at=datetime.now(timezone.utc)
                payment.payment_intent=obj['payment_intent']
                contractor=db.session.get(Contractor,payment.contractor_id)
                queue_email(f'payment:{payment.id}:receipt',contractor.email,'Payment received',
                    f'Your lead payment of {payment.amount_cents / 100:.2f} {payment.currency.upper()} has been confirmed. No rewards or prizes were issued.')
        else:
            if not isinstance(obj.get('payment_intent'),str) or not obj['payment_intent']:
                abort(400)
            payment = Payment.query.filter_by(payment_intent=obj.get('payment_intent')).with_for_update().first()
            if not payment:
                abort(409,'Payment has not been recorded yet.')
            refunded = obj.get('amount_refunded',0)
            if type(refunded) is not int or refunded < 0 or refunded > payment.amount_cents:
                abort(400)
            payment.refunded_cents=max(payment.refunded_cents,refunded)
            if payment.refunded_cents == payment.amount_cents:
                payment.status='refunded'
        db.session.commit()
    except Exception:
        db.session.rollback();raise
    return '',204


import stripe
@billing.errorhandler(stripe.StripeError)
def provider_unavailable(error):
    return render_template('error.html',code=503,title='Payment provider unavailable',
        message='We could not reach Stripe. Please try again later. Returning to this page does not confirm a payment.'),503

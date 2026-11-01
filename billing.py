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


def create_checkout(*,api_key,idempotency_key,**params):
    import stripe
    return stripe.StripeClient(api_key).v1.checkout.sessions.create(params,
        options={'idempotency_key':idempotency_key})


def retrieve_checkout(session_id,*,api_key):
    import stripe
    return stripe.StripeClient(api_key).v1.checkout.sessions.retrieve(session_id)


def billable_offer(contractor,offer_id):
    from app import LeadOffer
    from market_pricing import aware
    activation=payment_activation()
    if activation is None:
        abort(503,'Configure a timezone-aware payment activation date.')
    offer=LeadOffer.query.filter_by(id=offer_id,contractor_id=contractor.id,status='accepted').first()
    if not offer:
        abort(404)
    if not offer.accepted_at or aware(offer.accepted_at)<activation:
        abort(409,'This historical offer is not billable under the activation policy.')
    return offer


@billing.get('/contractor/billing')
@contractor_required
def overview(contractor):
    from app import Payment,LeadOffer
    from market_pricing import aware
    payments=Payment.query.filter_by(contractor_id=contractor.id).order_by(Payment.id.desc()).limit(100).all()
    offers=LeadOffer.query.filter_by(contractor_id=contractor.id,status='accepted').order_by(LeadOffer.id.desc()).limit(100).all()
    activation=payment_activation()
    paid_offers={row.offer_id for row in payments if row.status in ('paid','refunded')}
    offers=[row for row in offers if activation and row.accepted_at and aware(row.accepted_at)>=activation and row.id not in paid_offers]
    return render_template('billing.html',payments=payments,offers=offers,
        enabled=os.environ.get('PAYMENTS_ENABLED','').lower()=='true' and activation is not None)


@billing.post('/contractor/offers/<int:offer_id>/quote')
@contractor_required
def market_quote(contractor,offer_id):
    from app import db,Lead,Payment
    from market_pricing import current_benchmark,quote_from_benchmark,aware
    require_csrf()
    stripe_configuration()
    offer=billable_offer(contractor,offer_id)
    payment=Payment.query.filter_by(offer_id=offer_id).first()
    if payment:
        if payment.status in ('paid','refunded'):
            abort(409,'This offer has already been paid.')
        if not payment.market_benchmark_id or not payment.quote_expires_at:
            abort(409,'This older order needs reconciliation before market pricing can be applied.')
        if aware(payment.quote_expires_at)<=datetime.now(timezone.utc):
            abort(409,'This quote has expired. Administration must reconcile any earlier checkout before it can be replaced.')
    else:
        lead=db.session.get(Lead,offer.lead_id)
        evidence=current_benchmark(lead)
        amount,expires=quote_from_benchmark(evidence)
        payment=Payment(offer_id=offer_id,contractor_id=contractor.id,amount_cents=amount,currency='usd',
            price_id=f'market:{evidence.id}',market_benchmark_id=evidence.id,quote_expires_at=expires)
        db.session.add(payment)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409,'Another quote is being prepared. Please refresh your payment history.')
    return render_template('market_quote.html',payment=payment)


@billing.post('/contractor/offers/<int:offer_id>/checkout')
@contractor_required
def checkout(contractor,offer_id):
    import hashlib
    from app import db,Payment
    from market_pricing import aware
    require_csrf()
    key,origin=stripe_configuration()
    billable_offer(contractor,offer_id)
    payment=Payment.query.filter_by(offer_id=offer_id,contractor_id=contractor.id).first()
    if not payment or not payment.market_benchmark_id or not payment.quote_expires_at:
        abort(409,'Request a current market quote before starting checkout. Assigned prices are disabled.')
    if payment.status in ('paid','refunded'):
        abort(409,'This offer has already been paid.')
    remaining=(aware(payment.quote_expires_at)-datetime.now(timezone.utc)).total_seconds()
    if remaining<=0:
        abort(409,'This quote has expired. It cannot be charged at the old price.')
    if payment.session_id:
        existing=as_dict(retrieve_checkout(payment.session_id,api_key=key))
        if existing.get('status')!='open':
            abort(409,'Checkout is closed or awaiting confirmation. Please check payment history.')
        return redirect(existing['url'],code=303)
    if remaining<30*60+30:
        abort(409,'Too little quote validity remains to start Stripe Checkout. Request reconciliation for a fresh quote.')
    suffix=''.join(chr(97+value%26) for value in hashlib.sha256(str(payment.id).encode()).digest()[:8])
    created=create_checkout(api_key=key,mode='payment',
        line_items=[{'price_data':{'currency':'usd','unit_amount':payment.amount_cents,
            'product_data':{'name':f'Restoration lead offer #{offer_id}'}},'quantity':1}],
        client_reference_id=str(payment.id),
        integration_identifier='restoration-market-'+suffix,
        expires_at=int(aware(payment.quote_expires_at).timestamp()),
        metadata={'payment_id':str(payment.id),'contractor_id':str(contractor.id),
                  'benchmark_id':str(payment.market_benchmark_id)},
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
    if kind not in ('checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed','charge.refunded'):
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
        if kind.startswith('checkout.session.'):
            payment = Payment.query.filter_by(session_id=obj['id']).with_for_update().first()
            if not payment:
                # A signed callback can arrive before the session-create response.
                reference=obj.get('metadata',{}).get('payment_id','')
                if isinstance(reference,str) and reference.isdigit() and len(reference)<12:
                    payment=Payment.query.filter_by(id=int(reference),session_id=None,status='creating').with_for_update().first()
            if not payment:
                abort(409,'Checkout has not been linked yet.')
            if (obj.get('mode') != 'payment'
                or obj.get('amount_total') != payment.amount_cents or obj.get('currency') != payment.currency
                or obj.get('metadata',{}).get('payment_id') != str(payment.id)
                or obj.get('metadata',{}).get('contractor_id') != str(payment.contractor_id)):
                abort(400,'Payment details do not match the stored order.')
            if payment.market_benchmark_id and obj.get('metadata',{}).get('benchmark_id')!=str(payment.market_benchmark_id):
                abort(400,'Market quote does not match the order.')
            if kind=='checkout.session.async_payment_failed' or obj.get('payment_status')!='paid':
                if payment.status not in ('paid','refunded'):
                    payment.session_id=obj['id']
                    payment.status='failed' if kind=='checkout.session.async_payment_failed' else 'awaiting_payment'
                db.session.commit()
                return '',204
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

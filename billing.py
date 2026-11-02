"""Explicit Stripe Checkout and signed payment accounting. Rewards stay disabled."""
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from flask import Blueprint, abort, render_template, request, redirect, flash, url_for
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


def offer_contact_available(offer):
    """Legacy acceptance is preserved; newly billable contacts need verified payment."""
    from app import db, Payment, Contractor, Lead
    from market_pricing import aware
    if offer.status != 'accepted':
        return False
    from national_coverage import market_eligible
    contractor=db.session.get(Contractor,offer.contractor_id)
    lead=db.session.get(Lead,offer.lead_id)
    if not contractor or not lead or not market_eligible(contractor,lead):
        return False
    payment = Payment.query.filter_by(offer_id=offer.id, contractor_id=offer.contractor_id).first()
    if payment:
        return bool(payment.status == 'paid' and payment.paid_at and payment.refunded_cents < payment.amount_cents
                    and payment.mode == os.environ.get('STRIPE_MODE','test'))
    activation = payment_activation()
    if activation is None and os.environ.get('PAYMENTS_ENABLED','').lower() == 'true':
        return False
    # No retroactive fees for pre-activation or undated historical acceptances.
    return not activation or not offer.accepted_at or aware(offer.accepted_at) < activation



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


def expire_checkout(session_id, *, api_key):
    import stripe
    return stripe.StripeClient(api_key).v1.checkout.sessions.expire(session_id)


def billable_offer(contractor,offer_id):
    from app import db, Lead, LeadOffer
    from market_pricing import aware
    activation=payment_activation()
    if activation is None:
        abort(503,'Configure a timezone-aware payment activation date.')
    offer=LeadOffer.query.filter_by(id=offer_id,contractor_id=contractor.id,status='accepted').first()
    if not offer:
        abort(404)
    lead = db.session.get(Lead,offer.lead_id)
    if not lead or lead.status != 'New':
        abort(409,'This request is no longer open for new checkout. Existing payment history is retained.')
    from national_coverage import market_eligible
    if not market_eligible(contractor, lead):
        abort(409, 'This state is unavailable or the state coverage approval is no longer current.')
    if not offer.accepted_at or aware(offer.accepted_at)<activation:
        abort(409,'This historical offer is not billable under the activation policy.')
    return offer


@billing.get('/contractor/billing')
@contractor_required
def overview(contractor):
    from app import Payment,LeadOffer,Lead,CheckoutQuoteHistory
    from market_pricing import aware
    payments=Payment.query.filter_by(contractor_id=contractor.id).order_by(Payment.id.desc()).limit(100).all()
    offers=LeadOffer.query.join(Lead,Lead.id==LeadOffer.lead_id).filter(
        LeadOffer.contractor_id==contractor.id,LeadOffer.status=='accepted',Lead.status=='New'
    ).order_by(LeadOffer.id.desc()).limit(100).all()
    activation=payment_activation()
    paid_offers={row.offer_id for row in payments if row.status in ('paid','refunded')}
    offers=[row for row in offers if activation and row.accepted_at and aware(row.accepted_at)>=activation and row.id not in paid_offers]
    history={}
    for row in CheckoutQuoteHistory.query.filter_by(contractor_id=contractor.id).order_by(CheckoutQuoteHistory.id.desc()).limit(200).all():
        history.setdefault(row.payment_id,[]).append(row)
    return render_template('billing.html',payments=payments,offers=offers,quote_history=history,
        enabled=os.environ.get('PAYMENTS_ENABLED','').lower()=='true' and activation is not None,
        reconciliation_enabled=os.environ.get('CHECKOUT_RECONCILIATION_ENABLED','').lower()=='true')


@billing.post('/contractor/offers/<int:offer_id>/quote')
@contractor_required
def market_quote(contractor,offer_id):
    from app import db,Lead,Payment,CheckoutQuoteHistory
    from market_pricing import current_benchmark,quote_from_benchmark,aware
    require_csrf()
    stripe_configuration()
    offer=billable_offer(contractor,offer_id)
    payment=Payment.query.filter_by(offer_id=offer_id).first()
    if payment:
        if payment.mode != os.environ.get('STRIPE_MODE','test'):
            abort(409,'This order belongs to a different Stripe environment. It requires reconciliation.')
        if payment.status in ('paid','refunded'):
            abort(409,'This offer has already been paid.')
        if payment.status not in ('quoted','creating','open','expired'):
            abort(409,'This order is closed or awaiting confirmation. Its existing payment history must be reconciled before replacement.')
        if not payment.market_benchmark_id or not payment.quote_expires_at:
            abort(409,'This older order needs reconciliation before market pricing can be applied.')
        if aware(payment.quote_expires_at)<=datetime.now(timezone.utc) or payment.status=='expired':
            if payment.paid_at or payment.payment_intent or payment.refunded_cents:
                abort(409,'This order has payment activity. Preserve it for provider reconciliation.')
            previous_status=payment.status
            snapshot={name:getattr(payment,name) for name in (
                'contractor_id','quote_version','amount_cents','currency','mode',
                'market_benchmark_id','quote_expires_at','session_id')}
            # Unlinked creating orders may have an in-flight provider request.
            # Only a never-started quote or a verified expired session can retire.
            if payment.status == 'quoted' and not payment.session_id:
                retired_status='unused'
            elif payment.status=='expired' and payment.session_id:
                from checkout_reconciliation import validate_session
                try:
                    obj=validate_session(payment,retrieve_checkout(payment.session_id,api_key=stripe_configuration()[0]))
                except ValueError:
                    abort(409,'The earlier checkout could not be verified. Its payment history was preserved.')
                if obj.get('status')!='expired' or obj.get('payment_status')!='unpaid':
                    abort(409,'The earlier checkout is not confirmed expired. Its payment history was preserved.')
                retired_status='expired'
            else:
                abort(409,'This quote has expired. Reconcile any earlier checkout before requesting a replacement.')
            lead=db.session.get(Lead,offer.lead_id)
            evidence=current_benchmark(lead)
            amount,expires=quote_from_benchmark(evidence)
            changed=db.session.execute(update(Payment).where(
                Payment.id==payment.id,Payment.status==previous_status,
                Payment.session_id==snapshot['session_id'],Payment.quote_version==snapshot['quote_version'],
            ).values(amount_cents=amount,market_benchmark_id=evidence.id,
                price_id=f'market:{evidence.id}',quote_expires_at=expires,
                quote_version=snapshot['quote_version']+1,session_id=None,status='quoted'),
                execution_options={'synchronize_session':False}).rowcount
            if changed != 1:
                db.session.rollback()
                abort(409,'The quote changed in another session. Please refresh your payment history.')
            db.session.add(CheckoutQuoteHistory(payment_id=payment.id,status=retired_status,**snapshot))
            db.session.commit();db.session.refresh(payment)
    else:
        lead=db.session.get(Lead,offer.lead_id)
        evidence=current_benchmark(lead)
        amount,expires=quote_from_benchmark(evidence)
        payment=Payment(offer_id=offer_id,contractor_id=contractor.id,amount_cents=amount,currency='usd',mode=os.environ.get('STRIPE_MODE','test'),
            price_id=f'market:{evidence.id}',market_benchmark_id=evidence.id,quote_expires_at=expires,status='quoted')
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
    if payment.mode != os.environ.get('STRIPE_MODE','test'):
        abort(409,'This order belongs to a different Stripe environment. It cannot be charged here.')
    if request.form.get('quote_version','1') != str(payment.quote_version):
        abort(409,'This quote was replaced. Review the current quote before paying.')
    if payment.status in ('paid','refunded'):
        abort(409,'This offer has already been paid.')
    if payment.status not in ('quoted','creating','open'):
        abort(409,'Checkout is unavailable or awaiting payment confirmation. Check payment history.')
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
    if payment.status == 'quoted':
        changed=db.session.execute(update(Payment).where(
            Payment.id==payment.id,Payment.status=='quoted',Payment.session_id.is_(None),
            Payment.quote_expires_at==payment.quote_expires_at,Payment.quote_version==payment.quote_version,
        ).values(status='creating')).rowcount
        if changed != 1:
            db.session.rollback()
            abort(409,'Checkout changed in another session. Please check payment history.')
        # Persist the attempt before any external call. A timeout/crash must
        # never make this order look like a safely refreshable unused quote.
        db.session.commit();db.session.refresh(payment)
    suffix=''.join(chr(97+value%26) for value in hashlib.sha256(str(payment.id).encode()).digest()[:8])
    created=create_checkout(api_key=key,mode='payment',
        line_items=[{'price_data':{'currency':'usd','unit_amount':payment.amount_cents,
            'product_data':{'name':f'Restoration lead offer #{offer_id}'}},'quantity':1}],
        client_reference_id=str(payment.id),
        integration_identifier='restoration-market-'+suffix,
        expires_at=int(aware(payment.quote_expires_at).timestamp()),
        metadata={'payment_id':str(payment.id),'contractor_id':str(contractor.id),
                  'benchmark_id':str(payment.market_benchmark_id),'quote_version':str(payment.quote_version)},
        success_url=origin+'/contractor/billing?returned=1',cancel_url=origin+'/contractor/billing',
        idempotency_key=f'lead-payment:{payment.id}:v{payment.quote_version}')
    db.session.execute(update(Payment).where(Payment.id==payment.id,Payment.status=='creating',
        Payment.session_id.is_(None)).values(session_id=created['id'],status='open'))
    db.session.commit();db.session.refresh(payment)
    if payment.status != 'open' or payment.session_id != created['id']:
        return redirect('/contractor/billing',code=303)
    return redirect(created['url'],code=303)


@billing.post('/contractor/payments/<int:payment_id>/reconcile')
@contractor_required
def reconcile_checkout(contractor, payment_id):
    from app import db, Payment
    from checkout_reconciliation import configuration, reconcile_payment
    require_csrf()
    payment=Payment.query.filter_by(id=payment_id,contractor_id=contractor.id).first()
    if not payment:
        abort(404)
    key, mode=configuration()
    if payment.mode != mode:
        abort(409,'This order belongs to a different Stripe environment.')
    try:
        outcome=reconcile_payment(payment,api_key=key)
        db.session.commit()
    except ValueError:
        db.session.rollback()
        abort(409,'Checkout could not be verified. Its payment history was preserved.')
    except Exception:
        db.session.rollback()
        raise
    if outcome == 'expired':
        flash('The hosted checkout has expired. No replacement or charge was created.', 'success')
    elif outcome == 'unlinked':
        flash('The earlier checkout attempt needs provider reconciliation before it can be replaced.', 'notice')
    else:
        flash('Checkout status checked. Payment still requires a verified payment notification.', 'notice')
    return redirect(url_for('billing.overview'),code=303)


@billing.post('/webhooks/stripe')
def stripe_webhook():
    import stripe
    from app import db, Payment, ProviderEvent, Contractor, CheckoutQuoteHistory
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
    if kind not in ('checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed','checkout.session.expired','charge.refunded'):
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
                retired=CheckoutQuoteHistory.query.filter_by(session_id=obj['id']).first()
                if retired:
                    from checkout_reconciliation import validate_session
                    try:
                        validate_session(retired,{**obj,'livemode':event['livemode']})
                    except ValueError:
                        abort(400,'Retired checkout details do not match the original quote.')
                    if kind!='checkout.session.expired' or obj.get('status')!='expired' or obj.get('payment_status')!='unpaid':
                        abort(409,'An earlier retired checkout requires provider review.')
                    db.session.commit()
                    return '',204
                # A signed callback can arrive before the session-create response.
                reference=obj.get('metadata',{}).get('payment_id','')
                if isinstance(reference,str) and reference.isdigit() and len(reference)<12:
                    payment=Payment.query.filter_by(id=int(reference),session_id=None,status='creating').with_for_update().first()
            if not payment:
                abort(409,'Checkout has not been linked yet.')
            if (payment.mode != ('live' if event.get('livemode') else 'test') or obj.get('mode') != 'payment'
                or obj.get('amount_total') != payment.amount_cents or obj.get('currency') != payment.currency
                or obj.get('metadata',{}).get('payment_id') != str(payment.id)
                or obj.get('metadata',{}).get('contractor_id') != str(payment.contractor_id)
                or obj.get('metadata',{}).get('quote_version','1') != str(payment.quote_version)):
                abort(400,'Payment details do not match the stored order.')
            if payment.market_benchmark_id and obj.get('metadata',{}).get('benchmark_id')!=str(payment.market_benchmark_id):
                abort(400,'Market quote does not match the order.')
            if kind=='checkout.session.expired':
                if obj.get('status') != 'expired' or obj.get('payment_status') != 'unpaid':
                    abort(400,'Invalid checkout expiration state.')
                if payment.status in ('creating','open'):
                    db.session.execute(update(Payment).where(
                        Payment.id==payment.id,Payment.status.in_(('creating','open')),
                    ).values(session_id=obj['id'],status='expired'))
                db.session.commit()
                return '',204
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
            if payment.mode != ('live' if event.get('livemode') else 'test'):
                abort(400,'Payment environment mismatch.')
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

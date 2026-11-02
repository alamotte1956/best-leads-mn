"""Resend email and Twilio SMS outbox. Provider uncertainty is never auto-retried."""
import json
import os
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from sqlalchemy import update, func, or_
from flask import Blueprint, request, abort

communications = Blueprint('communications', __name__)


def email_test_settings():
    """An invalid test allowlist blocks all email; it never enables normal mode."""
    enabled = os.environ.get('EMAIL_TEST_ONLY', '').lower() == 'true'
    values = {item.strip().lower() for item in os.environ.get('EMAIL_TEST_RECIPIENTS', '').split(',')}
    valid = bool(values) and all(re.fullmatch(r'[^\s<>@,]+@[^\s<>@,]+\.[^\s<>@,]+', value) for value in values)
    return enabled, sorted(values) if valid else []


def email_recipient_allowed(recipient):
    testing, allowed = email_test_settings()
    return not testing or (recipient or '').strip().lower() in allowed


def queue_email(key, email, subject, body):
    from app import db, Delivery
    if email:
        db.session.add(Delivery(event_key=key,channel='email',recipient=email,
                                subject=subject,body=body))


def queue_offer(offer, contractor):
    from app import db, Delivery
    from notification_preferences import lead_alert_enabled
    from lead_choice import offer_description
    lead_type = offer_description(offer)
    body = lead_type + ' A restoration lead offer is available. Sign in to your contractor dashboard to review it. Availability expires after 15 minutes.'
    if contractor.email and lead_alert_enabled(contractor.id,'email'):
        db.session.add(Delivery(event_key=f'offer:{offer.id}:email',channel='email',
            recipient=contractor.email,subject='New restoration lead offer',body=body,
            contractor_id=contractor.id,offer_id=offer.id))
    if lead_alert_enabled(contractor.id,'sms'):
        db.session.add(Delivery(event_key=f'offer:{offer.id}:sms',channel='sms',recipient=contractor.phone,
            subject='Lead offer',body=body+' Reply STOP to opt out.',contractor_id=contractor.id,offer_id=offer.id))


def resend_email(delivery):
    if not email_recipient_allowed(delivery.recipient):
        raise ValueError('Recipient is outside the temporary email test allowlist')
    key = os.environ.get('RESEND_API_KEY','')
    sender = os.environ.get('RESEND_FROM_EMAIL','')
    if not key or not sender:
        raise RuntimeError('Resend is not configured')
    testing, _ = email_test_settings()
    subject = '[TEST] ' + delivery.subject if testing else delivery.subject
    body = 'TEST MESSAGE: This email is part of a website test.\n\n' + delivery.body if testing else delivery.body
    payload = json.dumps({'from':sender,'to':[delivery.recipient],
                          'subject':subject,'text':body,
                          'tags':[{'name':'delivery_id','value':str(delivery.id)}]}).encode()
    req = Request('https://api.resend.com/emails',data=payload,method='POST',headers={
        'Authorization':'Bearer '+key,'Content-Type':'application/json',
        'Accept':'application/json',
        'User-Agent':'RestorationContractorsMN/1.0 (+https://www.restorationcontractorsmn.com)',
        'Idempotency-Key':delivery.event_key})
    with urlopen(req,timeout=20) as response:
        return json.load(response)['id']


def twilio_sms(delivery):
    from twilio.rest import Client
    from twilio.http.http_client import TwilioHttpClient
    sid = os.environ.get('TWILIO_ACCOUNT_SID','')
    token = os.environ.get('TWILIO_AUTH_TOKEN','')
    service = os.environ.get('TWILIO_MESSAGING_SERVICE_SID','')
    callback = os.environ.get('TWILIO_STATUS_WEBHOOK_URL','')
    parts=urlsplit(callback)
    if not all((sid,token,service,callback)) or parts.scheme!='https' or not parts.netloc or parts.query or parts.fragment:
        raise RuntimeError('Twilio is not configured')
    from app import normalize_sms_phone
    number = normalize_sms_phone(delivery.recipient)
    if not number:
        raise ValueError('Invalid destination')
    client = Client(sid,token,http_client=TwilioHttpClient(timeout=20,max_retries=0))
    return client.messages.create(to='+1'+number,body=delivery.body,
        messaging_service_sid=service,status_callback=callback+'?delivery_id='+str(delivery.id)).sid


def deliver_pending(limit=20):
    from app import db, Delivery, Contractor, Lead, LeadOffer, ContractorAccountEvent, ConsumerRequestUpdate, contractor_sms_eligible
    from national_coverage import market_eligible
    from contractor_account_notifications import account_notice_current
    from consumer_requests import request_update_current
    from notification_preferences import lead_alert_enabled
    result = {'sent':0,'suppressed':0,'uncertain':0,'disabled':0,'cancelled':0}
    ready=[]
    for channel,flag,required in (
        ('email','EMAIL_SENDING_ENABLED',('RESEND_API_KEY','RESEND_FROM_EMAIL')),
        ('sms','SMS_SENDING_ENABLED',('TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_MESSAGING_SERVICE_SID','TWILIO_STATUS_WEBHOOK_URL'))):
        if os.environ.get(flag,'').lower()=='true' and all(os.environ.get(name) for name in required):
            ready.append(channel)
    # Disabled/unconfigured SMS must never occupy every batch slot and starve
    # the email-only launch. Unknown channels are also excluded, failing closed.
    result['disabled']=Delivery.query.filter(Delivery.status=='pending',~Delivery.channel.in_(ready)).count()
    eligible=Delivery.query.filter(Delivery.status=='pending',Delivery.channel.in_(ready))
    testing, allowed = email_test_settings()
    if testing:
        permitted=or_(Delivery.channel!='email',func.lower(func.trim(Delivery.recipient)).in_(allowed))
        result['disabled'] += eligible.filter(~permitted).count()
        eligible=eligible.filter(permitted)
    rows=eligible.order_by(
        Delivery.id).limit(min(max(limit,1),100)).all()
    for row in rows:
        flag = 'EMAIL_SENDING_ENABLED' if row.channel == 'email' else 'SMS_SENDING_ENABLED'
        if os.environ.get(flag,'').lower() != 'true':
            result['disabled'] += 1
            continue
        required = ('RESEND_API_KEY','RESEND_FROM_EMAIL') if row.channel=='email' else (
            'TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_MESSAGING_SERVICE_SID','TWILIO_STATUS_WEBHOOK_URL')
        if not all(os.environ.get(name) for name in required):
            result['disabled'] += 1
            continue
        account_event = ContractorAccountEvent.query.filter_by(delivery_id=row.id).first()
        if account_event and not account_notice_current(row, account_event):
            db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='pending').values(status='cancelled'))
            db.session.commit();result['cancelled'] += 1
            continue
        consumer_event = ConsumerRequestUpdate.query.filter_by(delivery_id=row.id).first()
        if consumer_event and not request_update_current(row, consumer_event):
            db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='pending').values(status='cancelled'))
            db.session.commit();result['cancelled'] += 1
            continue
        if row.offer_id:
            offer = db.session.get(LeadOffer,row.offer_id)
            contractor = db.session.get(Contractor,row.contractor_id)
            deadline = offer.expires_at if offer else None
            if deadline and deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if (not offer or offer.status != 'pending' or not deadline or deadline <= datetime.now(timezone.utc)
                    or not contractor or not contractor.active or not contractor.verified or contractor.is_test
                    or not market_eligible(contractor, db.session.get(Lead, offer.lead_id))
                    or not contractor.credential_review_current or not lead_alert_enabled(contractor.id,row.channel)
                    or (row.channel == 'sms' and not contractor_sms_eligible(contractor))):
                db.session.execute(update(Delivery).where(Delivery.id==row.id, Delivery.status=='pending').values(status='suppressed'));db.session.commit();result['suppressed'] += 1
                continue
            row.recipient = contractor.email if row.channel == 'email' else contractor.phone
        if row.channel == 'email' and not email_recipient_allowed(row.recipient):
            db.session.commit();result['disabled'] += 1
            continue
        from email_delivery import email_suppressed
        if row.channel == 'email' and email_suppressed(row.recipient):
            db.session.execute(update(Delivery).where(Delivery.id==row.id, Delivery.status=='pending').values(status='suppressed'))
            db.session.commit();result['suppressed'] += 1
            continue
        claimed = db.session.execute(update(Delivery).where(Delivery.id==row.id,
            Delivery.status=='pending').values(status='sending')).rowcount
        db.session.commit()
        if claimed != 1:
            continue
        try:
            if row.offer_id:
                current_offer = db.session.get(LeadOffer, row.offer_id)
                current_contractor = db.session.get(Contractor, row.contractor_id)
                if (not current_offer or current_offer.status != 'pending' or not current_contractor
                        or not market_eligible(current_contractor, db.session.get(Lead, current_offer.lead_id))):
                    db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='suppressed'))
                    db.session.commit();result['suppressed'] += 1
                    continue
            if row.offer_id and not lead_alert_enabled(row.contractor_id,row.channel):
                db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='suppressed'))
                db.session.commit();result['suppressed'] += 1
                continue
            if consumer_event and not request_update_current(row, consumer_event):
                db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='cancelled'))
                db.session.commit();result['cancelled'] += 1
                continue
            if account_event and not account_notice_current(row, account_event):
                db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='cancelled'))
                db.session.commit();result['cancelled'] += 1
                continue
            if row.contractor_id and not account_event:
                contractor=db.session.get(Contractor,row.contractor_id)
                if contractor:
                    db.session.refresh(contractor)
                if not contractor or not contractor.active or not contractor.verified or not contractor.credential_review_current or (row.channel=='sms' and not contractor_sms_eligible(contractor)):
                    db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='suppressed'))
                    db.session.commit();result['suppressed'] += 1
                    continue
            if row.channel == 'email' and email_suppressed(row.recipient):
                db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='suppressed'))
                db.session.commit();result['suppressed'] += 1
                continue
            if row.channel == 'email' and not email_recipient_allowed(row.recipient):
                db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='pending'))
                db.session.commit();result['disabled'] += 1
                continue
            provider_id = resend_email(row) if row.channel == 'email' else twilio_sms(row)
            db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(provider_id=provider_id,status='sent'))
            db.session.commit();result['sent'] += 1
        except Exception:
            # A timeout can occur AFTER provider acceptance. Reconcile before retrying.
            db.session.rollback()
            db.session.execute(update(Delivery).where(Delivery.id==row.id,
                Delivery.status=='sending').values(status='uncertain'))
            db.session.commit();result['uncertain'] += 1
    return result


@communications.post('/webhooks/twilio/status')
def twilio_status():
    from app import db, Delivery
    from twilio_security import validate_twilio_request
    public_url = os.environ.get('TWILIO_STATUS_WEBHOOK_URL','')
    if not public_url:
        abort(503)
    delivery_id=request.args.get('delivery_id')
    if delivery_id:
        if not delivery_id.isdigit() or len(delivery_id)>12 or len(request.args)!=1:
            abort(400)
        public_url += '?delivery_id='+delivery_id
    if not validate_twilio_request(public_url,request.form,request.headers.get('X-Twilio-Signature','')):
        abort(403)
    message_sid=request.form.get('MessageSid','')
    if not message_sid.startswith('SM') or len(message_sid)>100:
        abort(400)
    status = request.form.get('MessageStatus')
    if status not in ('delivered','undelivered','failed'):
        return '',204
    from sqlalchemy import or_
    condition = Delivery.provider_id==request.form.get('MessageSid')
    if delivery_id:
        condition = (Delivery.id==int(delivery_id)) & or_(Delivery.provider_id.is_(None),Delivery.provider_id==request.form.get('MessageSid'))
    db.session.execute(update(Delivery).where(condition,
        Delivery.channel=='sms', Delivery.status.in_(('sent','sending'))).values(status=status,provider_id=request.form.get('MessageSid')))
    db.session.commit()
    return '',204

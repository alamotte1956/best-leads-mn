"""Private same-browser homeowner tracking and transactional status notices."""
import re
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, session
from sqlalchemy import select, update

consumer_requests = Blueprint('consumer_requests', __name__)
PRIVATE_HEADERS = {'Cache-Control':'private, no-store, max-age=0',
                   'Referrer-Policy':'no-referrer', 'X-Robots-Tag':'noindex, nofollow'}
STATUS_COPY = {
    'pending': ('Looking for a contractor', 'Your request is saved for review and matching. Availability and response times vary.'),
    'accepted': ('A contractor accepted your request', 'You can contact the business below to discuss your project. This is not a confirmed appointment.'),
    'needs_review': ('Your match needs review', 'The previously matched account is not currently eligible. Our team needs to review the match. No replacement contractor is confirmed.'),
    'closed': ('Your request is closed', 'Matching has stopped for this request. This status does not confirm that restoration work is complete.'),
    'cancelled': ('Your request is cancelled', 'Matching has stopped for this request. Contact your contractor directly about any project arrangements.'),
    'review': ('Your request is under review', 'Our team needs to review the current request status. No appointment is confirmed here.'),
}


def define_consumer_updates(db):
    class ConsumerRequestUpdate(db.Model):
        __tablename__ = 'consumer_request_updates'
        id = db.Column(db.Integer, primary_key=True)
        lead_id = db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'), db.ForeignKey('leads.id'), nullable=False, index=True)
        offer_id = db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'), db.ForeignKey('lead_offers.id'))
        delivery_id = db.Column(db.Integer, db.ForeignKey('provider_deliveries.id'), unique=True, nullable=False)
        status = db.Column(db.String(20), nullable=False)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        __table_args__ = (db.UniqueConstraint('lead_id','status',name='consumer_update_lead_status'),
            db.CheckConstraint("status in ('accepted','closed','cancelled')",name='consumer_update_status'))
    return ConsumerRequestUpdate


def remember_request(lead_id, now=None):
    session['last_lead_reference'] = lead_id
    session['last_lead_status_at'] = (now or datetime.now(timezone.utc)).isoformat()


def owned_request(now=None):
    """No URL, email, phone or user-supplied lead ID grants access."""
    from app import db, Lead
    lead_id = session.get('last_lead_reference')
    if type(lead_id) is not int or not 0 < lead_id <= 2**63-1:
        return None
    try:
        issued = datetime.fromisoformat(session.get('last_lead_status_at',''))
        if issued.tzinfo is None:
            return None
        age = (now or datetime.now(timezone.utc)) - issued.astimezone(timezone.utc)
        if not timedelta(0) <= age < timedelta(days=7):
            return None
    except (ValueError, TypeError):
        return None
    return db.session.get(Lead, lead_id)


def request_status(lead):
    from app import db, LeadOffer, Contractor
    if lead.status in ('Closed','Cancelled'):
        return lead.status.lower(), None, None
    if lead.status != 'New':
        return 'review', None, None
    offers = LeadOffer.query.filter_by(lead_id=lead.id,status='accepted').order_by(LeadOffer.id.desc()).limit(2).all()
    if not offers:
        return 'pending', None, None
    if len(offers) != 1:
        return 'needs_review', None, None
    offer = offers[0]
    contractor = db.session.get(Contractor, offer.contractor_id)
    if (not contractor or not contractor.active or not contractor.verified or contractor.is_test
            or not contractor.credential_review_current):
        return 'needs_review', None, None
    return 'accepted', contractor, offer


@consumer_requests.get('/request-status')
def status():
    lead = owned_request()
    state, contractor, offer = request_status(lead) if lead else (None,None,None)
    phone_digits = re.sub(r'[^0-9]','',contractor.phone or '') if contractor else ''
    return render_template('request_status.html',lead=lead,state=state,
        status_copy=STATUS_COPY.get(state),contractor=contractor,phone_digits=phone_digits), 200, PRIVATE_HEADERS


def queue_request_update(lead, state, offer_id=None):
    """Caller owns the request lock/transaction. Never sends or commits."""
    from app import db, Delivery, ConsumerRequestUpdate
    if state not in ('accepted','closed','cancelled'):
        raise ValueError('Unsupported consumer status notification.')
    if not lead.email:
        return None
    previous = select(ConsumerRequestUpdate.delivery_id).where(ConsumerRequestUpdate.lead_id == lead.id)
    db.session.execute(update(Delivery).where(Delivery.id.in_(previous),Delivery.status=='pending').values(status='cancelled'))
    title, message = STATUS_COPY[state]
    if state == 'accepted':
        message = 'A contractor has accepted the request. This is not a confirmed appointment. Business contact details are available on your private status page.'
    delivery = Delivery(event_key=f'lead:{lead.id}:update:{state}',channel='email',recipient=lead.email,
        subject='Restoration request update',body=f'Your restoration request #{lead.id}: {title.lower()}. '
        f'{message} View current details at https://RestorationContractorsMN.com/request-status in the original browser '
        'used to submit your request. This private status access lasts seven days. No charge has been made by this update.')
    db.session.add(delivery); db.session.flush()
    db.session.add(ConsumerRequestUpdate(lead_id=lead.id,offer_id=offer_id,delivery_id=delivery.id,status=state))
    return delivery


def request_update_current(delivery, event):
    from app import db, Lead, ConsumerRequestUpdate
    from email_delivery import canonical_email
    if delivery.channel != 'email' or delivery.contractor_id is not None or delivery.offer_id is not None:
        return False
    latest = ConsumerRequestUpdate.query.filter_by(lead_id=event.lead_id).order_by(ConsumerRequestUpdate.id.desc()).first()
    lead = db.session.get(Lead,event.lead_id)
    if (not latest or latest.id != event.id or not lead
            or canonical_email(lead.email) != canonical_email(delivery.recipient)):
        return False
    state, contractor, offer = request_status(lead)
    return state == event.status and (state != 'accepted' or offer.id == event.offer_id)

"""Transactional administrator account decisions and their Resend notices."""
import uuid
from sqlalchemy import select, update

NOTICES = {
    'approved': (
        'Your contractor account is approved',
        'Your Restoration Contractors MN account has been approved. '
        'Create or reset your own password at https://www.restorationcontractorsmn.com/contractor/forgot-password. '
        'A private, single-use link will be emailed to the address on your approved account. '
        'If you already have a password, sign in at https://www.restorationcontractorsmn.com/contractor/login. '
        'Approval does not guarantee lead availability. No charge has been made.'),
    'deactivated': (
        'Your contractor account is inactive',
        'Your Restoration Contractors MN account has been deactivated. '
        'You cannot access contractor offers or start new lead purchases while the account is inactive. '
        'Contact the team through RestorationContractorsMN.com for assistance. '
        'Existing payment history is retained.'),
    'review_rejected': (
        'Your contractor application needs attention',
        'Your license and insurance review did not receive approval. '
        'Your Restoration Contractors MN account is inactive and cannot access offers or start lead purchases. '
        'Contact the team through RestorationContractorsMN.com to discuss the information needed for review. '
        'Submitting information does not automatically approve or activate an account.'),
}


def define_account_events(db):
    class ContractorAccountEvent(db.Model):
        __tablename__ = 'contractor_account_events'
        id = db.Column(db.Integer, primary_key=True)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False, index=True)
        delivery_id = db.Column(db.Integer, db.ForeignKey('provider_deliveries.id'), unique=True, nullable=False)
        review_id = db.Column(db.Integer, db.ForeignKey('contractor_credential_reviews.id'))
        status = db.Column(db.String(30), nullable=False)
        actor = db.Column(db.String(30), nullable=False, default='administrator')
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        __table_args__ = (db.CheckConstraint(
            "status in ('approved','deactivated','review_rejected')", name='contractor_account_event_status'),)
    return ContractorAccountEvent


def queue_account_notice(contractor, status, review_id=None):
    """Caller owns the account lock and transaction; never commits or sends."""
    from app import db, Delivery, ContractorAccountEvent
    subject, body = NOTICES[status]
    previous = select(ContractorAccountEvent.delivery_id).where(
        ContractorAccountEvent.contractor_id == contractor.id)
    db.session.execute(update(Delivery).where(Delivery.id.in_(previous),
        Delivery.status == 'pending').values(status='cancelled'))
    delivery = Delivery(event_key='account-status:'+uuid.uuid4().hex, channel='email',
        recipient=contractor.email, subject=subject, body=body, contractor_id=contractor.id)
    db.session.add(delivery); db.session.flush()
    event = ContractorAccountEvent(contractor_id=contractor.id, delivery_id=delivery.id,
        status=status, review_id=review_id)
    db.session.add(event)
    return event


def account_notice_current(delivery, event):
    """Recheck the recorded decision before allowing an inactive-account notice."""
    from app import Contractor, ContractorAccountEvent
    from email_delivery import canonical_email
    if (delivery.channel != 'email' or delivery.offer_id is not None
            or event.contractor_id != delivery.contractor_id):
        return False
    latest = ContractorAccountEvent.query.filter_by(contractor_id=event.contractor_id).order_by(
        ContractorAccountEvent.id.desc()).first()
    contractor = Contractor.query.filter_by(id=event.contractor_id).populate_existing().first()
    if (not latest or latest.id != event.id or not contractor or contractor.is_test
            or canonical_email(contractor.email) != canonical_email(delivery.recipient)):
        return False
    if event.status == 'approved':
        return bool(contractor.active and contractor.verified and contractor.credential_review_current)
    if event.status == 'review_rejected':
        from credential_verification import latest_review
        review = latest_review(contractor)
        return bool(not contractor.active and not contractor.verified and review and review.decision == 'rejected')
    return event.status == 'deactivated' and not contractor.active

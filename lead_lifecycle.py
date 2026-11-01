"""Shared atomic matching termination; callers authenticate and own the transaction."""
from flask import abort
from sqlalchemy import update


def define_lead_status_events(db):
    class LeadStatusEvent(db.Model):
        __tablename__ = 'lead_status_events'
        id = db.Column(db.Integer, primary_key=True)
        lead_id = db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'), db.ForeignKey('leads.id'), nullable=False, index=True)
        previous_status = db.Column(db.String(50), nullable=False)
        new_status = db.Column(db.String(50), nullable=False)
        actor = db.Column(db.String(20), nullable=False)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        __table_args__ = (
            db.CheckConstraint("new_status in ('Closed','Cancelled')",name='lead_status_event_target'),
            db.CheckConstraint("actor in ('administrator','consumer')",name='lead_status_event_actor'),
        )
    return LeadStatusEvent


def end_matching(lead_id, target, *, actor, allow_same=False):
    """Keep offer cancellation, audit and email in the caller's transaction."""
    from app import db, Lead, LeadOffer, LeadStatusEvent
    from consumer_requests import queue_request_update
    if type(lead_id) is not int or lead_id <= 0 or target not in ('Closed','Cancelled'):
        raise ValueError('Invalid matching termination.')
    if actor not in ('administrator','consumer') or (actor == 'consumer' and target != 'Cancelled'):
        raise ValueError('Invalid request actor.')
    if db.session.get_bind().dialect.name == 'postgresql':
        from sequential_matching_lock import lock_lead_for_matching
        lock_lead_for_matching(db.session, lead_id)
    lead = Lead.query.filter_by(id=lead_id).populate_existing().with_for_update().first()
    if lead is None:
        abort(404)
    if allow_same and lead.status == target:
        return False
    if lead.status != 'New':
        abort(409, 'Only an open request can be closed or cancelled.')
    changed = db.session.execute(update(Lead).where(Lead.id == lead_id,
        Lead.status == 'New').values(status=target)).rowcount
    if changed != 1:
        db.session.refresh(lead)
        if allow_same and lead.status == target:
            return False
        abort(409, 'The request changed. Refresh its status before trying again.')
    db.session.execute(update(LeadOffer).where(LeadOffer.lead_id == lead_id,
        LeadOffer.status == 'pending').values(status='cancelled'))
    db.session.add(LeadStatusEvent(lead_id=lead_id,previous_status='New',new_status=target,actor=actor))
    queue_request_update(lead, target.lower())
    return True

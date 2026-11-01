"""Authenticated contractor coverage settings and administrative lead controls."""
from functools import wraps
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from national import administrator
from contractor_onboarding import require_csrf
from contractor_session_security import contractor_session_valid
from contractor_matching import contractor_matches

operations = Blueprint('operations', __name__)


def contractor_required(fn):
    @wraps(fn)
    def guarded(*args, **kwargs):
        from app import db, Contractor
        identifier = session.get('contractor_id')
        contractor = db.session.get(Contractor, identifier) if isinstance(identifier, int) and not isinstance(identifier, bool) else None
        if not contractor_session_valid(dict(session), contractor):
            return redirect(url_for('contractor_login'))
        return fn(contractor, *args, **kwargs)
    return guarded


@operations.route('/contractor/settings', methods=['GET', 'POST'])
@contractor_required
def settings(contractor):
    from app import db, ContractorService, valid_zip
    error = None
    if request.method == 'POST':
        require_csrf()
        raw = request.form.get('zip_codes', '')
        zips = list(dict.fromkeys(part.strip() for part in raw.split(',') if part.strip()))
        if not zips or len(raw) > 500 or not all(valid_zip(value) for value in zips):
            error = 'Enter five-digit ZIP codes separated by commas, up to 500 characters.'
        if error is None:
            # Coverage belongs to the authenticated account. No account ID is accepted.
            contractor.zip_codes = ','.join(zips)
            contractor.service_radius_zip = zips[0]
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            flash('Your service-area ZIP codes have been updated.', 'success')
            return redirect(url_for('operations.settings'))
    services = ContractorService.query.filter_by(contractor_id=contractor.id).all()
    return render_template('contractor_settings.html', contractor=contractor,
                           services=services, error=error), 400 if error else 200


@operations.get('/admin/leads/<int:lead_id>')
@administrator
def lead_review(lead_id):
    from app import db, Lead, LeadOffer, Contractor, ContractorService
    lead = db.session.get(Lead, lead_id)
    if lead is None:
        abort(404)
    service_map = {}
    for service in ContractorService.query.all():
        service_map.setdefault(service.contractor_id, []).append(service.service_name)
    candidates = []
    if lead.status == 'New':
        candidates = [contractor for contractor in Contractor.query.filter_by(active=True, verified=True, is_test=False).all()
                      if contractor_matches(contractor, lead, service_map.get(contractor.id, []))]
    offers = db.session.query(LeadOffer, Contractor).join(Contractor, Contractor.id == LeadOffer.contractor_id).filter(LeadOffer.lead_id == lead_id).order_by(LeadOffer.id.desc()).all()
    from app import ConsumerRequestUpdate, Delivery, LeadStatusEvent
    consumer_updates = db.session.query(ConsumerRequestUpdate, Delivery).join(
        Delivery, Delivery.id == ConsumerRequestUpdate.delivery_id).filter(
        ConsumerRequestUpdate.lead_id == lead_id).order_by(ConsumerRequestUpdate.id.desc()).limit(20).all()
    status_events = LeadStatusEvent.query.filter_by(lead_id=lead_id).order_by(LeadStatusEvent.id.desc()).limit(20).all()
    return render_template('lead_review.html', lead=lead, candidates=candidates, offers=offers,
        consumer_updates=consumer_updates, status_events=status_events)


@operations.post('/admin/leads/<int:lead_id>/status')
@administrator
def lead_status(lead_id):
    from app import db
    from lead_lifecycle import end_matching
    require_csrf()
    target = request.form.get('status')
    if target not in ('Cancelled', 'Closed'):
        abort(400, 'Choose Cancelled or Closed.')
    try:
        end_matching(lead_id,target,actor='administrator')
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    flash('Request marked ' + target.lower() + '. Pending offers were cancelled.', 'success')
    return redirect(url_for('operations.lead_review', lead_id=lead_id))

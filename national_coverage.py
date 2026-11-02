"""Additive state coverage applications. Approval never opens a disabled market."""
import json
from datetime import date, datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from national import administrator
from national_markets import STATES, code_enabled
from contractor_onboarding import require_csrf
from operations import contractor_required

coverage = Blueprint('coverage', __name__)


def define_national_coverage(db):
    class ContractorOrigin(db.Model):
        __tablename__ = 'contractor_origins'
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), primary_key=True)
        state_code = db.Column(db.String(2), nullable=False)
        __table_args__ = (db.CheckConstraint("state_code in ('MN','TX','FL','NC','GA','WI','IN')"),)

    class LeadMarket(db.Model):
        __tablename__ = 'lead_markets'
        lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), primary_key=True)
        state_code = db.Column(db.String(2), nullable=False, index=True)
        intake_brand = db.Column(db.String(3), nullable=False, default='MN')
        __table_args__ = (db.CheckConstraint("state_code in ('MN','TX','FL','NC','GA','WI','IN')"),
                         db.CheckConstraint("intake_brand in ('MN','USA')",name='lead_market_intake_brand'))

    class MarketApplication(db.Model):
        __tablename__ = 'contractor_market_applications'
        id = db.Column(db.Integer, primary_key=True)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False, index=True)
        state_code = db.Column(db.String(2), nullable=False, index=True)
        zip_codes = db.Column(db.String(500), nullable=False)
        services_json = db.Column(db.Text, nullable=False)
        license_number = db.Column(db.String(100), nullable=False)
        applicant_notes = db.Column(db.Text, nullable=False)
        status = db.Column(db.String(20), nullable=False, default='pending')
        pending_key = db.Column(db.String(50), unique=True)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        __table_args__ = (db.CheckConstraint("state_code in ('MN','TX','FL','NC','GA','WI','IN')", name='market_application_state'),
                         db.CheckConstraint("status in ('pending','approved','rejected')"))

        @property
        def services(self):
            return json.loads(self.services_json)

    class MarketReview(db.Model):
        __tablename__ = 'contractor_market_reviews'
        id = db.Column(db.Integer, primary_key=True)
        application_id = db.Column(db.Integer, db.ForeignKey('contractor_market_applications.id'), unique=True, nullable=False)
        decision = db.Column(db.String(20), nullable=False)
        license_reference = db.Column(db.String(255), nullable=False)
        insurance_reference = db.Column(db.String(255), nullable=False)
        scope_reference = db.Column(db.String(255), nullable=False)
        license_expires = db.Column(db.Date)
        insurance_expires = db.Column(db.Date)
        private_notes = db.Column(db.Text, nullable=False)
        response_message = db.Column(db.String(1000), nullable=False)
        reviewed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        __table_args__ = (db.CheckConstraint("decision in ('approved','rejected')"),)
    return LeadMarket, MarketApplication, MarketReview, ContractorOrigin


@coverage.after_request
def private(response):
    from consumer_requests import PRIVATE_HEADERS
    response.headers.update(PRIVATE_HEADERS)
    return response


def lead_state(lead):
    """Missing sidecar means legacy Minnesota; an unknown explicit state fails closed."""
    from app import LeadMarket
    from sqlalchemy import inspect
    inspected = inspect(lead, raiseerr=False)
    if inspected is not None and hasattr(inspected, 'mapper'):
        row = LeadMarket.query.filter_by(lead_id=lead.id).first() if lead.id else None
        return row.state_code if row else 'MN'
    return getattr(lead, 'state_code', 'MN')


def status_origin(lead):
    from app import db,LeadMarket
    row=db.session.get(LeadMarket,lead.id)
    # Preserve the original browser/site link even if a location review corrects
    # the state. Never construct an email URL from untrusted Host headers.
    return 'https://RestorationContractorsUSA.com' if row and row.intake_brand=='USA' else 'https://RestorationContractorsMN.com'


def latest_application(contractor_id, state_code):
    from app import MarketApplication
    return MarketApplication.query.filter_by(contractor_id=contractor_id, state_code=state_code).order_by(MarketApplication.id.desc()).first()


def approved_coverage(contractor_id, state_code, today=None):
    from app import db, MarketReview, Contractor
    contractor=db.session.get(Contractor,contractor_id)
    if (not contractor or not contractor.active or not contractor.verified or contractor.is_test
            or not contractor.credential_review_current):
        return None
    row = latest_application(contractor_id, state_code)
    if not row or row.status != 'approved':
        return None
    review = MarketReview.query.filter_by(application_id=row.id).first()
    today = today or datetime.now(timezone.utc).date()
    if not (review and review.decision == 'approved' and review.license_expires and review.insurance_expires
            and min(review.license_expires, review.insurance_expires) >= today):
        return None
    return row


def market_eligible(contractor, lead):
    if contractor is None or lead is None:
        return False
    if (contractor.active is not True or contractor.verified is not True or contractor.is_test is not False
            or not getattr(contractor,'credential_review_current',True)):
        return False
    state = lead_state(lead)
    if not code_enabled(state):
        return False
    if state == 'MN' and minnesota_origin(contractor):
        return True
    row = approved_coverage(contractor.id, state)
    from contractor_matching import normalize_service
    return bool(row and lead.zip_code in row.zip_codes.split(',') and
                normalize_service(lead.service_needed) in {normalize_service(s) for s in row.services})


def minnesota_origin(contractor):
    from app import ContractorOrigin
    from sqlalchemy import inspect
    inspected=inspect(contractor,raiseerr=False)
    if inspected is None or not hasattr(inspected,'mapper'):
        return getattr(contractor,'origin_state','MN')=='MN'
    origin=ContractorOrigin.query.filter_by(contractor_id=contractor.id).first()
    return not origin or origin.state_code=='MN'


def application_history(contractor_id):
    from app import MarketApplication, MarketReview
    return MarketApplication.query.outerjoin(MarketReview, MarketReview.application_id == MarketApplication.id).add_entity(
        MarketReview).filter(MarketApplication.contractor_id == contractor_id).order_by(MarketApplication.id.desc()).limit(50).all()


@coverage.route('/contractor/markets', methods=['GET', 'POST'])
@contractor_required
def apply(contractor):
    from app import db, Contractor, MarketApplication, valid_zip
    from service_catalog import SERVICES
    error = None
    if request.method == 'POST':
        require_csrf()
        state = request.form.get('state_code', '')
        raw_zips = request.form.get('zip_codes', '')
        zips = list(dict.fromkeys(z.strip() for z in raw_zips.split(',') if z.strip()))
        services = list(dict.fromkeys(request.form.getlist('services')))
        license_number = request.form.get('license_number', '').strip()
        notes = request.form.get('applicant_notes', '').strip()
        if state not in {s[0] for s in STATES.values()} or (state=='MN' and minnesota_origin(contractor)):
            error = 'Choose one of the six future states. Minnesota coverage stays in your existing settings.'
        elif not zips or len(raw_zips) > 500 or not all(valid_zip(z) for z in zips):
            error = 'Enter five-digit ZIP codes separated by commas, up to 500 characters.'
        elif not services or any(s not in SERVICES for s in services):
            error = 'Choose at least one listed restoration service.'
        elif not license_number or len(license_number) > 100 or len(notes) > 2000:
            error = 'Enter the state license or registration identifier (up to 100 characters) and notes up to 2,000 characters.'
        elif request.form.get('review_required') != 'yes':
            error = 'Confirm that state coverage requires separate review and launch approval.'
        if error is None:
            try:
                # All requests for this contractor serialize on PostgreSQL; unique pending_key also covers races.
                Contractor.query.filter_by(id=contractor.id).with_for_update().one()
                if MarketApplication.query.filter_by(pending_key=f'{contractor.id}:{state}').first():
                    error = 'A request for this state is already awaiting review.'
                else:
                    db.session.add(MarketApplication(contractor_id=contractor.id, state_code=state,
                        zip_codes=','.join(zips), services_json=json.dumps(services), license_number=license_number,
                        applicant_notes=notes, status='pending', pending_key=f'{contractor.id}:{state}'))
                    db.session.commit()
                    flash('State coverage requested. Review and market launch approval are required before matching.', 'success')
                    return redirect(url_for('coverage.apply'), code=303)
            except IntegrityError:
                db.session.rollback()
                error = 'A request for this state is already awaiting review.'
        if error:
            db.session.rollback()
    return render_template('market_application.html', states=STATES, services=SERVICES, error=error,
        allow_mn=not minnesota_origin(contractor), history=application_history(contractor.id)), 400 if error else 200


@coverage.get('/admin/national/applications')
@administrator
def applications():
    from app import db, MarketApplication, Contractor
    rows = db.session.query(MarketApplication, Contractor).join(Contractor, Contractor.id == MarketApplication.contractor_id).order_by(
        (MarketApplication.status == 'pending').desc(), MarketApplication.id.desc()).limit(200).all()
    return render_template('market_applications.html', rows=rows)


@coverage.route('/admin/national/applications/<int:application_id>', methods=['GET', 'POST'])
@administrator
def review(application_id):
    from app import db, Contractor, MarketApplication, MarketReview
    from communications import queue_email
    row = db.get_or_404(MarketApplication, application_id)
    contractor = db.session.get(Contractor, row.contractor_id)
    error = None
    if request.method == 'POST':
        require_csrf()
        decision = request.form.get('decision', '')
        refs = {name: request.form.get(name, '').strip() for name in ('license_reference', 'insurance_reference', 'scope_reference')}
        notes = request.form.get('private_notes', '').strip()
        response = request.form.get('response_message', '').strip()
        license_expires = insurance_expires = None
        try:
            if decision not in ('approved', 'rejected') or not notes or len(notes) > 5000 or not response or len(response) > 1000:
                raise ValueError('Choose a decision, enter private notes (up to 5,000 characters) and an applicant message (up to 1,000 characters).')
            if any(len(value) > 255 for value in refs.values()):
                raise ValueError('Evidence references must be 255 characters or fewer.')
            if decision == 'approved':
                if not all(refs.values()) or request.form.get('state_scope_checked') != 'yes':
                    raise ValueError('Check state-specific license, insurance, service and ZIP coverage and record all three evidence references.')
                license_expires = date.fromisoformat(request.form.get('license_expires', ''))
                insurance_expires = date.fromisoformat(request.form.get('insurance_expires', ''))
                if min(license_expires, insurance_expires) < datetime.now(timezone.utc).date():
                    raise ValueError('Expired credentials cannot be approved.')
                if not contractor.active or not contractor.verified or contractor.is_test or not contractor.credential_review_current:
                    raise ValueError('Approve the contractor account and current credentials before approving another state.')
        except ValueError as exc:
            error = str(exc)
        if error is None:
            try:
                Contractor.query.filter_by(id=contractor.id).populate_existing().with_for_update().one()
                if decision == 'approved' and (not contractor.active or not contractor.verified or contractor.is_test
                        or not contractor.credential_review_current):
                    abort(409, 'The contractor account approval changed. Recheck credentials before approval.')
                row = MarketApplication.query.filter_by(id=application_id).populate_existing().with_for_update().one()
                if row.status != 'pending':
                    abort(409, 'This application has already been reviewed.')
                from sqlalchemy import update
                changed = db.session.execute(update(MarketApplication).where(MarketApplication.id == application_id,
                    MarketApplication.status == 'pending').values(status=decision, pending_key=None)).rowcount
                if changed != 1:
                    abort(409, 'This application has already been reviewed.')
                db.session.add(MarketReview(application_id=row.id, decision=decision, **refs,
                    license_expires=license_expires, insurance_expires=insurance_expires, private_notes=notes, response_message=response))
                queue_email(f'market-application:{row.id}:decision', contractor.email, 'State coverage review completed',
                    'Your state coverage request has been reviewed. Sign in to your contractor account to view the decision. State launch approval is separate.')
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            return redirect(url_for('coverage.review', application_id=application_id), code=303)
    result = MarketReview.query.filter_by(application_id=application_id).first()
    return render_template('market_review.html', row=row, contractor=contractor, review=result, error=error), 400 if error else 200


def national_report():
    from app import db, Lead, LeadMarket, Contractor, ContractorOrigin, MarketApplication, Payment, LeadOffer
    # Legacy leads and contractor accounts are Minnesota records, never reclassified by ZIP guesses.
    reports = {row[0]: dict(leads=0, open=0, contractors=0, pending=0, approved=0, revenue_cents=0, refunded_cents=0) for row in STATES.values()}
    for code, status, count in db.session.query(db.func.coalesce(LeadMarket.state_code, 'MN'), Lead.status, db.func.count(Lead.id)).outerjoin(
            LeadMarket, LeadMarket.lead_id == Lead.id).group_by(db.func.coalesce(LeadMarket.state_code, 'MN'), Lead.status):
        if code in reports:
            reports[code]['leads'] += count
            reports[code]['open'] += count if status == 'New' else 0
    mn_contractors=Contractor.query.outerjoin(ContractorOrigin,ContractorOrigin.contractor_id==Contractor.id).filter(
        db.or_(ContractorOrigin.state_code.is_(None),ContractorOrigin.state_code=='MN')).all()
    reports['MN']['contractors'] = len(mn_contractors)
    reports['MN']['approved'] = sum(bool(c.active and c.verified and not c.is_test and c.credential_review_current) for c in mn_contractors)
    reports['MN']['pending'] = sum(not c.active for c in mn_contractors)
    # Latest application per contractor/state prevents counting old approvals twice.
    latest = db.session.query(db.func.max(MarketApplication.id)).group_by(MarketApplication.contractor_id, MarketApplication.state_code)
    for row in MarketApplication.query.filter(MarketApplication.id.in_(latest)).all():
        report = reports[row.state_code]
        report['contractors'] += 1
        report['pending'] += row.status == 'pending'
        report['approved'] += bool(approved_coverage(row.contractor_id, row.state_code))
    for code, amount, refunded in db.session.query(db.func.coalesce(LeadMarket.state_code, 'MN'), db.func.sum(Payment.amount_cents), db.func.sum(Payment.refunded_cents)).join(
            LeadOffer, LeadOffer.id == Payment.offer_id).join(Lead, Lead.id == LeadOffer.lead_id).outerjoin(LeadMarket, LeadMarket.lead_id == Lead.id).filter(
            Payment.status.in_(('paid', 'refunded'))).group_by(db.func.coalesce(LeadMarket.state_code, 'MN')):
        if code in reports:
            reports[code]['revenue_cents'] = (amount or 0) - (refunded or 0)
            reports[code]['refunded_cents'] = refunded or 0
    return reports

"""Append-only manual credential reviews. No external verification is implied."""
from datetime import date, datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import update
from national import administrator
from contractor_onboarding import require_csrf

verification = Blueprint('verification', __name__)


def define_verification(db):
    class CredentialReview(db.Model):
        __tablename__ = 'contractor_credential_reviews'
        id = db.Column(db.Integer, primary_key=True)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False, index=True)
        decision = db.Column(db.String(20), nullable=False)
        license_number = db.Column(db.String(50), nullable=False)
        license_expires = db.Column(db.Date)
        insurance_expires = db.Column(db.Date)
        license_reference = db.Column(db.String(255), nullable=False)
        insurance_reference = db.Column(db.String(255), nullable=False)
        notes = db.Column(db.Text, nullable=False)
        reviewed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        __table_args__ = (db.CheckConstraint("decision in ('approved','rejected')", name='credential_review_decision'),)
    return CredentialReview


def latest_review(contractor):
    from app import CredentialReview
    return CredentialReview.query.filter_by(contractor_id=contractor.id).order_by(CredentialReview.id.desc()).first()


def review_valid(contractor, review, today=None):
    today = today or datetime.now(timezone.utc).date()
    return bool(review and review.decision == 'approved' and
        review.license_number == (contractor.license_number or '') and
        review.license_expires and review.license_expires >= today and
        review.insurance_expires and review.insurance_expires >= today)


def current_credentials(contractor):
    review = latest_review(contractor)
    # Existing approved records retain their prior behavior until reviewed.
    # New approvals always require a review through the admin approval route.
    return review_valid(contractor, review) if review else True


@verification.route('/admin/contractors/<int:contractor_id>/verification', methods=['GET','POST'])
@administrator
def review_credentials(contractor_id):
    from app import db, Contractor, CredentialReview, LeadOffer
    contractor = db.session.get(Contractor, contractor_id)
    if contractor is None:
        abort(404)
    error = None
    if request.method == 'POST':
        require_csrf()
        decision = request.form.get('decision', '')
        notes = request.form.get('notes', '').strip()
        license_reference = request.form.get('license_reference', '').strip()
        insurance_reference = request.form.get('insurance_reference', '').strip()
        license_expires = insurance_expires = None
        try:
            if decision not in ('approved','rejected') or not notes or len(notes) > 5000:
                raise ValueError('Choose a decision and enter review notes (up to 5,000 characters).')
            if len(license_reference) > 255 or len(insurance_reference) > 255:
                raise ValueError('Evidence references must be no longer than 255 characters.')
            if decision == 'approved':
                if not contractor.license_number or not license_reference or not insurance_reference:
                    raise ValueError('A license number and both evidence references are required for approval.')
                if request.form.get('license_checked') != 'yes' or request.form.get('insurance_checked') != 'yes':
                    raise ValueError('Confirm that both the license and insurance were checked.')
                try:
                    license_expires = date.fromisoformat(request.form.get('license_expires', ''))
                    insurance_expires = date.fromisoformat(request.form.get('insurance_expires', ''))
                except ValueError:
                    raise ValueError('Enter valid license and insurance expiration dates.')
                if min(license_expires, insurance_expires) < datetime.now(timezone.utc).date():
                    raise ValueError('Expired credentials cannot be approved.')
        except ValueError as exc:
            error = str(exc)
        if error is None:
            try:
                contractor = Contractor.query.filter_by(id=contractor_id).populate_existing().with_for_update().one()
                previous_review = latest_review(contractor)
                was_enabled = bool(contractor.active or contractor.verified)
                review = CredentialReview(contractor_id=contractor_id, decision=decision,
                    license_number=contractor.license_number or '', license_expires=license_expires,
                    insurance_expires=insurance_expires, license_reference=license_reference,
                    insurance_reference=insurance_reference, notes=notes)
                db.session.add(review)
                if decision == 'rejected':
                    contractor.active = False
                    contractor.verified = False
                    db.session.execute(update(LeadOffer).where(LeadOffer.contractor_id == contractor_id,
                        LeadOffer.status == 'pending').values(status='cancelled'))
                    if was_enabled or not previous_review or previous_review.decision != 'rejected':
                        from contractor_account_notifications import queue_account_notice
                        db.session.flush()
                        queue_account_notice(contractor, 'review_rejected', review_id=review.id)
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            flash('Credential review recorded. Approved reviews still require account activation in administration.' if decision == 'approved' else 'Review rejected. Account deactivated and pending offers cancelled.', 'success')
            return redirect(url_for('verification.review_credentials', contractor_id=contractor_id))
    reviews = CredentialReview.query.filter_by(contractor_id=contractor_id).order_by(CredentialReview.id.desc()).limit(20).all()
    from minnesota_lookup_sources import MN_LOOKUP_SOURCES
    from app import ContractorAccountEvent, Delivery
    account_events = db.session.query(ContractorAccountEvent, Delivery).join(
        Delivery, Delivery.id == ContractorAccountEvent.delivery_id).filter(
        ContractorAccountEvent.contractor_id == contractor_id).order_by(ContractorAccountEvent.id.desc()).limit(20).all()
    return render_template('credential_review.html', contractor=contractor, reviews=reviews,
        error=error, lookup_sources=MN_LOOKUP_SOURCES, account_events=account_events), 400 if error else 200

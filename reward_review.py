"""Business identity review only. Real rewards, entries and credit issuance stay closed."""
import hashlib
import re
from datetime import date, datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from national import administrator
from operations import contractor_required
from contractor_onboarding import require_csrf

reward_review = Blueprint('reward_review', __name__)


def define_reward_review(db):
    class RewardIdentityApplication(db.Model):
        __tablename__ = 'reward_identity_applications'
        id = db.Column(db.Integer, primary_key=True)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False, index=True)
        legal_name = db.Column(db.String(200), nullable=False)
        jurisdiction = db.Column(db.String(5), nullable=False)
        registration_id = db.Column(db.String(100), nullable=False)
        notes = db.Column(db.Text, nullable=False)
        status = db.Column(db.String(20), nullable=False, default='pending')
        pending_key = db.Column(db.Integer, unique=True)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        __table_args__ = (db.CheckConstraint("status in ('pending','approved','rejected')"),)

    class RewardBusinessAccount(db.Model):
        __tablename__ = 'reward_business_accounts'
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), primary_key=True)
        business_id = db.Column(db.Integer, db.ForeignKey('reward_businesses.id'), unique=True, nullable=False)
        application_id = db.Column(db.Integer, db.ForeignKey('reward_identity_applications.id'), unique=True, nullable=False)
        verified_until = db.Column(db.Date, nullable=False)

    class RewardIdentityReview(db.Model):
        __tablename__ = 'reward_identity_reviews'
        id = db.Column(db.Integer, primary_key=True)
        application_id = db.Column(db.Integer, db.ForeignKey('reward_identity_applications.id'), unique=True, nullable=False)
        decision = db.Column(db.String(20), nullable=False)
        evidence_reference = db.Column(db.String(255), nullable=False)
        canonical_jurisdiction = db.Column(db.String(5), nullable=False)
        canonical_registration_id = db.Column(db.String(100), nullable=False)
        private_notes = db.Column(db.Text, nullable=False)
        response_message = db.Column(db.String(1000), nullable=False)
        reviewed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
        __table_args__ = (db.CheckConstraint("decision in ('approved','rejected')"),)
    return RewardIdentityApplication, RewardBusinessAccount, RewardIdentityReview


@reward_review.after_request
def private_pages(response):
    from consumer_requests import PRIVATE_HEADERS
    response.headers.update(PRIVATE_HEADERS)
    return response


def identity_digest(jurisdiction, registration_id):
    """Canonical principal registry ID, independently resolved by the reviewer.

    Alternate state registrations of one business must resolve to this same
    principal identity. A hash alone does not verify identity or resolve aliases.
    """
    jurisdiction = jurisdiction.strip().upper()
    registration_id = registration_id.strip().upper()
    if not re.fullmatch(r'US-[A-Z]{2}', jurisdiction) or not re.fullmatch(r'[A-Z0-9][A-Z0-9 ._/-]{0,99}', registration_id):
        raise ValueError('Use a US-XX registry jurisdiction and a valid public registration identifier, not an EIN or personal ID.')
    # Formatting aliases in a single registry must not create extra businesses.
    normalized = re.sub(r'[^A-Z0-9]', '', registration_id)
    return hashlib.sha256((jurisdiction+':'+normalized).encode('ascii')).hexdigest()


def current_business(contractor_id):
    from app import db, RewardBusinessAccount, RewardBusiness, Contractor
    account = db.session.get(RewardBusinessAccount, contractor_id)
    contractor = db.session.get(Contractor, contractor_id)
    business = db.session.get(RewardBusiness, account.business_id) if account else None
    if (not account or account.verified_until < datetime.now(timezone.utc).date() or not business or not business.verified
            or not contractor or not contractor.active or not contractor.verified or contractor.is_test or not contractor.credential_review_current):
        return None
    return business


@reward_review.route('/contractor/rewards', methods=['GET','POST'])
@contractor_required
def overview(contractor):
    from app import db, Contractor, RewardIdentityApplication, RewardBusinessAccount, RewardIdentityReview
    error=None
    if request.method=='POST':
        require_csrf()
        legal_name=request.form.get('legal_name','').strip()
        jurisdiction=request.form.get('jurisdiction','').strip().upper()
        registration_id=request.form.get('registration_id','').strip()
        notes=request.form.get('notes','').strip()
        try:
            identity_digest(jurisdiction,registration_id)
            if not legal_name or len(legal_name)>200 or len(notes)>2000:
                raise ValueError('Enter the legal business name (up to 200 characters) and notes up to 2,000 characters.')
            if request.form.get('identity_review')!='yes':
                raise ValueError('Confirm that this is a business-identity review request, not a rewards entry.')
            Contractor.query.filter_by(id=contractor.id).populate_existing().with_for_update().one()
            if current_business(contractor.id):
                raise ValueError('This account already has a current business identity. Identities and credits cannot be transferred.')
            if RewardIdentityApplication.query.filter_by(pending_key=contractor.id).first():
                raise ValueError('Your business identity request is already awaiting review.')
            db.session.add(RewardIdentityApplication(contractor_id=contractor.id,legal_name=legal_name,
                jurisdiction=jurisdiction,registration_id=registration_id,notes=notes,pending_key=contractor.id))
            db.session.commit()
            flash('Business identity submitted for review. No entry, credit, spin or prize was issued.','success')
            return redirect(url_for('reward_review.overview'),code=303)
        except ValueError as exc:
            db.session.rollback();error=str(exc)
        except IntegrityError:
            db.session.rollback();error='A request or verified business link already exists. Refresh your account history.'
    history=db.session.query(RewardIdentityApplication,RewardIdentityReview).outerjoin(RewardIdentityReview,
        RewardIdentityReview.application_id==RewardIdentityApplication.id).filter(
        RewardIdentityApplication.contractor_id==contractor.id).order_by(RewardIdentityApplication.id.desc()).limit(20).all()
    return render_template('rewards_overview.html',history=history,business=current_business(contractor.id),
        pending=RewardIdentityApplication.query.filter_by(pending_key=contractor.id).first(),
        linked=db.session.get(RewardBusinessAccount,contractor.id),error=error),400 if error else 200


@reward_review.get('/admin/rewards')
@administrator
def readiness():
    from app import db, RewardIdentityApplication, Contractor
    rows=db.session.query(RewardIdentityApplication,Contractor).join(Contractor,
        Contractor.id==RewardIdentityApplication.contractor_id).order_by(
        (RewardIdentityApplication.status=='pending').desc(),RewardIdentityApplication.id.desc()).limit(200).all()
    return render_template('rewards_admin.html',rows=rows)


@reward_review.route('/admin/rewards/identity/<int:application_id>',methods=['GET','POST'])
@administrator
def review_identity(application_id):
    from app import db, Contractor, RewardIdentityApplication, RewardIdentityReview, RewardBusiness, RewardBusinessAccount
    from communications import queue_email
    row=db.get_or_404(RewardIdentityApplication,application_id)
    contractor=db.session.get(Contractor,row.contractor_id)
    error=None
    if request.method=='POST':
        require_csrf()
        decision=request.form.get('decision','')
        reference=request.form.get('evidence_reference','').strip()
        jurisdiction=request.form.get('canonical_jurisdiction','').strip().upper()
        registration_id=request.form.get('canonical_registration_id','').strip()
        notes=request.form.get('private_notes','').strip()
        response=request.form.get('response_message','').strip()
        try:
            if decision not in ('approved','rejected') or not notes or len(notes)>5000 or not response or len(response)>1000 or len(reference)>255:
                raise ValueError('Choose a decision and provide private notes and an applicant message within the stated limits.')
            verified_until=None;digest=None
            if decision=='approved':
                digest=identity_digest(jurisdiction,registration_id)
                if not reference or request.form.get('identity_checked')!='yes' or request.form.get('duplicates_checked')!='yes':
                    raise ValueError('Record registry/account-control evidence and confirm business identity and duplicate-business checks.')
                verified_until=date.fromisoformat(request.form.get('verified_until',''))
                if verified_until<datetime.now(timezone.utc).date():raise ValueError('Verification must be current.')
            Contractor.query.filter_by(id=contractor.id).populate_existing().with_for_update().one()
            row=RewardIdentityApplication.query.filter_by(id=application_id).populate_existing().with_for_update().one()
            if row.status!='pending':abort(409,'This identity request has already been reviewed.')
            if decision=='approved':
                if not contractor.active or not contractor.verified or contractor.is_test or not contractor.credential_review_current:
                    raise ValueError('The contractor account must retain its approval and current credentials.')
                business=RewardBusiness.query.filter_by(identity_digest=digest).first()
                existing_link=RewardBusinessAccount.query.filter_by(business_id=business.id).first() if business else None
                account=db.session.get(RewardBusinessAccount,contractor.id)
                if existing_link and existing_link.contractor_id!=contractor.id:
                    raise ValueError('This legal business is already linked to an account. Resolve duplicate accounts before approval. No credits can be transferred.')
                if account and (not business or account.business_id!=business.id):
                    raise ValueError('This contractor account already has a business identity. Identity switching is not permitted.')
                if not business:
                    business=RewardBusiness(identity_digest=digest,verified=True);db.session.add(business);db.session.flush()
                business.verified=True
                if account:
                    account.application_id=row.id;account.verified_until=verified_until
                else:
                    db.session.add(RewardBusinessAccount(contractor_id=contractor.id,business_id=business.id,
                        application_id=row.id,verified_until=verified_until))
            from sqlalchemy import update
            changed=db.session.execute(update(RewardIdentityApplication).where(RewardIdentityApplication.id==row.id,
                RewardIdentityApplication.status=='pending').values(status=decision,pending_key=None)).rowcount
            if changed!=1:abort(409,'This identity request has already been reviewed.')
            db.session.add(RewardIdentityReview(application_id=row.id,decision=decision,evidence_reference=reference,
                canonical_jurisdiction=jurisdiction,canonical_registration_id=registration_id,
                private_notes=notes,response_message=response))
            queue_email(f'reward-identity:{row.id}:review',contractor.email,'Business identity review completed',
                'Your business identity request has been reviewed. Sign in to view the result. LeadIQ Rewards remains unavailable pending official rules. No credit or prize was issued.')
            db.session.commit()
            return redirect(url_for('reward_review.review_identity',application_id=application_id),code=303)
        except ValueError as exc:
            db.session.rollback();error=str(exc)
        except IntegrityError:
            db.session.rollback();error='Another review or business identity link was saved. Recheck duplicate accounts and review history.'
        except Exception:
            db.session.rollback();raise
    review=RewardIdentityReview.query.filter_by(application_id=application_id).first()
    return render_template('rewards_identity_review.html',row=row,contractor=contractor,review=review,error=error),400 if error else 200


@reward_review.post('/contractor/rewards/free-entry')
@reward_review.post('/contractor/rewards/redeem')
def closed_rewards():
    # No environment flag or client-supplied approval can override the legal hold.
    return {'error':'LeadIQ Rewards entries and redemption are closed pending approved official rules and legal review.'},503

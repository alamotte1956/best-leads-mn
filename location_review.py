"""Postal facility associations flag review; they never prove property jurisdiction."""
import json
from functools import lru_cache
from pathlib import Path
from flask import Blueprint,abort,redirect,render_template,request,url_for
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from national import administrator
from national_markets import STATES,code_enabled
from contractor_onboarding import require_csrf

locations=Blueprint('locations',__name__)
REVIEW_STATUS='Needs location review'


def define_location_review(db):
    class LeadLocationReview(db.Model):
        __tablename__='lead_location_reviews'
        id=db.Column(db.Integer,primary_key=True)
        lead_id=db.Column(db.Integer,db.ForeignKey('leads.id'),unique=True,nullable=False)
        zip_code=db.Column(db.String(5),nullable=False)
        state_code=db.Column(db.String(2),nullable=False)
        previous_state_code=db.Column(db.String(2))
        decision=db.Column(db.String(20),nullable=False)
        evidence_reference=db.Column(db.String(255),nullable=False)
        private_notes=db.Column(db.Text,nullable=False)
        reviewed_at=db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        __table_args__=(db.CheckConstraint("decision in ('approved','unavailable')"),
                       db.CheckConstraint("state_code in ('MN','TX','FL','NC','GA','WI')"))
    return LeadLocationReview


@lru_cache(maxsize=1)
def postal_reference():
    path=Path(__file__).parent/'data/usps_zip_facilities_2026_10.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('version')!='2026-10' or len(data.get('facility_states_by_zip',{}))<30000:
        raise RuntimeError('The reviewed postal reference is missing or invalid.')
    return data


def needs_location_review(zip_code,state_code):
    """An association is a plausibility signal, not geographic verification.

    Unknown ZIPs and mismatches are saved for review rather than called invalid.
    Cross-border ZIPs can have facilities in more than one state.
    """
    return state_code not in postal_reference()['facility_states_by_zip'].get(zip_code,[])


@locations.route('/admin/leads/<int:lead_id>/location',methods=['GET','POST'])
@administrator
def review(lead_id):
    from app import db,Lead,LeadOffer,LeadMarket,LeadLocationReview
    from national_coverage import lead_state
    from consumer_requests import queue_request_update
    lead=db.get_or_404(Lead,lead_id);error=None
    if request.method=='POST':
        require_csrf()
        decision=request.form.get('decision','')
        state=request.form.get('state_code','')
        reference=request.form.get('evidence_reference','').strip()
        notes=request.form.get('private_notes','').strip()
        if (decision not in ('approved','unavailable') or state not in {s[0] for s in STATES.values()}
                or not reference or len(reference)>255 or not notes or len(notes)>5000
                or request.form.get('jurisdiction_checked')!='yes'):
            error='Choose a state and decision, confirm property jurisdiction, and record evidence (up to 255 characters) and private notes (up to 5,000 characters).'
        elif decision=='approved' and not code_enabled(state):
            error='This state is closed. You can record the request as unavailable, but cannot enable matching.'
        if not error:
            try:
                if db.session.get_bind().dialect.name=='postgresql':
                    from sequential_matching_lock import lock_lead_for_matching
                    lock_lead_for_matching(db.session,lead_id)
                lead=Lead.query.filter_by(id=lead_id).populate_existing().with_for_update().one()
                if lead.status!=REVIEW_STATUS or LeadLocationReview.query.filter_by(lead_id=lead_id).first():
                    abort(409,'This request no longer awaits a location review.')
                if LeadOffer.query.filter_by(lead_id=lead_id,status='accepted').first():
                    abort(409,'Accepted offer history requires separate reconciliation before location changes.')
                target='New' if decision=='approved' else 'Cancelled'
                previous_state=lead_state(lead)
                changed=db.session.execute(update(Lead).where(Lead.id==lead_id,Lead.status==REVIEW_STATUS).values(status=target)).rowcount
                if changed!=1:abort(409,'The request changed during review.')
                scope=db.session.get(LeadMarket,lead_id)
                if scope:scope.state_code=state
                else:db.session.add(LeadMarket(lead_id=lead_id,state_code=state))
                db.session.execute(update(LeadOffer).where(LeadOffer.lead_id==lead_id,LeadOffer.status=='pending').values(status='cancelled'))
                db.session.add(LeadLocationReview(lead_id=lead_id,zip_code=lead.zip_code,state_code=state,
                    previous_state_code=previous_state,decision=decision,evidence_reference=reference,private_notes=notes))
                db.session.flush()
                if decision=='unavailable':queue_request_update(lead,'cancelled')
                db.session.commit()
                return redirect(url_for('locations.review',lead_id=lead_id),code=303)
            except IntegrityError:
                db.session.rollback();error='Another location review was saved. Refresh the request history.'
            except Exception:
                db.session.rollback();raise
    return render_template('location_review.html',lead=lead,current_state=lead_state(lead),states=STATES,error=error,
        review=LeadLocationReview.query.filter_by(lead_id=lead_id).first(),review_status=REVIEW_STATUS),400 if error else 200

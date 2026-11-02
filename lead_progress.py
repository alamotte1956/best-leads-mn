"""Private, contractor-reported follow-up for accepted offers. No fulfillment events."""
import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import and_, case, or_, update
from sqlalchemy.exc import IntegrityError
from operations import contractor_required
from national import administrator
from contractor_onboarding import require_csrf
from contractor_session_security import contractor_session_valid
from consumer_requests import PRIVATE_HEADERS

lead_progress = Blueprint('lead_progress',__name__)
STAGES = {
    'new':'Ready to contact', 'contact_attempted':'Contact attempted', 'contacted':'Contacted',
    'estimate_sent':'Estimate sent', 'work_scheduled':'Work scheduled',
    'completed':'Work completed', 'not_proceeding':'Not proceeding',
}
STAGE_CHECK="stage in ('new','contact_attempted','contacted','estimate_sent','work_scheduled','completed','not_proceeding')"


def define_lead_progress(db):
    class ContractorLeadProgress(db.Model):
        __tablename__='contractor_lead_progress'
        offer_id=db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'),db.ForeignKey('lead_offers.id'),primary_key=True)
        contractor_id=db.Column(db.Integer,db.ForeignKey('contractors.id'),nullable=False,index=True)
        stage=db.Column(db.String(30),nullable=False)
        next_follow_up=db.Column(db.Date)
        note=db.Column(db.Text,nullable=False,default='')
        version=db.Column(db.Integer,nullable=False)
        updated_at=db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        __table_args__=(db.CheckConstraint(STAGE_CHECK,name='lead_progress_stage'),
                       db.CheckConstraint('version > 0',name='lead_progress_version'))
    class LeadProgressEvent(db.Model):
        __tablename__='contractor_lead_progress_events'
        id=db.Column(db.Integer,primary_key=True)
        offer_id=db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'),db.ForeignKey('lead_offers.id'),nullable=False,index=True)
        contractor_id=db.Column(db.Integer,db.ForeignKey('contractors.id'),nullable=False)
        previous_stage=db.Column(db.String(30),nullable=False)
        stage=db.Column(db.String(30),nullable=False)
        next_follow_up=db.Column(db.Date)
        note=db.Column(db.Text,nullable=False,default='')
        version=db.Column(db.Integer,nullable=False)
        created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        __table_args__=(db.CheckConstraint(STAGE_CHECK,name='lead_progress_event_stage'),
                       db.UniqueConstraint('offer_id','version',name='lead_progress_event_version'))
    return ContractorLeadProgress,LeadProgressEvent


class ProgressConflict(RuntimeError):
    pass


def followup_today():
    return datetime.now(ZoneInfo('America/Chicago')).date()


@lead_progress.after_request
def private_response(response):
    response.headers.update(PRIVATE_HEADERS)
    return response


@lead_progress.get('/contractor/leads')
@contractor_required
def pipeline(contractor):
    from app import db, LeadOffer, Lead, ContractorLeadProgress as Progress
    stage=request.args.get('stage','all');due=request.args.get('due','all');page_text=request.args.get('page','1')
    if (stage not in ('all',*STAGES) or due not in ('all','overdue','today','upcoming')
            or not page_text.isascii() or not page_text.isdigit() or not 1<=len(page_text)<=6 or int(page_text)<1):
        abort(400)
    today=followup_today()
    query=db.session.query(LeadOffer,Lead,Progress).join(Lead,Lead.id==LeadOffer.lead_id).outerjoin(
        Progress,and_(Progress.offer_id==LeadOffer.id,Progress.contractor_id==LeadOffer.contractor_id)
    ).filter(LeadOffer.contractor_id==contractor.id,LeadOffer.status=='accepted')
    if stage=='new':query=query.filter(or_(Progress.offer_id.is_(None),Progress.stage=='new'))
    elif stage!='all':query=query.filter(Progress.stage==stage)
    if due=='overdue':query=query.filter(Progress.next_follow_up<today)
    elif due=='today':query=query.filter(Progress.next_follow_up==today)
    elif due=='upcoming':query=query.filter(Progress.next_follow_up>today)
    total=query.count();pages=max(1,math.ceil(total/20));page=min(int(page_text),pages)
    rows=query.order_by(case((Progress.next_follow_up.is_(None),1),else_=0),
        Progress.next_follow_up,LeadOffer.id.desc()).offset((page-1)*20).limit(20).all()
    return render_template('lead_pipeline.html',rows=rows,stage=stage,due=due,stages=STAGES,
        total=total,page=page,pages=pages,today=today)


def detail_context(offer, *, readonly, form_data=None, error=None):
    from app import db,Lead,Contractor,ContractorLeadProgress,LeadProgressEvent
    from contact_links import mailto_address
    lead=db.session.get(Lead,offer.lead_id)
    if not lead:abort(404)
    current=ContractorLeadProgress.query.filter_by(offer_id=offer.id,contractor_id=offer.contractor_id).populate_existing().first()
    saved={'stage':current.stage,'next_follow_up':current.next_follow_up.isoformat() if current.next_follow_up else '',
           'note':current.note} if current else {'stage':'new','next_follow_up':'','note':''}
    return dict(offer=offer,lead=lead,contractor=db.session.get(Contractor,offer.contractor_id),progress=current,
        stages=STAGES,readonly=readonly,error=error,form_data=saved if form_data is None else form_data,
        revision=current.version if current else 0,phone_digits=re.sub(r'[^0-9]','',lead.phone or ''),
        homeowner_mailto=mailto_address(lead.email),
        history=LeadProgressEvent.query.filter_by(offer_id=offer.id,contractor_id=offer.contractor_id).order_by(LeadProgressEvent.id.desc()).limit(30).all())


@lead_progress.route('/contractor/offers/<int:offer_id>/follow-up',methods=['GET','POST'])
@contractor_required
def detail(contractor,offer_id):
    from app import db,Contractor,LeadOffer,ContractorLeadProgress as Progress,LeadProgressEvent
    offer=LeadOffer.query.filter_by(id=offer_id,contractor_id=contractor.id,status='accepted').first()
    if not offer:abort(404)
    from billing import offer_contact_available
    if not offer_contact_available(offer):
        if request.method == 'POST':
            require_csrf()
        return render_template('lead_access_locked.html',offer=offer),402
    error=None;code=200;form_data=None
    if request.method=='POST':
        require_csrf();form_data=request.form
        revision=request.form.get('version','')
        stage=request.form.get('stage','');note=request.form.get('note','').strip()
        next_text=request.form.get('next_follow_up','').strip()
        try:
            if not revision.isascii() or not revision.isdigit() or not 1<=len(revision)<=9:
                raise ValueError('Refresh the page before saving your update.')
            if stage not in STAGES:raise ValueError('Choose a follow-up stage from the list.')
            if len(note)>2000:raise ValueError('Keep your note within 2,000 characters.')
            try:
                next_date=date.fromisoformat(next_text) if next_text else None
                if next_text and len(next_text)!=10:raise ValueError()
            except ValueError:raise ValueError('Enter a valid follow-up date or leave it blank.') from None
            contractor=Contractor.query.filter_by(id=contractor.id).populate_existing().with_for_update().one()
            if not contractor_session_valid(dict(session),contractor):abort(403)
            offer=LeadOffer.query.filter_by(id=offer_id,contractor_id=contractor.id,status='accepted').populate_existing().with_for_update().first()
            if not offer:abort(404)
            current=Progress.query.filter_by(offer_id=offer.id,contractor_id=contractor.id).populate_existing().first()
            old_stage=current.stage if current else 'new';version=current.version if current else 0
            same=(old_stage==stage and (current.next_follow_up if current else None)==next_date
                  and (current.note if current else '')==note)
            if same:
                db.session.rollback();flash('Your follow-up is already up to date.','success')
                return redirect(url_for('lead_progress.detail',offer_id=offer.id),code=303)
            if int(revision)!=version:raise ProgressConflict()
            if not current:
                db.session.add(Progress(offer_id=offer.id,contractor_id=contractor.id,stage=stage,
                    next_follow_up=next_date,note=note,version=1));db.session.flush()
            else:
                changed=db.session.execute(update(Progress).where(Progress.offer_id==offer.id,
                    Progress.version==version).values(stage=stage,next_follow_up=next_date,note=note,
                    version=version+1,updated_at=db.func.now())).rowcount
                if changed!=1:raise ProgressConflict()
            db.session.add(LeadProgressEvent(offer_id=offer.id,contractor_id=contractor.id,
                previous_stage=old_stage,stage=stage,next_follow_up=next_date,note=note,version=version+1))
            db.session.commit();flash('Your reported follow-up was saved.','success')
            return redirect(url_for('lead_progress.detail',offer_id=offer.id),code=303)
        except ValueError as exc:
            db.session.rollback();error=str(exc);code=400
        except (ProgressConflict,IntegrityError):
            db.session.rollback();error='Another update was saved. Your draft is still below. Review the latest saved update, then save again if your draft still applies.';code=409
        except Exception:
            db.session.rollback();raise
    return render_template('lead_followup.html',**detail_context(offer,readonly=False,form_data=form_data,error=error)),code


@lead_progress.get('/admin/offers/<int:offer_id>/follow-up')
@administrator
def inspect(offer_id):
    from app import db,LeadOffer
    offer=db.session.get(LeadOffer,offer_id)
    if not offer:abort(404)
    return render_template('lead_followup.html',**detail_context(offer,readonly=True))

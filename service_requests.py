"""Administrator-reviewed additions to contractor services; existing rows stay intact."""
from datetime import datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from operations import contractor_required
from national import administrator
from contractor_onboarding import require_csrf
from contractor_matching import normalize_service
from service_catalog import SERVICES
from consumer_requests import PRIVATE_HEADERS

service_requests = Blueprint('service_requests',__name__)


def define_service_requests(db):
    class ServiceRequest(db.Model):
        __tablename__ = 'contractor_service_requests'
        id = db.Column(db.Integer,primary_key=True)
        contractor_id = db.Column(db.Integer,db.ForeignKey('contractors.id'),nullable=False,index=True)
        service_name = db.Column(db.String(100),nullable=False)
        contractor_notes = db.Column(db.Text,nullable=False,default='')
        status = db.Column(db.String(20),nullable=False,default='pending')
        pending_key = db.Column(db.String(150),unique=True)
        created_at = db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        resolved_at = db.Column(db.DateTime(timezone=True))
        resolved_by = db.Column(db.String(20))
        coverage_reference = db.Column(db.String(255))
        private_review_notes = db.Column(db.Text)
        response_message = db.Column(db.Text)
        __table_args__ = (
            db.CheckConstraint("status in ('pending','approved','rejected','withdrawn')",name='service_request_status'),
            db.CheckConstraint("(status = 'pending' AND pending_key IS NOT NULL AND resolved_at IS NULL AND resolved_by IS NULL) OR (status != 'pending' AND pending_key IS NULL AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL AND ((status = 'withdrawn' AND resolved_by = 'contractor') OR (status in ('approved','rejected') AND resolved_by = 'administrator')))",name='service_request_resolution'),
            db.CheckConstraint("status != 'approved' OR (coverage_reference IS NOT NULL AND length(trim(coverage_reference)) > 0)",name='service_request_coverage'),
        )
    return ServiceRequest


def registered_services(contractor):
    from app import ContractorService
    names = [contractor.service_type] + [row.service_name for row in
        ContractorService.query.filter_by(contractor_id=contractor.id).order_by(ContractorService.id).all()]
    seen=set(); result=[]
    for name in names:
        key=normalize_service(name)
        if key and key not in seen:
            seen.add(key);result.append(name)
    return result


@service_requests.after_request
def private_response(response):
    response.headers.update(PRIVATE_HEADERS)
    return response


@service_requests.route('/contractor/services/request',methods=['GET','POST'])
@contractor_required
def submit(contractor):
    from app import db, Contractor, ServiceRequest
    from communications import queue_email
    from contractor_session_security import contractor_session_valid
    from flask import session
    error=None;code=200
    if request.method=='POST':
        require_csrf()
        name=request.form.get('service_name','').strip()
        notes=request.form.get('contractor_notes','').strip()
        try:
            contractor=Contractor.query.filter_by(id=contractor.id).populate_existing().with_for_update().one()
            if not contractor_session_valid(dict(session),contractor):abort(403)
            if name not in SERVICES:raise ValueError('Choose a service from the list.')
            if len(notes)>1000:raise ValueError('Keep your request notes within 1,000 characters.')
            if normalize_service(name) in {normalize_service(item) for item in registered_services(contractor)}:
                raise ValueError('That service is already registered on your account.')
            key=f'{contractor.id}:{name}'
            if ServiceRequest.query.filter_by(pending_key=key).first():
                raise ValueError('That service already has a request awaiting review.')
            row=ServiceRequest(contractor_id=contractor.id,service_name=name,contractor_notes=notes,pending_key=key)
            db.session.add(row);db.session.flush()
            queue_email(f'service-request:{row.id}:received',contractor.email,'Service request received',
                f'Your additional-service request #{row.id} was received. Submitting a request does not approve a service. '
                'Sign in to your contractor settings at RestorationContractorsMN.com to see its current status. No charge has been made.')
            db.session.commit()
            flash('Additional service requested. Your registered services remain unchanged until approval.','success')
            return redirect(url_for('operations.settings'),code=303)
        except ValueError as exc:
            db.session.rollback();error=str(exc);code=400
        except IntegrityError:
            db.session.rollback();error='A request for that service was already submitted. Check your request history.';code=409
        except Exception:
            db.session.rollback();raise
    current=registered_services(contractor)
    unavailable={normalize_service(item) for item in current}
    unavailable.update(normalize_service(item.service_name) for item in
        ServiceRequest.query.filter_by(contractor_id=contractor.id,status='pending').all())
    available=[name for name in SERVICES if normalize_service(name) not in unavailable]
    return render_template('service_request.html',contractor=contractor,services=available,
        current_services=current,error=error),code


@service_requests.post('/contractor/services/requests/<int:request_id>/withdraw')
@contractor_required
def withdraw(contractor,request_id):
    from app import db, Contractor, ServiceRequest
    require_csrf()
    try:
        Contractor.query.filter_by(id=contractor.id).with_for_update().one()
        row=ServiceRequest.query.filter_by(id=request_id,contractor_id=contractor.id).populate_existing().with_for_update().first()
        if not row:abort(404)
        if row.status=='withdrawn':
            db.session.rollback()
            return redirect(url_for('operations.settings'),code=303)
        changed=db.session.execute(update(ServiceRequest).where(ServiceRequest.id==row.id,
            ServiceRequest.status=='pending').values(status='withdrawn',pending_key=None,
            resolved_at=datetime.now(timezone.utc),resolved_by='contractor')).rowcount
        if changed!=1:abort(409,'This request has already been reviewed.')
        db.session.commit()
    except Exception:
        db.session.rollback();raise
    flash('Service request withdrawn. Existing registered services are unchanged.','success')
    return redirect(url_for('operations.settings'),code=303)


@service_requests.get('/admin/service-requests')
@administrator
def queue():
    from app import db, ServiceRequest, Contractor
    state=request.args.get('status','pending')
    if state not in ('pending','approved','rejected','withdrawn'):abort(400)
    rows=db.session.query(ServiceRequest,Contractor).join(Contractor,
        Contractor.id==ServiceRequest.contractor_id).filter(ServiceRequest.status==state).order_by(ServiceRequest.id.desc()).limit(100).all()
    return render_template('service_request_queue.html',rows=rows,state=state,
        pending_count=ServiceRequest.query.filter_by(status='pending').count())


@service_requests.route('/admin/service-requests/<int:request_id>',methods=['GET','POST'])
@administrator
def review(request_id):
    from app import db, ServiceRequest, Contractor, ContractorService
    from credential_verification import latest_review, review_valid
    from communications import queue_email
    row=db.session.get(ServiceRequest,request_id)
    if not row:abort(404)
    contractor=db.session.get(Contractor,row.contractor_id)
    error=None;code=200
    if request.method=='POST':
        require_csrf()
        try:
            contractor=Contractor.query.filter_by(id=row.contractor_id).populate_existing().with_for_update().one()
            row=ServiceRequest.query.filter_by(id=request_id).populate_existing().with_for_update().one()
            if row.status!='pending':abort(409,'This service request is already resolved.')
            action=request.form.get('decision','')
            notes=request.form.get('private_review_notes','').strip()
            message=request.form.get('response_message','').strip()
            reference=request.form.get('coverage_reference','').strip()
            if action not in ('approved','rejected'):raise ValueError('Choose an approval or rejection decision.')
            if not notes or len(notes)>2000:raise ValueError('Enter internal review notes within 2,000 characters.')
            if len(message)>2000 or len(reference)>255:raise ValueError('Check the message and evidence reference lengths.')
            if action=='rejected' and not message:raise ValueError('Explain the decision in the message visible to the contractor.')
            if action=='approved':
                if row.service_name not in SERVICES:abort(409,'The requested service is not in the supported catalog.')
                if not contractor.active or not contractor.verified or contractor.is_test:abort(409,'The contractor must be approved and active first.')
                if not review_valid(contractor,latest_review(contractor)):
                    abort(409,'Record a current approved license and insurance review before approving another service.')
                if (not reference or request.form.get('license_scope_checked')!='yes'
                        or request.form.get('insurance_scope_checked')!='yes'):
                    raise ValueError('Confirm license and insurance coverage for this service and record the evidence reference.')
            changed=db.session.execute(update(ServiceRequest).where(ServiceRequest.id==row.id,
                ServiceRequest.status=='pending').values(status=action,pending_key=None,
                resolved_at=datetime.now(timezone.utc),resolved_by='administrator',
                private_review_notes=notes,response_message=message,coverage_reference=reference or None)).rowcount
            if changed!=1:abort(409,'Another reviewer resolved this request. Refresh the page.')
            if action=='approved' and normalize_service(row.service_name) not in {
                    normalize_service(item) for item in registered_services(contractor)}:
                db.session.add(ContractorService(contractor_id=contractor.id,service_name=row.service_name))
            queue_email(f'service-request:{row.id}:decision',contractor.email,'Service request reviewed',
                f'Your additional-service request #{row.id} was {action}. '
                'Sign in to contractor settings at RestorationContractorsMN.com to view the decision and your current services. '
                'Account approval and current credentials are still required for lead eligibility. No charge has been made.')
            db.session.commit()
            flash('Service request '+action+'. Decision and email notice saved.','success')
            return redirect(url_for('service_requests.review',request_id=row.id),code=303)
        except ValueError as exc:
            db.session.rollback();error=str(exc);code=400
        except Exception:
            db.session.rollback();raise
    return render_template('service_request_review.html',entry=row,contractor=contractor,
        current_services=registered_services(contractor),error=error,
        credential_ready=review_valid(contractor,latest_review(contractor))),code

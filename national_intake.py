"""Public multistate forms behind the same immutable state-launch gate."""
import json
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from national_markets import STATES, enabled
from contractor_onboarding import require_csrf

national_intake=Blueprint('national_intake',__name__)


def launched(state):
    if state not in STATES or not enabled(state):abort(404)
    return STATES[state]


@national_intake.get('/usa/<state>/request')
def request_form(state):
    market=launched(state)
    if market[0]=='MN':return redirect('/#request',code=302)
    return render_template('national_request.html',market=market)


@national_intake.route('/usa/<state>/contractors/apply',methods=['GET','POST'])
def register(state):
    market=launched(state)
    if market[0]=='MN':return redirect(url_for('signup'),code=307 if request.method=='POST' else 302)
    from app import db,Contractor,ContractorService,ContractorOrigin,MarketApplication,valid_email,valid_phone,valid_zip
    from service_catalog import SERVICES
    error=None
    if request.method=='POST':
        require_csrf()
        company=request.form.get('company_name','').strip()
        contact=request.form.get('contact_name','').strip()
        email=request.form.get('email','').strip().lower()
        phone=request.form.get('phone','').strip()
        license_number=request.form.get('license_number','').strip()
        raw_zips=request.form.get('zip_codes','')
        zips=list(dict.fromkeys(z.strip() for z in raw_zips.split(',') if z.strip()))
        services=list(dict.fromkeys(request.form.getlist('services')))
        if not company or len(company)>150 or not contact or len(contact)>100 or not valid_email(email) or len(email)>120:
            error='Enter your business name, contact name and a valid business email within the stated limits.'
        elif not valid_phone(phone) or len(phone)>20 or not license_number or len(license_number)>50:
            error='Enter a valid phone number and the state license or registration identifier (up to 50 characters).'
        elif not zips or len(raw_zips)>500 or not all(valid_zip(z) for z in zips):
            error='Enter five-digit service ZIP codes separated by commas, up to 500 characters.'
        elif not services or any(s not in SERVICES for s in services):
            error='Choose at least one listed restoration service.'
        elif request.form.get('approval_required')!='yes':
            error='Confirm that account approval and separate state coverage review are required.'
        if error is None:
            try:
                contractor=Contractor(company_name=company,contact_name=contact,email=email,phone=phone,
                    zip_codes='',service_radius_zip=None,service_type=services[0],license_number=license_number,
                    active=False,verified=False,is_test=False,sms_consent=False)
                db.session.add(contractor);db.session.flush()
                db.session.add(ContractorOrigin(contractor_id=contractor.id,state_code=market[0]))
                db.session.add_all(ContractorService(contractor_id=contractor.id,service_name=s) for s in services)
                db.session.add(MarketApplication(contractor_id=contractor.id,state_code=market[0],zip_codes=','.join(zips),
                    services_json=json.dumps(services),license_number=license_number,applicant_notes='Initial state application',
                    pending_key=f'{contractor.id}:{market[0]}'))
                from communications import queue_email
                queue_email(f'application:{contractor.id}:received',contractor.email,'Contractor application received',
                    f'Your {market[1]} contractor application was received. Account and state coverage approval are required before lead eligibility or purchases. No automatic charges or rewards were issued.')
                db.session.commit();flash('Application received. Account and state coverage approval are required before access or lead purchases.','success')
                return redirect(url_for('national_intake.register',state=state),code=303)
            except IntegrityError:
                db.session.rollback();error='An application already exists for that business email. Use your existing account for additional state coverage.'
            except Exception:
                db.session.rollback();raise
    return render_template('national_registration.html',market=market,services=SERVICES,error=error),400 if error else 200

"""Disposable CI-only browser fixture. It never uses a hosted database/provider."""
import os
import sys
import time
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
if os.environ.get('CI')!='true' or os.environ.get('RCUSA_BROWSER_FIXTURE')!='1':
    raise RuntimeError('This disposable fixture runs only in an explicitly selected CI test workflow.')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
# Each request gets its own connection to this disposable, local database.
# A single-thread server can be held by WebKit's idle/preconnected sockets.
fixture_directory=tempfile.TemporaryDirectory(prefix='rcusa-browser-fixture-')
os.environ['DATABASE_URL']='sqlite:///'+str(Path(fixture_directory.name)/'browser.sqlite')
os.environ['SECRET_KEY']='isolated-browser-checks-only'
os.environ['ADMIN_PASSWORD_HASH']='isolated-browser-admin-checks'
os.environ['PAYMENTS_ACTIVATION_UTC']=''
for flag in ('EMAIL_SENDING_ENABLED','SMS_SENDING_ENABLED','PAYMENTS_ENABLED','ENABLE_LIVE_MATCHING','CHECKOUT_RECONCILIATION_ENABLED','STRIPE_LIVE_PAYMENTS_ENABLED'):
    os.environ[flag]='false'
from app import app,db,Contractor,Lead,LeadOffer,MarketApplication,RewardIdentityApplication
from flask import redirect,session
from contractor_session_security import create_contractor_session_data
from admin_session_security import current_password_fingerprint
with app.app_context():
    db.create_all()
    c=Contractor(company_name='Synthetic CI Restoration Business',contact_name='Synthetic Owner',email='owner@example.com',
        phone='6125550100',zip_codes='55401',service_type='Mold Remediation',license_number='SYNTHETIC',
        active=True,verified=True,is_test=False,password_hash='synthetic-hash')
    lead=Lead(homeowner_name='Synthetic CI Consumer',phone='6125550199',email='consumer@example.com',zip_code='55401',
        service_needed='Mold Remediation',description='Synthetic browser-test request.',status='New')
    db.session.add_all([c,lead]);db.session.flush()
    db.session.add(LeadOffer(contractor_id=c.id,lead_id=lead.id,status='accepted',
        offered_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15)))
    db.session.add(MarketApplication(contractor_id=c.id,state_code='TX',zip_codes='75201',services_json='["Mold Remediation"]',
        license_number='SYNTHETIC',applicant_notes='Synthetic fixture',pending_key=f'{c.id}:TX'))
    db.session.add(RewardIdentityApplication(contractor_id=c.id,legal_name='Synthetic Legal Business',jurisdiction='US-MN',
        registration_id='SYNTHETIC-123',notes='Synthetic fixture',pending_key=c.id))
    db.session.commit();contractor_id=c.id
@app.get('/__ci/admin')
def admin():
    session.clear();session.update(admin_authenticated=True,admin_login_at=time.time()-1,
        admin_password_fingerprint=current_password_fingerprint())
    return redirect('/admin/national')
@app.get('/__ci/contractor')
def contractor():
    session.clear();session.update(create_contractor_session_data(contractor_id))
    session['contractor_password_fingerprint']=hashlib.sha256(b'synthetic-hash').hexdigest()
    return redirect('/contractor/dashboard')
app.run(host='127.0.0.1',port=int(os.environ.get('RCUSA_BROWSER_PORT','5055')),threaded=True,use_reloader=False)

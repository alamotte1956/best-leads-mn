"""Owner-only QuickBooks connection, read-only reports and reviewed expense export."""
import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import datetime,timedelta,timezone,date
from decimal import Decimal,InvalidOperation
from urllib.parse import urlencode
from flask import Blueprint,render_template,request,session,redirect,url_for,flash,abort
from sqlalchemy import select,update,inspect
from sqlalchemy.exc import IntegrityError
from national import administrator
from contractor_onboarding import require_csrf
from consumer_requests import PRIVATE_HEADERS
import quickbooks_client as client

quickbooks=Blueprint('quickbooks',__name__)

def now():return datetime.now(timezone.utc)
def aware(value):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def schema_ready():
    from app import db
    return all(inspect(db.engine).has_table(name) for name in ('quickbooks_connections','quickbooks_oauth_attempts','quickbooks_exports'))

def ready():
    if client.readiness() or not schema_ready():abort(503,'Complete the protected QuickBooks configuration and database setup first.')

def connection(required=False):
    from app import QuickBooksConnection
    row=QuickBooksConnection.query.filter_by(environment=client.environment()).populate_existing().first() if schema_ready() else None
    if required and (not row or row.status!='connected' or not row.confirmed_at or row.client_binding!=client.binding()):
        abort(409,'Connect and confirm the correct QuickBooks company first.')
    return row

@quickbooks.after_request
def private(response):response.headers.update(PRIVATE_HEADERS);return response

@quickbooks.app_errorhandler(client.QBOError)
def provider_failure(error):
    from app import db
    db.session.rollback()
    return render_template('error.html',code=502,title='QuickBooks needs attention',message=str(error)),502,PRIVATE_HEADERS

@quickbooks.get('/admin/quickbooks')
@administrator
def overview():
    from app import FinanceEntry,QuickBooksExport
    missing=client.readiness()
    if not schema_ready():missing.append('QuickBooks database migration')
    try:mode=client.environment()
    except client.QBOError:mode='invalid'
    row=connection() if mode!='invalid' else None
    entries=[];exports=[]
    if row and row.confirmed_at and row.status=='connected':
        local_mode='test' if mode=='sandbox' else 'live'
        entries=FinanceEntry.query.filter_by(mode=local_mode,kind='expense',voided_at=None).order_by(FinanceEntry.id.desc()).limit(100).all()
        exports=QuickBooksExport.query.filter_by(environment=mode).order_by(QuickBooksExport.id.desc()).limit(100).all()
    return render_template('quickbooks.html',missing=missing,mode=mode,connection=row,entries=entries,exports=exports,
        exports_enabled=(mode=='sandbox' or os.environ.get('QBO_LIVE_EXPORTS_ENABLED')=='true'))

@quickbooks.post('/admin/quickbooks/connect')
@administrator
def connect():
    from app import db,QuickBooksOAuthAttempt
    require_csrf();ready()
    row=connection()
    if row and row.status=='connected':abort(409,'Disconnect the current company before replacing its authorization.')
    state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);session['qbo_browser_nonce']=nonce
    db.session.add(QuickBooksOAuthAttempt(state_hash=hashlib.sha256(state.encode()).hexdigest(),
        browser_hash=hashlib.sha256(nonce.encode()).hexdigest(),admin_fingerprint=session['admin_password_fingerprint'],
        client_binding=client.binding(),environment=client.environment(),expires_at=now()+timedelta(minutes=10)))
    db.session.commit()
    return redirect(client.AUTHORIZATION+'?'+urlencode(dict(client_id=os.environ['QBO_CLIENT_ID'],redirect_uri=client.CALLBACK,
        response_type='code',scope='com.intuit.quickbooks.accounting',state=state)),code=303)

@quickbooks.get('/admin/quickbooks/callback')
def callback():
    from app import db,QuickBooksOAuthAttempt,QuickBooksConnection
    from admin_session_security import admin_session_valid
    # Never place provider codes into a login redirect or a session cookie.
    if not admin_session_valid(session):abort(400,'Sign in as administrator and restart the QuickBooks connection.')
    ready()
    state=request.args.get('state','');nonce=session.get('qbo_browser_nonce','')
    if not state or len(state)>256 or not nonce:abort(400,'QuickBooks connection state is missing or invalid.')
    attempt=db.session.execute(select(QuickBooksOAuthAttempt).where(QuickBooksOAuthAttempt.state_hash==hashlib.sha256(state.encode()).hexdigest()).with_for_update()).scalar_one_or_none()
    if (not attempt or attempt.consumed_at or aware(attempt.expires_at)<=now()
            or attempt.browser_hash!=hashlib.sha256(nonce.encode()).hexdigest()
            or attempt.admin_fingerprint!=session.get('admin_password_fingerprint')
            or attempt.client_binding!=client.binding() or attempt.environment!=client.environment()):
        db.session.rollback();abort(400,'QuickBooks connection expired or does not match this browser. Restart it.')
    claimed=db.session.execute(update(QuickBooksOAuthAttempt).where(QuickBooksOAuthAttempt.id==attempt.id,QuickBooksOAuthAttempt.consumed_at.is_(None)).values(consumed_at=now())).rowcount
    db.session.commit();session.pop('qbo_browser_nonce',None)
    if claimed!=1:abort(400,'This QuickBooks connection attempt was already used.')
    if request.args.get('error'):
        flash('QuickBooks connection was not authorized. Your existing records were not changed.','error')
        return redirect(url_for('quickbooks.overview'),code=303)
    code=request.args.get('code','');realm=request.args.get('realmId','')
    if not code or len(code)>4096 or not re.fullmatch(r'[0-9]{1,30}',realm):abort(400,'Intuit did not return a valid authorization code and company.')
    row=connection()
    if row and row.status=='connected':abort(409,'A company was connected in another session. Review it before reconnecting.')
    tokens=client.token_data(client.token_request(dict(grant_type='authorization_code',code=code,redirect_uri=client.CALLBACK)))
    info=client.raw_api(client.environment(),realm,tokens['access_token'],'/companyinfo/'+realm).get('CompanyInfo',{})
    # CompanyInfo.Id identifies the CompanyInfo entity (often "1"), not the OAuth realm.
    if not re.fullmatch(r'[0-9]{1,30}',str(info.get('Id',''))) or not isinstance(info.get('CompanyName'),str) or not info['CompanyName'].strip():
        raise client.QBOError('The selected QuickBooks company could not be verified. Restart the connection.')
    if row is None:
        row=QuickBooksConnection(environment=client.environment(),realm_id=realm,company_name=info['CompanyName'][:255],client_binding=client.binding())
        db.session.add(row)
    row.realm_id=realm;row.company_name=info['CompanyName'][:255];row.encrypted_tokens=client.seal(tokens)
    row.client_binding=client.binding();row.status='connected';row.confirmed_at=None
    try:db.session.commit()
    except IntegrityError:
        db.session.rollback();abort(409,'A connection was saved concurrently. Review the connected company before continuing.')
    flash('Authorization received. Confirm the company before reading reports or exporting expenses.','success')
    return redirect(url_for('quickbooks.overview'),code=303)

@quickbooks.post('/admin/quickbooks/confirm')
@administrator
def confirm():
    from app import db
    require_csrf();ready();row=connection()
    if (not row or row.status!='connected' or row.client_binding!=client.binding() or request.form.get('realm_id')!=row.realm_id
            or request.form.get('connection_id')!=str(row.id) or request.form.get('confirm_company')!='yes'):
        abort(409,'Review and confirm the currently connected company.')
    row.confirmed_at=now();db.session.commit()
    return redirect(url_for('quickbooks.overview'),code=303)

@quickbooks.post('/admin/quickbooks/disconnect')
@administrator
def disconnect():
    from app import db,QuickBooksOAuthAttempt
    require_csrf()
    if not schema_ready():abort(503,'QuickBooks schema setup is required.')
    row=connection()
    if not row:return redirect(url_for('quickbooks.overview'),code=303)
    if request.form.get('connection_id')!=str(row.id) or request.form.get('realm_id')!=row.realm_id:abort(409,'The connected company changed. Review it before disconnecting.')
    try:tokens=client.unseal(row.encrypted_tokens) if row.encrypted_tokens else None
    except client.QBOError:tokens=None
    if row.encrypted_tokens and (not tokens or not os.environ.get('QBO_CLIENT_ID') or not os.environ.get('QBO_CLIENT_SECRET')):
        flash('Local access stopped. Also disconnect this app in QuickBooks because provider revocation could not be verified.','error')
        tokens=None
    if tokens:
        credential=__import__('base64').b64encode((os.environ['QBO_CLIENT_ID']+':'+os.environ['QBO_CLIENT_SECRET']).encode()).decode()
        try:client.transport(client.REVOKE,'POST',json.dumps({'token':tokens['refresh_token']}).encode(),{'Authorization':'Basic '+credential,'Content-Type':'application/json'})
        except client.QBOError:
            # Stop local access even if provider revocation was not confirmed.
            flash('Local access stopped. Intuit did not confirm revocation; also disconnect this app in QuickBooks.','error')
    row.encrypted_tokens=None;row.status='disconnected';row.confirmed_at=None
    db.session.execute(update(QuickBooksOAuthAttempt).where(QuickBooksOAuthAttempt.environment==client.environment(),QuickBooksOAuthAttempt.consumed_at.is_(None)).values(consumed_at=now()))
    db.session.commit();session.pop('qbo_browser_nonce',None)
    return redirect(url_for('quickbooks.overview'),code=303)


def report_period():
    from owner_finance import CENTRAL
    today=now().astimezone(CENTRAL).date()
    try:
        start=date.fromisoformat(request.args.get('start',today.replace(day=1).isoformat()));end=date.fromisoformat(request.args.get('end',today.isoformat()))
    except ValueError:abort(400,'Choose valid report dates.')
    basis=request.args.get('basis','Cash')
    if end<start or (end-start).days>183 or basis not in ('Cash','Accrual'):abort(400,'Choose a date range of at most 184 days and Cash or Accrual accounting.')
    return start,end,basis

def report_lines(rows,depth=0):
    if depth>8:raise client.QBOError('QuickBooks returned an unsupported report layout.')
    result=[]
    for row in rows.get('Row',[]):
        for kind in ('Header','ColData'):
            values=row.get(kind,{}).get('ColData',[]) if kind=='Header' else row.get(kind,[])
            if values:result.append(dict(depth=depth,label=str(values[0].get('value',''))[:255],amount=str(values[-1].get('value',''))[:80] if len(values)>1 else ''))
        if row.get('Rows'):result.extend(report_lines(row['Rows'],depth+1))
        if row.get('Summary'):
            values=row['Summary'].get('ColData',[])
            if values:result.append(dict(depth=depth,label=str(values[0].get('value',''))[:255],amount=str(values[-1].get('value',''))[:80] if len(values)>1 else ''))
        if len(result)>2000:raise client.QBOError('Choose a shorter QuickBooks report period.')
    return result

@quickbooks.get('/admin/quickbooks/profit-and-loss')
@administrator
def profit_and_loss():
    ready();row=connection(True);start,end,basis=report_period()
    data=client.api(row.id,'/reports/ProfitAndLoss',dict(start_date=start.isoformat(),end_date=end.isoformat(),accounting_method=basis,summarize_column_by='Total'),expected_realm=row.realm_id)
    header=data.get('Header',{})
    if (header.get('ReportName')!='ProfitAndLoss' or header.get('StartPeriod')!=start.isoformat()
            or header.get('EndPeriod')!=end.isoformat() or header.get('ReportBasis')!=basis):
        raise client.QBOError('QuickBooks did not confirm the requested report period and accounting basis.')
    return render_template('quickbooks_report.html',connection=row,mode=client.environment(),header=header,
        lines=report_lines(data.get('Rows',{})),start=start,end=end,basis=basis,
        no_data=any(o.get('Name')=='NoReportData' and str(o.get('Value')).lower()=='true' for o in header.get('Option',[])))


def source_hash(entry):
    return hashlib.sha256(json.dumps([entry.id,entry.mode,entry.occurred_on.isoformat(),entry.kind,entry.category,entry.description,entry.amount_cents,entry.state_code,entry.voided_at is not None],separators=(',',':')).encode()).hexdigest()

def export_entry(entry_id):
    from app import db,FinanceEntry
    entry=db.session.get(FinanceEntry,entry_id)
    expected='test' if client.environment()=='sandbox' else 'live'
    if not entry or entry.kind!='expense' or entry.mode!=expected or entry.voided_at:abort(409,'Choose a current expense in the matching test/live environment.')
    return entry

def account_choices(row):
    data=client.api(row.id,'/query',{'query':'select * from Account where Active = true maxresults 1000'},expected_realm=row.realm_id)
    accounts=data.get('QueryResponse',{}).get('Account',[])
    return ([a for a in accounts if a.get('AccountType') in ('Expense','Other Expense','Cost of Goods Sold')],
            [a for a in accounts if a.get('AccountType') in ('Bank','Credit Card')])

@quickbooks.get('/admin/quickbooks/expenses/<int:entry_id>')
@administrator
def expense_review(entry_id):
    ready();row=connection(True);entry=export_entry(entry_id)
    expenses,funding=account_choices(row)
    return render_template('quickbooks_expense.html',connection=row,mode=client.environment(),entry=entry,expenses=expenses,funding=funding,source_hash=source_hash(entry),
        exports_enabled=client.environment()=='sandbox' or os.environ.get('QBO_LIVE_EXPORTS_ENABLED')=='true')


def purchase_matches(actual,payload):
    try:
        if not re.fullmatch(r'[0-9]{1,30}',str(actual.get('Id',''))):return False
        if (actual.get('TxnDate')!=payload['TxnDate'] or actual.get('PrivateNote')!=payload['PrivateNote']
            or actual.get('PaymentType')!=payload['PaymentType'] or actual.get('AccountRef',{}).get('value')!=payload['AccountRef']['value']):return False
        lines=actual.get('Line',[])
        return (len(lines)==1 and Decimal(str(actual['TotalAmt']))==Decimal(str(payload['TotalAmt']))
            and Decimal(str(lines[0]['Amount']))==Decimal(str(payload['Line'][0]['Amount']))
            and lines[0].get('AccountBasedExpenseLineDetail',{}).get('AccountRef',{}).get('value')==payload['Line'][0]['AccountBasedExpenseLineDetail']['AccountRef']['value'])
    except (KeyError,TypeError,InvalidOperation):return False

@quickbooks.post('/admin/quickbooks/expenses/<int:entry_id>/export')
@administrator
def expense_export(entry_id):
    from app import db,QuickBooksExport
    require_csrf();ready();row=connection(True)
    realm=row.realm_id
    if client.environment()=='production' and os.environ.get('QBO_LIVE_EXPORTS_ENABLED')!='true':abort(503,'Live QuickBooks writes are disabled pending sandbox validation and account mapping review.')
    entry=export_entry(entry_id)
    previous=QuickBooksExport.query.filter_by(environment=client.environment(),finance_entry_id=entry.id).first()
    if previous:
        if previous.status=='sent':return redirect(url_for('quickbooks.overview'),code=303)
        abort(409,'This expense has an unconfirmed export. Reconcile it with QuickBooks before creating any correction.')
    if request.form.get('source_hash')!=source_hash(entry) or request.form.get('confirm_export')!='yes':abort(409,'Review the current expense and explicitly confirm its export.')
    expenses,funding=account_choices(row)
    expense_id=request.form.get('expense_account','');funding_id=request.form.get('funding_account','')
    expense=next((a for a in expenses if str(a.get('Id'))==expense_id),None)
    paid_from=next((a for a in funding if str(a.get('Id'))==funding_id),None)
    if not expense or not paid_from:abort(400,'Select active expense and payment accounts from the connected company.')
    # Currency must be verified; never silently book USD into a foreign home currency.
    preferences=client.api(row.id,'/preferences',expected_realm=realm).get('Preferences',{})
    if preferences.get('CurrencyPrefs',{}).get('HomeCurrency',{}).get('value')!='USD':
        abort(409,'A USD home currency must be verified before exporting these USD expenses.')
    # Recheck after provider reads; a local correction could have occurred meanwhile.
    db.session.refresh(entry)
    if entry.voided_at or request.form.get('source_hash')!=source_hash(entry):abort(409,'The expense changed. Review it again.')
    key='rcusa-'+uuid.uuid4().hex
    amount=float(Decimal(entry.amount_cents)/100)
    payload=dict(TxnDate=entry.occurred_on.isoformat(),PaymentType='CreditCard' if paid_from['AccountType']=='Credit Card' else 'Cash',
        AccountRef={'value':funding_id},PrivateNote='RCUSA expense export '+key,TotalAmt=amount,
        Line=[dict(Amount=amount,Description=entry.description,DetailType='AccountBasedExpenseLineDetail',AccountBasedExpenseLineDetail={'AccountRef':{'value':expense_id}})])
    record=QuickBooksExport(environment=client.environment(),realm_id=realm,finance_entry_id=entry.id,
        request_id=key,payload_json=json.dumps(payload),source_hash=source_hash(entry),status='sending')
    db.session.add(record)
    try:db.session.commit()
    except IntegrityError:
        db.session.rollback();abort(409,'Another session already started this expense export. Review export history.')
    try:
        actual=client.api(row.id,'/purchase',{'requestid':key},payload,expected_realm=realm).get('Purchase',{})
        if not purchase_matches(actual,payload):raise client.QBOError('QuickBooks did not confirm the exact expense. Review its transaction before reconciling.')
        db.session.refresh(record,with_for_update=True)
        if record.status=='sent' and record.external_id!=str(actual['Id']):
            raise client.QBOError('A different matching transaction was already reconciled. Review QuickBooks for duplicates.')
        record.status='sent';record.external_id=str(actual['Id']);record.completed_at=now();db.session.commit()
    except client.QBOError:
        db.session.execute(update(QuickBooksExport).where(QuickBooksExport.id==record.id,QuickBooksExport.status=='sending').values(status='uncertain'))
        db.session.commit();raise
    flash('Expense recorded in QuickBooks. It remains the same local expense, not a second local cost.','success')
    return redirect(url_for('quickbooks.overview'),code=303)

@quickbooks.post('/admin/quickbooks/exports/<int:export_id>/reconcile')
@administrator
def reconcile(export_id):
    from app import db,QuickBooksExport
    require_csrf();ready();row=connection(True);record=db.session.get(QuickBooksExport,export_id)
    if not record or record.environment!=client.environment() or record.realm_id!=row.realm_id:abort(404)
    external=request.form.get('external_id','')
    if not re.fullmatch(r'[0-9]{1,30}',external):abort(400,'Enter the existing QuickBooks Purchase transaction ID.')
    if record.status=='sent':
        if record.external_id!=external:abort(409,'A confirmed export cannot be reassigned to a different transaction.')
        return redirect(url_for('quickbooks.overview'),code=303)
    actual=client.api(row.id,'/purchase/'+external,expected_realm=row.realm_id).get('Purchase',{})
    if not purchase_matches(actual,json.loads(record.payload_json)):abort(409,'That transaction does not match the immutable exported expense.')
    record.status='sent';record.external_id=external;record.completed_at=now();db.session.commit()
    return redirect(url_for('quickbooks.overview'),code=303)

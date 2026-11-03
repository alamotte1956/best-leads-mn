"""Opt-in PostgreSQL checks. Only loopback test_* databases are accepted.

Uses a randomly named test schema, never public or a production database.
Run separately from tests/ because those tests intentionally force SQLite.
"""
import os
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import create_engine,text,update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
schema='rcusa_test_'+uuid.uuid4().hex
base_engine=None
app=db=None


def validate_target(value):
    url=make_url(value)
    if (url.get_backend_name()!='postgresql' or url.host not in ('localhost','127.0.0.1','::1')
            or not (url.database or '').startswith('test_') or url.query):
        raise ValueError('PostgreSQL checks accept only a loopback test_* database. Production URLs are refused.')
    return url


def setUpModule():
    global base_engine,app,db
    value=os.environ.get('POSTGRES_TEST_URL','')
    if not value:raise unittest.SkipTest('POSTGRES_TEST_URL is not configured; no PostgreSQL checks executed.')
    url=validate_target(value)
    base_engine=create_engine(url)
    with base_engine.begin() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped=url.set(query={**url.query,'options':'-csearch_path='+schema})
    os.environ['DATABASE_URL']=scoped.render_as_string(hide_password=False)
    os.environ['SECRET_KEY']='isolated-postgres-tests-only'
    for flag in ('EMAIL_SENDING_ENABLED','SMS_SENDING_ENABLED','PAYMENTS_ENABLED','ENABLE_LIVE_MATCHING'):
        os.environ[flag]='false'
    from app import app as application,db as database
    app=application;db=database
    with app.app_context():
        if db.session.execute(text('SELECT current_schema()')).scalar_one()!=schema:
            raise RuntimeError('Test schema isolation failed; refusing all writes.')
        db.session.rollback();db.create_all()


def tearDownModule():
    if app is not None:
        with app.app_context():db.session.remove();db.engine.dispose()
    if base_engine is not None:
        # schema is generated above, never accepted from an argument/environment.
        with base_engine.begin() as connection:connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        base_engine.dispose()


class PostgresConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.ctx=app.app_context();self.ctx.push()
        self.assertEqual(db.session.execute(text('SELECT current_schema()')).scalar_one(),schema)
        db.session.rollback();db.drop_all();db.create_all()
        from app import Contractor,Lead
        c=Contractor(company_name='Synthetic',contact_name='Owner',email='synthetic@example.com',phone='6125550100',
            zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False)
        lead=Lead(homeowner_name='Synthetic',phone='6125550199',zip_code='55401',service_needed='Mold Remediation',status='New')
        db.session.add_all([c,lead]);db.session.commit();self.contractor_id=c.id;self.lead_id=lead.id

    def tearDown(self):db.session.remove();self.ctx.pop()

    def offer(self):
        from app import LeadOffer
        row=LeadOffer(lead_id=self.lead_id,contractor_id=self.contractor_id,status='pending',
            offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(row);db.session.commit();return row.id

    def test_sequential_matching_concurrency_creates_exactly_one_pending_offer(self):
        def attempt(_):
            with app.app_context():
                from app import Contractor,Lead,LeadOffer
                from contractor_offer_advancement import advance_sequential_offer
                result=advance_sequential_offer(db.session,db.session.get(Lead,self.lead_id),Contractor.query.all(),LeadOffer)
                created=result['new_offer'] is not None;db.session.commit();return created
        with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),1)
        from app import LeadOffer
        self.assertEqual(LeadOffer.query.filter_by(lead_id=self.lead_id,status='pending').count(),1)

    def test_acceptance_concurrency_commits_exactly_once(self):
        identifier=self.offer()
        def attempt(_):
            with app.app_context():
                from contractor_offer_transactions import accept_contractor_offer
                result=accept_contractor_offer(db.session,identifier,self.contractor_id)
                db.session.commit();return result is not None
        with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),1)

    def test_shared_request_concurrent_acceptance_never_exceeds_three(self):
        from app import Contractor, LeadOffer, LeadMatchPreference
        db.session.add(LeadMatchPreference(lead_id=self.lead_id,contractor_limit=3))
        ids=[]
        for i in range(4):
            contractor=Contractor(company_name='Synthetic Shared '+str(i),contact_name='Owner',
                email=f'shared{i}@example.com',phone='6125550100',zip_codes='55401',
                service_type='Mold Remediation',active=True,verified=True,is_test=False)
            db.session.add(contractor);db.session.flush()
            offer=LeadOffer(lead_id=self.lead_id,contractor_id=contractor.id,status='pending',
                offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),
                expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
            db.session.add(offer);db.session.flush();ids.append((offer.id,contractor.id))
        db.session.commit()
        def accept(pair):
            with app.app_context():
                from contractor_offer_transactions import accept_contractor_offer
                row=accept_contractor_offer(db.session,*pair);db.session.commit();return row is not None
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sum(pool.map(accept,ids)),3)
        db.session.expire_all()
        self.assertEqual(LeadOffer.query.filter_by(lead_id=self.lead_id,status='accepted').count(),3)

    def test_cancellation_and_acceptance_leave_no_pending_offer(self):
        identifier=self.offer()
        def accept():
            with app.app_context():
                from contractor_offer_transactions import accept_contractor_offer
                accept_contractor_offer(db.session,identifier,self.contractor_id);db.session.commit()
        def close():
            with app.app_context():
                from lead_lifecycle import end_matching
                end_matching(self.lead_id,'Closed',actor='administrator');db.session.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(accept),pool.submit(close)]
            for future in futures:future.result()
        from app import Lead,LeadOffer
        db.session.expire_all();self.assertEqual(db.session.get(Lead,self.lead_id).status,'Closed')
        self.assertIn(db.session.get(LeadOffer,identifier).status,('accepted','cancelled'))

    def reward_models(self):
        from app import RewardBusiness,RewardCredit,RewardMonth,RewardSpin
        return RewardBusiness,RewardCredit,RewardMonth,RewardSpin

    def test_combined_purchase_free_first_month_concurrency_commits_ten(self):
        from reward_transactions import issue_credit,consume_credit
        models=self.reward_models();Business,Credit,Month,Spin=models
        business=Business(identity_digest='a'*64,verified=True);db.session.add(business);db.session.commit();identifier=business.id
        ids=[issue_credit(db,models,identifier,'mixed-'+str(i),'free' if i%2 else 'purchase').id for i in range(18)]
        db.session.commit()
        def attempt(credit):
            with app.app_context():
                try:
                    consume_credit(db,models,identifier,credit,datetime(2026,11,15,tzinfo=timezone.utc));db.session.commit();return True
                except ValueError:db.session.rollback();return False
        with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(attempt,ids)),10)
        db.session.expire_all();self.assertEqual(db.session.get(Month,(identifier,'2026-11')).used,10)
        self.assertEqual(Spin.query.count(),10)

    def test_duplicate_credit_source_concurrency_issues_once(self):
        from reward_transactions import issue_credit
        models=self.reward_models();Business,Credit,_,_=models
        business=Business(identity_digest='b'*64,verified=True);db.session.add(business);db.session.commit();identifier=business.id
        def attempt(_):
            with app.app_context():
                try:
                    issue_credit(db,models,identifier,'same-provider-event','purchase');db.session.commit();return True
                except IntegrityError:db.session.rollback();return False
        with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),1)
        self.assertEqual(Credit.query.count(),1)

    def test_checkout_reconciliation_cannot_overwrite_concurrent_payment(self):
        from app import Payment,LeadOffer
        from checkout_reconciliation import reconcile_payment
        from unittest.mock import patch
        from threading import Event
        identifier=self.offer()
        offer=db.session.get(LeadOffer,identifier);offer.status='accepted'
        row=Payment(offer_id=identifier,contractor_id=self.contractor_id,
            amount_cents=2500,currency='usd',price_id='synthetic',mode='test',
            status='open',session_id='cs_postgres_synthetic',
            quote_expires_at=datetime.now(timezone.utc)-timedelta(minutes=1))
        db.session.add(row);db.session.commit();payment_id=row.id
        obj={'id':row.session_id,'mode':'payment','livemode':False,'status':'open',
             'payment_status':'unpaid','amount_total':2500,'currency':'usd',
             'metadata':{'payment_id':str(payment_id),'contractor_id':str(self.contractor_id)}}
        ready=Event();paid=Event()
        def payment_callback():
            if not ready.wait(10):raise RuntimeError('Reconciliation did not reach provider call.')
            with app.app_context():
                db.session.execute(update(Payment).where(Payment.id==payment_id).values(
                    status='paid',paid_at=datetime.now(timezone.utc),payment_intent='pi_concurrent'))
                db.session.commit()
            paid.set()
        def expire(*args,**kwargs):
            ready.set()
            if not paid.wait(10):raise RuntimeError('Payment callback did not commit.')
            return {**obj,'status':'expired'}
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(payment_callback)
            with patch.dict(os.environ,{'STRIPE_MODE':'test'}),patch('billing.retrieve_checkout',return_value=obj),patch('billing.expire_checkout',side_effect=expire):
                self.assertEqual(reconcile_payment(row,api_key='sk_test_synthetic'),'changed')
                db.session.commit()
            future.result()
        db.session.expire_all();row=db.session.get(Payment,payment_id)
        self.assertEqual(row.status,'paid');self.assertEqual(row.payment_intent,'pi_concurrent')

    def test_quote_history_migration_preserves_legacy_order(self):
        from app import Payment
        identifier=self.offer()
        row=Payment(offer_id=identifier,contractor_id=self.contractor_id,
            amount_cents=2500,currency='usd',price_id='synthetic',mode='test',
            status='open',session_id='cs_legacy_synthetic')
        db.session.add(row);db.session.commit();payment_id=row.id
        db.session.remove()
        migration=Path(__file__).resolve().parents[1]/'migrations'/'019_checkout_quote_history.sql'
        with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            self.assertEqual(connection.execute(text('SELECT current_schema()')).scalar_one(),schema)
            connection.execute(text('DROP TABLE checkout_quote_history'))
            connection.execute(text('ALTER TABLE lead_payments DROP COLUMN quote_version'))
            with connection.connection.cursor() as cursor:
                cursor.execute(migration.read_text())
                cursor.execute(migration.read_text())
            preserved=connection.execute(text('SELECT amount_cents,session_id,status,mode,quote_version FROM lead_payments WHERE id=:id'),{'id':payment_id}).one()
            self.assertEqual(tuple(preserved),(2500,'cs_legacy_synthetic','open','test',1))
            self.assertEqual(connection.execute(text('SELECT COUNT(*) FROM checkout_quote_history')).scalar_one(),0)


    def test_consumer_recovery_link_is_consumed_exactly_once_under_concurrency(self):
        import re
        from app import Lead, Delivery, AccessRecoveryToken
        lead=db.session.get(Lead,self.lead_id);lead.email='recovery@example.com';db.session.commit()
        client=app.test_client()
        with client.session_transaction() as state: state['_csrf']='isolated-recovery-csrf'
        response=client.post('/request-access',data={'_csrf':'isolated-recovery-csrf','email':'recovery@example.com'})
        self.assertEqual(response.status_code,303)
        notice=Delivery.query.filter_by(recipient='recovery@example.com').one()
        path=re.search(r'https://www\.restorationcontractorsmn\.com([^\s]+)',notice.body).group(1)
        def consume(_):
            with app.test_client() as separate:
                with separate.session_transaction() as state: state['_csrf']='isolated-consume-csrf'
                return separate.post(path,data={'_csrf':'isolated-consume-csrf'}).status_code==303
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(consume,range(8))),1)
        db.session.expire_all();self.assertIsNotNone(AccessRecoveryToken.query.one().used_at)

    def test_concurrent_evidence_imports_preserve_one_immutable_observation_and_type(self):
        from market_pricing import import_benchmark_records
        from app import MarketBenchmark,BenchmarkMatchType
        observed=datetime.now(timezone.utc)-timedelta(seconds=1)
        def import_one(index):
            with app.app_context():
                data=dict(state_code='MN',service_name='Mold Remediation',zip_code='55401',
                    contractor_limit=3,observed_at=observed,angi_cents=10000+index,thumbtack_cents=8000,
                    angi_reference='synthetic-angi',thumbtack_reference='synthetic-thumbtack',
                    comparison_basis='comparable_contractor_lead_fee',import_key='synthetic-concurrent-evidence')
                try:
                    return import_benchmark_records([data])
                except (ValueError,IntegrityError):
                    db.session.rollback()
                    return 0
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(import_one,range(8))),1)
        self.assertEqual(MarketBenchmark.query.count(),1)
        self.assertEqual(BenchmarkMatchType.query.count(),1)
        self.assertEqual(BenchmarkMatchType.query.one().contractor_limit,3)
        self.assertEqual(BenchmarkMatchType.query.one().benchmark_id,MarketBenchmark.query.one().id)

    def test_quickbooks_callback_replay_and_refresh_are_serialized(self):
        import hashlib,time
        from unittest.mock import patch
        from cryptography.fernet import Fernet
        from app import QuickBooksConnection,QuickBooksOAuthAttempt
        from admin_session_security import current_password_fingerprint
        import quickbooks_client as provider
        env={'QBO_ENABLED':'true','QBO_ENVIRONMENT':'sandbox','QBO_CLIENT_ID':'synthetic-ci-qbo',
             'QBO_CLIENT_SECRET':'synthetic-ci-secret','QBO_TOKEN_KEY':Fernet.generate_key().decode(),'ADMIN_PASSWORD_HASH':'synthetic-ci-owner'}
        with patch.dict(os.environ,env):
            state='synthetic-shared-qbo-state';nonce='synthetic-shared-browser'
            db.session.add(QuickBooksOAuthAttempt(state_hash=hashlib.sha256(state.encode()).hexdigest(),browser_hash=hashlib.sha256(nonce.encode()).hexdigest(),
                admin_fingerprint=current_password_fingerprint(),client_binding=provider.binding(),environment='sandbox',expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)))
            db.session.commit()
            def finish(_):
                with app.test_client() as browser:
                    with browser.session_transaction() as session:
                        session.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint(),qbo_browser_nonce=nonce)
                    return browser.get('/admin/quickbooks/callback',query_string={'state':state,'code':'synthetic-ci-code','realmId':'93410001'}).status_code
            reply={'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires_in':3600,'x_refresh_token_expires_in':86400}
            with patch.object(provider,'token_request',return_value=reply) as token,patch.object(provider,'raw_api',return_value={'CompanyInfo':{'Id':'1','CompanyName':'Synthetic sandbox'}}):
                with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(finish,range(8)))
                self.assertEqual(results.count(303),1);self.assertEqual(results.count(400),7);self.assertEqual(token.call_count,1)
            self.assertEqual(QuickBooksConnection.query.count(),1)
            row=QuickBooksConnection.query.one();tokens=provider.unseal(row.encrypted_tokens);tokens['access_expires']=time.time()-1;row.encrypted_tokens=provider.seal(tokens);db.session.commit();connection_id=row.id
            def read(_):
                with app.app_context():
                    try:return provider.api(connection_id,'/preferences',expected_realm='93410001')=={'synthetic':True}
                    finally:db.session.remove()
            with patch.object(provider,'token_request',return_value=reply) as token,patch.object(provider,'raw_api',return_value={'synthetic':True}):
                with ThreadPoolExecutor(max_workers=8) as pool:self.assertTrue(all(pool.map(read,range(8))))
                self.assertEqual(token.call_count,1)

    def test_quickbooks_concurrent_expense_export_sends_once(self):
        import time,copy
        from unittest.mock import patch
        from cryptography.fernet import Fernet
        from app import QuickBooksConnection,QuickBooksExport,FinanceEntry
        from admin_session_security import current_password_fingerprint
        from quickbooks import source_hash
        import quickbooks_client as provider
        env={'QBO_ENABLED':'true','QBO_ENVIRONMENT':'sandbox','QBO_CLIENT_ID':'synthetic-ci-qbo','QBO_CLIENT_SECRET':'synthetic-ci-secret','QBO_TOKEN_KEY':Fernet.generate_key().decode(),'ADMIN_PASSWORD_HASH':'synthetic-ci-owner'}
        with patch.dict(os.environ,env):
            connection=QuickBooksConnection(environment='sandbox',realm_id='93410001',company_name='Synthetic sandbox',client_binding=provider.binding(),encrypted_tokens=provider.seal({'access_token':'synthetic-access','refresh_token':'synthetic-refresh','access_expires':time.time()+3600,'refresh_expires':time.time()+86400}),status='connected',confirmed_at=datetime.now(timezone.utc))
            entry=FinanceEntry(entry_key='synthetic-concurrent-qbo-expense',occurred_on=datetime.now(timezone.utc).date(),kind='expense',category='Hosting',description='Synthetic hosting',amount_cents=2525,mode='test')
            db.session.add_all([connection,entry]);db.session.commit();entry_id=entry.id;fingerprint=source_hash(entry)
            def raw(mode,realm,token,path,params=None,payload=None):
                if path=='/query':return {'QueryResponse':{'Account':[{'Id':'10','Name':'Hosting','AccountType':'Expense'},{'Id':'20','Name':'Bank','AccountType':'Bank'}]}}
                if path=='/preferences':return {'Preferences':{'CurrencyPrefs':{'HomeCurrency':{'value':'USD'}}}}
                if path=='/purchase':return {'Purchase':dict(copy.deepcopy(payload),Id='81')}
                raise AssertionError(path)
            def send(_):
                with app.test_client() as browser:
                    with browser.session_transaction() as session:session.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint(),_csrf='synthetic-qbo-csrf')
                    return browser.post(f'/admin/quickbooks/expenses/{entry_id}/export',data={'_csrf':'synthetic-qbo-csrf','source_hash':fingerprint,'expense_account':'10','funding_account':'20','confirm_export':'yes'}).status_code
            with patch.object(provider,'raw_api',side_effect=raw) as api:
                with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(send,range(8)))
                self.assertTrue(all(status in (303,409) for status in results),results)
                self.assertEqual(len([call for call in api.call_args_list if call.args[3]=='/purchase']),1)
            self.assertEqual(QuickBooksExport.query.count(),1);self.assertEqual(QuickBooksExport.query.one().status,'sent')
            from apply_quickbooks_schema import main
            main();main();self.assertEqual(FinanceEntry.query.count(),1);self.assertEqual(QuickBooksExport.query.count(),1)

    def test_all_additive_migrations_can_run_twice_in_isolated_schema(self):
        db.session.remove()
        with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            self.assertEqual(connection.execute(text('SELECT current_schema()')).scalar_one(),schema)
            for iteration in range(2):
                for migration in sorted((Path(__file__).resolve().parents[1]/'migrations').glob('*.sql')):
                    # Migration bodies contain literal LIKE '%' and format('%I')
                    # expressions. No DBAPI parameter mapping may be supplied:
                    # psycopg2 otherwise treats these SQL literals as placeholders.
                    with self.subTest(migration=migration.name,iteration=iteration):
                        with connection.connection.cursor() as cursor:
                            try:
                                cursor.execute(migration.read_text(encoding='utf-8-sig'))
                            except Exception:
                                cursor.execute('ROLLBACK')
                                raise


if __name__=='__main__':unittest.main(verbosity=2)

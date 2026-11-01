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
from sqlalchemy import create_engine,text
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

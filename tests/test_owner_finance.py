import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import csv
import io
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from app import app,db,Contractor,Lead,LeadOffer,LeadMarket,Payment,FinanceEntry,FinanceReview
from owner_finance import report_data,amount_cents

class OwnerFinanceTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-finance-admin','EMAIL_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()
        self.contractor=Contractor(company_name='Synthetic Business',contact_name='Owner',email='finance@example.com',phone='6125550100',zip_codes='55401')
        db.session.add(self.contractor);db.session.commit();self.admin()
        self.fields=dict(_csrf='finance-csrf',start='2026-11-01',end='2026-11-30',mode='live',state='ALL')
    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()
    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as s:s.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint(),_csrf='finance-csrf')
    def payment(self,amount=10000,refund=0,mode='live',state='MN',status='paid',paid=None,currency='usd'):
        lead=Lead(homeowner_name='Synthetic Private Consumer',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.flush()
        if state!='MN':db.session.add(LeadMarket(lead_id=lead.id,state_code=state,intake_brand='USA'))
        offer=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='accepted',expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer);db.session.flush()
        p=Payment(offer_id=offer.id,contractor_id=self.contractor.id,amount_cents=amount,refunded_cents=refund,mode=mode,status=status,currency=currency,price_id='synthetic',paid_at=paid or datetime(2026,11,5,12,tzinfo=timezone.utc))
        db.session.add(p);db.session.commit();return p
    def entry(self,**extra):
        data=dict(self.fields,entry_key='synthetic-entry-key-1234567890',occurred_on='2026-11-05',kind='expense',category='Advertising',description='Synthetic advertising invoice',amount='25.25',entry_state='ALL');data.update(extra)
        return self.client.post('/admin/finance/entries',data=data)
    def report(self,state='ALL',mode='live'):return report_data(date(2026,11,1),date(2026,11,30),mode,state)
    def test_profit_uses_confirmed_receipts_refunds_and_costs_without_double_counting_fees(self):
        self.payment(amount=10000,refund=2000);self.payment(amount=99999,mode='test');self.payment(amount=88888,status='open');self.payment(amount=77777,currency='cad')
        self.assertEqual(self.entry().status_code,303)
        self.assertEqual(self.entry(entry_key='synthetic-fee-key-1234567890',category='Payment processing',amount='3.00').status_code,303)
        result=self.report();self.assertEqual((result['gross'],result['refunds'],result['net'],result['costs'],result['fees'],result['result']),(10000,2000,8000,2825,300,5175))
        self.assertFalse(result['costs_reviewed'])
        page=self.client.get('/admin/finance?start=2026-11-01&end=2026-11-30')
        self.assertEqual(page.status_code,200);self.assertIn('Costs not confirmed',page.text);self.assertIn('$51.75',page.text);self.assertNotIn('Synthetic Private Consumer',page.text)
        self.assertIn('no-store',page.headers['Cache-Control'])
    def test_duplicate_post_is_idempotent_and_conflicting_reuse_is_rejected(self):
        self.assertEqual(self.entry().status_code,303);self.assertEqual(self.entry().status_code,303)
        self.assertEqual(FinanceEntry.query.count(),1);self.assertEqual(self.entry(amount='99.00').status_code,409)
    def test_cost_review_is_invalidated_and_void_preserves_audit(self):
        self.entry();row=FinanceEntry.query.one()
        self.assertEqual(self.client.post('/admin/finance/review',data=dict(self.fields,confirm_costs='yes')).status_code,303)
        self.assertTrue(self.report()['costs_reviewed'])
        self.assertEqual(self.client.post(f'/admin/finance/entries/{row.id}/void',data=dict(self.fields,reason='Duplicate invoice')).status_code,303)
        db.session.refresh(row);self.assertIsNotNone(row.voided_at);self.assertEqual(row.void_reason,'Duplicate invoice')
        self.assertEqual(FinanceEntry.query.count(),1);self.assertEqual(self.report()['costs'],0);self.assertFalse(self.report()['costs_reviewed'])
    def test_shared_costs_do_not_falsely_appear_as_state_profit(self):
        self.payment(state='TX');self.entry(amount='40.00');self.entry(entry_key='synthetic-texas-key-123456789',entry_state='TX',amount='10.00')
        result=self.report('TX');self.assertEqual((result['result'],result['shared']),(9000,4000));self.assertEqual(self.report()['result'],5000)
        page=self.client.get('/admin/finance?start=2026-11-01&end=2026-11-30&state=TX');self.assertIn('State contribution before shared costs',page.text)
    def test_environment_dates_and_new_income_are_separate(self):
        self.payment(mode='test');self.entry(mode='test',kind='other_income',amount='7.00')
        self.assertEqual(self.report()['net'],0);self.assertEqual(self.report(mode='test')['net'],10700)
        self.assertIn('TEST DATA ONLY',self.client.get('/admin/finance?start=2026-11-01&end=2026-11-30&mode=test').text)
        self.assertEqual(self.client.get('/admin/finance?start=2026-12-01&end=2026-11-01').status_code,400)
        self.assertEqual(self.client.get('/admin/finance?mode=arbitrary').status_code,400)
    def test_central_day_boundary_and_nonpositive_margin(self):
        self.payment(paid=datetime(2026,11,1,4,tzinfo=timezone.utc)) # October 31 Central.
        self.assertEqual(self.report()['gross'],0);self.entry();self.assertEqual(self.report()['result'],-2525);self.assertIsNone(self.report()['margin'])
    def test_auth_csrf_decimal_validation_and_export_formula_safety(self):
        for value in ('0','-1','1.234','NaN','1e3','1,000','1000001'):
            with self.assertRaises(ValueError):amount_cents(value)
        self.assertEqual(self.entry(_csrf='wrong').status_code,400)
        self.entry(description='=HYPERLINK("https://example.invalid")')
        response=self.client.get('/admin/finance/export.csv?start=2026-11-01&end=2026-11-30')
        rows=list(csv.reader(io.StringIO(response.text)));self.assertTrue(any(cell.startswith("'=HYPERLINK") for row in rows for cell in row));self.assertIn('no-store',response.headers['Cache-Control'])
        with self.client.session_transaction() as s:s.clear()
        self.assertEqual(self.client.get('/admin/finance').status_code,403);self.assertEqual(self.client.get('/admin/finance/export.csv').status_code,403)
        self.assertEqual(self.entry().status_code,403)

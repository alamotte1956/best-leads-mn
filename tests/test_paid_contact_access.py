import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import app,db,Contractor,Lead,LeadOffer,Payment,ContractorLeadProgress,LeadProgressEvent
from contractor_session_security import create_contractor_session_data
from billing import offer_contact_available


class PaidContactTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z','STRIPE_MODE':'test','PAYMENTS_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()
        self.contractor=Contractor(company_name='Business',contact_name='Owner',email='owner@example.com',phone='6125550100',
            zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,password_hash='synthetic-hash')
        self.lead=Lead(homeowner_name='PRIVATE CONSUMER NAME',phone='6125550199',email='private@example.com',
            zip_code='55401',service_needed='Mold Remediation',description='PRIVATE PROJECT DETAILS',status='New')
        db.session.add_all([self.contractor,self.lead]);db.session.flush()
        self.offer=LeadOffer(contractor_id=self.contractor.id,lead_id=self.lead.id,status='accepted',
            accepted_at=datetime.now(timezone.utc),offered_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(self.offer);db.session.commit()
        with self.client.session_transaction() as s:
            s.update(create_contractor_session_data(self.contractor.id));s['_csrf']='paid-csrf'
            s['contractor_password_fingerprint']=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest()

    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()

    def payment(self,status='open',mode='test'):
        row=Payment(contractor_id=self.contractor.id,offer_id=self.offer.id,amount_cents=2500,currency='usd',
            price_id='synthetic',mode=mode,status=status,paid_at=datetime.now(timezone.utc) if status=='paid' else None)
        db.session.add(row);db.session.commit();return row

    def assert_private(self,response):
        for text in ('PRIVATE CONSUMER NAME','6125550199','private@example.com','PRIVATE PROJECT DETAILS'):
            self.assertNotIn(text,response.text)

    def test_new_accepted_offer_requires_verified_payment_on_every_contact_view(self):
        self.assertFalse(offer_contact_available(self.offer))
        for path in ('/contractor/dashboard','/contractor/leads',f'/contractor/offers/{self.offer.id}/follow-up'):
            response=self.client.get(path);self.assert_private(response)
            self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertEqual(self.client.get(f'/contractor/offers/{self.offer.id}/follow-up').status_code,402)

    def test_unpaid_post_cannot_record_progress_or_expose_draft(self):
        response=self.client.post(f'/contractor/offers/{self.offer.id}/follow-up',data={
            '_csrf':'paid-csrf','version':'0','stage':'contacted','note':'PRIVATE DRAFT'})
        self.assertEqual(response.status_code,402);self.assert_private(response)
        self.assertEqual(ContractorLeadProgress.query.count(),0);self.assertEqual(LeadProgressEvent.query.count(),0)
        self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/follow-up',data={'_csrf':'wrong'}).status_code,400)

    def test_checkout_return_and_unconfirmed_payment_do_not_unlock_contacts(self):
        payment=self.payment('awaiting_payment')
        self.assert_private(self.client.get('/contractor/dashboard?returned=1'))
        payment.status='paid';payment.paid_at=None;db.session.commit()
        self.assertFalse(offer_contact_available(self.offer))

    def test_verified_paid_order_unlocks_owner_and_full_refund_locks_again(self):
        payment=self.payment('paid')
        self.assertTrue(offer_contact_available(self.offer))
        self.assertIn('PRIVATE CONSUMER NAME',self.client.get('/contractor/dashboard').text)
        self.assertEqual(self.client.get(f'/contractor/offers/{self.offer.id}/follow-up').status_code,200)
        payment.refunded_cents=payment.amount_cents;payment.status='refunded';db.session.commit()
        self.assertFalse(offer_contact_available(self.offer));self.assert_private(self.client.get('/contractor/dashboard'))

    def test_test_payment_does_not_unlock_live_or_invalid_mode(self):
        self.payment('paid')
        for mode in ('live','invalid'):
            with patch.dict(os.environ,{'STRIPE_MODE':mode}):
                self.assertFalse(offer_contact_available(self.offer));self.assert_private(self.client.get('/contractor/leads'))

    def test_historical_and_undated_acceptance_keeps_existing_access_without_retroactive_charge(self):
        self.offer.accepted_at=datetime(2019,1,1,tzinfo=timezone.utc);db.session.commit()
        self.assertTrue(offer_contact_available(self.offer))
        self.offer.accepted_at=None;db.session.commit();self.assertTrue(offer_contact_available(self.offer))
        self.assertIn('PRIVATE CONSUMER NAME',self.client.get('/contractor/dashboard').text)

    def test_pending_and_declined_never_unlock_even_with_payment_record(self):
        self.payment('paid')
        for status in ('pending','declined'):
            self.offer.status=status;db.session.commit();self.assertFalse(offer_contact_available(self.offer))
            self.assert_private(self.client.get('/contractor/dashboard'))

    def test_enabled_payments_with_missing_activation_fail_closed(self):
        with patch.dict(os.environ,{'PAYMENTS_ENABLED':'true','PAYMENTS_ACTIVATION_UTC':''}):
            self.assertFalse(offer_contact_available(self.offer));self.assert_private(self.client.get('/contractor/dashboard'))

    def test_test_order_cannot_be_reused_for_live_checkout(self):
        payment=self.payment('open')
        from app import MarketBenchmark
        benchmark=MarketBenchmark(state_code='MN',service_name='Mold Remediation',zip_code='55401',observed_at=datetime.now(timezone.utc),
            angi_cents=4000,thumbtack_cents=3500,angi_reference='synthetic',thumbtack_reference='synthetic',
            comparison_basis='comparable_contractor_lead_fee',import_key='synthetic')
        db.session.add(benchmark);db.session.flush();payment.market_benchmark_id=benchmark.id
        payment.quote_expires_at=datetime.now(timezone.utc)+timedelta(hours=1);db.session.commit()
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'live','STRIPE_LIVE_PAYMENTS_ENABLED':'true',
            'STRIPE_SECRET_KEY':'sk_live_synthetic','PUBLIC_SITE_URL':'https://example.com'}
        with patch.dict(os.environ,config),patch('billing.create_checkout') as send:
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/checkout',data={'_csrf':'paid-csrf'}).status_code,409)
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/quote',data={'_csrf':'paid-csrf'}).status_code,409)
            send.assert_not_called()

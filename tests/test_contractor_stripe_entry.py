import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import time
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from app import app,db,Contractor,Payment
from billing import payment_readiness
from contractor_session_security import create_contractor_session_data


class ContractorStripeEntryTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'PAYMENTS_ENABLED':'true','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z',
            'STRIPE_MODE':'test','STRIPE_SECRET_KEY':'rk_test_synthetic','STRIPE_WEBHOOK_SECRET':'whsec_synthetic',
            'PUBLIC_SITE_URL':'https://example.com','STRIPE_LIVE_PAYMENTS_ENABLED':'false',
            'ADMIN_PASSWORD_HASH':'synthetic-admin','CHECKOUT_RECONCILIATION_ENABLED':'true'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.contractor=Contractor(company_name='Synthetic',contact_name='Owner',email='synthetic@example.com',phone='6125550100',zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,password_hash='synthetic-hash')
        db.session.add(self.contractor);db.session.commit();self.client=app.test_client()
        with self.client.session_transaction() as state:
            state.update(create_contractor_session_data(self.contractor.id));state['contractor_password_fingerprint']=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest();state['_csrf']='synthetic-csrf'
    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()
    def test_ready_test_checkout_and_dashboard_links(self):
        page=self.client.get('/contractor/billing')
        self.assertIn('no-store',page.headers['Cache-Control']);self.assertIn('noindex',page.headers['X-Robots-Tag'])
        self.assertEqual(page.status_code,200);self.assertIn('Test checkout available — no real charges',page.text)
        self.assertIn('You do not need a Stripe account',page.text)
        self.assertIn('Stripe payments and receipts',self.client.get('/contractor/dashboard').text)
        self.assertIn('Stripe payments and receipts',self.client.get('/contractor/settings').text)
        self.assertNotIn('rk_test_synthetic',page.text);self.assertNotIn('whsec_synthetic',page.text)
    def test_missing_confirmation_configuration_hides_checkout_and_blocks_provider(self):
        for value in ('','invalid'):
            with self.subTest(value=value),patch.dict(os.environ,{'STRIPE_WEBHOOK_SECRET':value}),patch('billing.create_checkout') as create:
                page=self.client.get('/contractor/billing')
                self.assertIn('Payment setup in progress',page.text);self.assertNotIn('>Get current market quote<',page.text)
                response=self.client.post('/contractor/offers/1/checkout',data={'_csrf':'synthetic-csrf'})
                self.assertEqual(response.status_code,503);create.assert_not_called()
    def test_readiness_requires_matching_key_origin_activation_and_live_switch(self):
        for config in ({'STRIPE_SECRET_KEY':''},{'STRIPE_SECRET_KEY':'rk_live_synthetic'},
                {'PUBLIC_SITE_URL':'http://example.com'},{'PAYMENTS_ACTIVATION_UTC':'bad'},
                {'PAYMENTS_ENABLED':'false'},{'STRIPE_MODE':'live','STRIPE_SECRET_KEY':'rk_live_synthetic'},
                {'STRIPE_MODE':'invalid'}):
            with self.subTest(config=config),patch.dict(os.environ,config):self.assertFalse(payment_readiness()['ready'])
        with patch.dict(os.environ,{'STRIPE_MODE':'live','STRIPE_SECRET_KEY':'rk_live_synthetic','STRIPE_LIVE_PAYMENTS_ENABLED':'true'}):
            self.assertEqual(payment_readiness(),{'ready':True,'test_mode':False})
    def test_contractors_cannot_change_configuration_or_see_admin_setup(self):
        self.assertEqual(self.client.post('/contractor/billing',data={'STRIPE_SECRET_KEY':'injected'}).status_code,405)
        self.assertEqual(self.client.get('/admin/integrations').status_code,302)
        self.assertEqual(os.environ['STRIPE_SECRET_KEY'],'rk_test_synthetic')
        other=app.test_client();self.assertEqual(other.get('/contractor/billing').status_code,302)
    def test_admin_sees_setup_without_credential_values(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as state:state.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint())
        page=self.client.get('/admin/integrations')
        self.assertIn('Contractor Stripe checkout',page.text);self.assertIn('/webhooks/stripe',page.text)
        self.assertIn('charge.refunded',page.text);self.assertNotIn('rk_test_synthetic',page.text);self.assertNotIn('whsec_synthetic',page.text)

    def test_resume_button_requires_current_mode_ready_configuration_and_unpaid_order(self):
        from datetime import timedelta
        from app import Lead,LeadOffer
        lead=Lead(homeowner_name='Synthetic',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.flush()
        offer=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='accepted',accepted_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        db.session.add(offer);db.session.flush()
        payment=Payment(contractor_id=self.contractor.id,offer_id=offer.id,amount_cents=2500,currency='usd',mode='test',price_id='synthetic-lab',status='open',session_id='cs_test_synthetic')
        db.session.add(payment);db.session.commit()
        page=self.client.get('/contractor/billing')
        self.assertIn('Resume Stripe checkout',page.text);self.assertIn('name="quote_version"',page.text)
        self.assertIn('name="_csrf"',page.text);self.assertNotIn('cs_test_synthetic',page.text)
        for config in ({'STRIPE_MODE':'live','STRIPE_SECRET_KEY':'rk_live_synthetic','STRIPE_LIVE_PAYMENTS_ENABLED':'true'}, {'STRIPE_WEBHOOK_SECRET':''}):
            with patch.dict(os.environ,config):self.assertNotIn('Resume Stripe checkout',self.client.get('/contractor/billing').text)
        payment.status='paid';db.session.commit()
        self.assertNotIn('Resume Stripe checkout',self.client.get('/contractor/billing').text)

import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import hashlib
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import app, db, Contractor, Lead, LeadMarket, MarketApplication, MarketReview, Delivery, LeadOffer, Payment
from national_markets import STATES, city_slug
from national_coverage import lead_state, national_report
from contractor_matching import contractor_matches
from contractor_session_security import create_contractor_session_data


class NationalCoverageTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'ADMIN_PASSWORD_HASH':'synthetic-admin', 'EMAIL_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push()
        db.drop_all();db.create_all();self.client=app.test_client()
        self.contractor=Contractor(company_name='Restoration Company',contact_name='Owner',email='owner@example.com',
            phone='6125550100',zip_codes='55401',service_type='Mold Remediation',license_number='MN-TEST',
            active=True,verified=True,is_test=False,password_hash='synthetic-hash')
        db.session.add(self.contractor);db.session.commit()

    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()

    def owner(self):
        with self.client.session_transaction() as s:
            s.clear();s.update(create_contractor_session_data(self.contractor.id));s['_csrf']='market-csrf'
            s['contractor_password_fingerprint']=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest()

    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as s:
            s.clear();s.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint(),_csrf='market-csrf')

    def submit(self, **extra):
        data=dict(_csrf='market-csrf',state_code='TX',zip_codes='75201,77002',services=['Fire Damage Restoration'],
            license_number='STATE-TEST',applicant_notes='OWNER NOTES',review_required='yes')
        data.update(extra)
        return self.client.post('/contractor/markets',data=data)

    def decision(self, identifier, **extra):
        future=(datetime.now(timezone.utc)+timedelta(days=30)).date().isoformat()
        data=dict(_csrf='market-csrf',decision='approved',license_reference='PRIVATE LICENSE',
            insurance_reference='PRIVATE INSURANCE',scope_reference='PRIVATE SCOPE',license_expires=future,
            insurance_expires=future,private_notes='PRIVATE NOTES',response_message='Your requested state coverage was reviewed.',state_scope_checked='yes')
        data.update(extra)
        return self.client.post(f'/admin/national/applications/{identifier}',data=data)

    def application(self):
        self.owner();self.assertEqual(self.submit().status_code,303)
        return MarketApplication.query.one()

    def lead(self, state=None, zip_code='55401', service='Mold Remediation'):
        lead=Lead(homeowner_name='Homeowner',phone='6125550199',zip_code=zip_code,service_needed=service,status='New')
        db.session.add(lead);db.session.flush()
        if state:db.session.add(LeadMarket(lead_id=lead.id,state_code=state))
        db.session.commit();return lead

    def test_brand_hostname_allowlist_and_existing_minnesota(self):
        for host in ('RestorationContractorsUSA.com','www.restorationcontractorsusa.com'):
            page=self.client.get('/',base_url='https://'+host).text
            self.assertIn('Property damage is stressful',page);self.assertIn('rcusa-logo-tm.png',page)
            self.assertIn('rcusa-logo-tm.png',self.client.get('/contractor/login',base_url='https://'+host).text)
        for host in ('RestorationContractorsMN.com','restorationcontractorsusa.com.evil.example','localhost'):
            page=self.client.get('/',base_url='https://'+host).text
            self.assertIn('MINNESOTA PROPERTY RESTORATION',page);self.assertIn('rcmn-logo-tm.png',page)

    def test_private_previews_cover_every_catalog_market_and_city(self):
        self.assertEqual(self.client.get('/admin/national/preview/texas').status_code,403)
        self.admin()
        descriptions=set()
        for slug, info in STATES.items():
            paths=[('/admin/national/preview/'+slug,info[1])]+[('/admin/national/preview/'+slug+'/'+city_slug(c),c) for c in info[2]]
            for path,label in paths:
                response=self.client.get(path)
                self.assertEqual(response.status_code,200,path);self.assertIn(label,response.text)
                self.assertIn('no-store',response.headers['Cache-Control']);self.assertIn('noindex',response.text)
                self.assertIn('AI-generated',response.text);self.assertNotIn('rel="canonical"',response.text)
            descriptions.add(self.client.get(paths[0][0]).text)
        self.assertEqual(len(descriptions),6)
        self.assertEqual(self.client.get('/admin/national/preview/texas/no-such-city').status_code,404)

    def test_sitemap_excludes_disabled_and_private_pages(self):
        response=self.client.get('/usa/sitemap.xml')
        self.assertEqual(response.status_code,200);self.assertIn('application/xml',response.content_type)
        self.assertIn('/usa/minnesota/twin-cities',response.text)
        for slug in STATES:
            if slug!='minnesota':self.assertNotIn('/usa/'+slug,response.text)
        self.assertNotIn('/admin/',response.text)
        self.assertIn('https://RestorationContractorsUSA.com/usa/minnesota',self.client.get('/usa/minnesota',base_url='https://evil.example').text)

    def test_owner_csrf_and_registration_validation(self):
        self.assertEqual(self.client.get('/contractor/markets').status_code,302)
        self.owner();self.assertEqual(self.submit(_csrf='wrong').status_code,400)
        for changes in ({'state_code':'MN'},{'state_code':'CA'},{'zip_codes':'7520'},{'services':['Invented service']},
                        {'license_number':''},{'review_required':'no'},{'applicant_notes':'x'*2001}):
            self.assertEqual(self.submit(**changes).status_code,400,changes)
        self.assertEqual(MarketApplication.query.count(),0)

    def test_pending_deduplication_owner_binding_and_original_coverage(self):
        self.owner();self.assertEqual(self.submit(contractor_id=999,status='approved').status_code,303)
        row=MarketApplication.query.one();self.assertEqual(row.contractor_id,self.contractor.id);self.assertEqual(row.status,'pending')
        self.assertEqual(self.submit().status_code,400);self.assertEqual(MarketApplication.query.count(),1)
        self.assertEqual(self.contractor.zip_codes,'55401');self.assertEqual(self.contractor.service_type,'Mold Remediation')
        self.assertIn('no-store',self.client.get('/contractor/markets').headers['Cache-Control'])

    def test_review_requires_admin_csrf_and_full_current_evidence(self):
        row=self.application()
        self.assertEqual(self.decision(row.id).status_code,403)
        self.admin();self.assertEqual(self.decision(row.id,_csrf='bad').status_code,400)
        for changes in ({'license_reference':''},{'scope_reference':''},{'state_scope_checked':'no'},
                        {'license_expires':'2000-01-01'},{'response_message':''},{'private_notes':''}):
            self.assertEqual(self.decision(row.id,**changes).status_code,400,changes)
        self.assertEqual(MarketReview.query.count(),0);db.session.refresh(row);self.assertEqual(row.status,'pending')

    def test_approval_is_not_launch_and_cannot_bypass_matching_billing_or_acceptance(self):
        row=self.application();self.admin();self.assertEqual(self.decision(row.id).status_code,303)
        lead=self.lead('TX','75201','Fire Damage Restoration')
        self.assertFalse(contractor_matches(self.contractor,lead))
        self.assertEqual(self.client.get('/usa/texas').status_code,404)
        self.assertEqual(self.decision(row.id).status_code,409);self.assertEqual(MarketReview.query.count(),1)
        offer=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='pending',
            offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
        db.session.add(offer);db.session.commit()
        from contractor_offer_transactions import accept_contractor_offer
        self.assertIsNone(accept_contractor_offer(db.session,offer.id,self.contractor.id));db.session.rollback()
        offer.status='accepted';offer.accepted_at=datetime.now(timezone.utc);db.session.commit()
        from billing import billable_offer
        from werkzeug.exceptions import Conflict
        with patch.dict(os.environ,{'PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}):
            with self.assertRaises(Conflict):billable_offer(self.contractor,offer.id)

    def test_independent_services_and_zip_coverage_after_future_launch(self):
        row=self.application();self.admin();self.decision(row.id)
        with patch('national_markets.enabled',return_value=True):
            self.assertTrue(contractor_matches(self.contractor,self.lead('TX','75201','Fire Damage Restoration')))
            self.assertFalse(contractor_matches(self.contractor,self.lead('TX','75202','Fire Damage Restoration')))
            self.assertFalse(contractor_matches(self.contractor,self.lead('TX','75201','Mold Remediation')))
            self.assertFalse(contractor_matches(self.contractor,self.lead('FL','75201','Fire Damage Restoration')))
            review=MarketReview.query.one();review.insurance_expires=datetime(2000,1,1).date();db.session.commit()
            self.assertFalse(contractor_matches(self.contractor,self.lead('TX','75201','Fire Damage Restoration')))

    def test_private_notes_never_appear_in_owner_history_or_email(self):
        row=self.application();self.admin();self.decision(row.id)
        self.owner();page=self.client.get('/contractor/markets').text
        self.assertIn('Your requested state coverage was reviewed.',page)
        for private in ('PRIVATE LICENSE','PRIVATE INSURANCE','PRIVATE SCOPE','PRIVATE NOTES'):
            self.assertNotIn(private,page);self.assertNotIn(private,Delivery.query.one().body)

    def test_denial_and_replacement_do_not_reuse_old_state_approval(self):
        row=self.application();self.admin();self.decision(row.id)
        self.owner();self.assertEqual(self.submit().status_code,303)
        with patch('national_markets.enabled',return_value=True):
            self.assertFalse(contractor_matches(self.contractor,self.lead('TX','75201','Fire Damage Restoration')))
        replacement=MarketApplication.query.order_by(MarketApplication.id.desc()).first()
        self.admin();self.assertEqual(self.decision(replacement.id,decision='rejected',license_expires='',insurance_expires='').status_code,303)
        self.assertEqual(MarketReview.query.count(),2)

    def test_expired_account_cannot_gain_state_approval(self):
        row=self.application();self.contractor.active=False;db.session.commit();self.admin()
        self.assertEqual(self.decision(row.id).status_code,400);self.assertEqual(MarketReview.query.count(),0)

    def test_report_preserves_legacy_state_and_refund_totals(self):
        legacy=self.lead();texas=self.lead('TX','75201')
        self.assertEqual(lead_state(legacy),'MN');self.assertEqual(lead_state(texas),'TX')
        row=self.application();self.admin();self.decision(row.id)
        offer=LeadOffer(lead_id=texas.id,contractor_id=self.contractor.id,status='accepted',
            offered_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer);db.session.flush()
        db.session.add(Payment(offer_id=offer.id,contractor_id=self.contractor.id,amount_cents=10000,refunded_cents=2500,
            currency='usd',price_id='historical-test',status='paid'));db.session.commit()
        report=national_report();self.assertEqual(report['MN']['leads'],1);self.assertEqual(report['TX']['leads'],1)
        self.assertEqual(report['TX']['approved'],1);self.assertEqual(report['TX']['revenue_cents'],7500)
        self.assertEqual(report['TX']['refunded_cents'],2500)
        page=self.client.get('/admin/national');self.assertEqual(page.status_code,200);self.assertIn('$75.00',page.text)
        self.assertIn('no-store',page.headers['Cache-Control'])

    def test_owner_cannot_read_another_contractors_application(self):
        row=self.application()
        other=Contractor(company_name='Other',contact_name='Other',email='other@example.com',phone='6125550101',
            zip_codes='55401',active=True,verified=True,is_test=False,password_hash='synthetic-hash')
        db.session.add(other);db.session.commit();self.contractor=other;self.owner()
        self.assertNotIn('OWNER NOTES',self.client.get('/contractor/markets').text)
        self.assertEqual(self.client.get(f'/admin/national/applications/{row.id}').status_code,403)

    def test_review_and_notification_are_one_transaction(self):
        row=self.application();self.admin()
        with patch('communications.queue_email',side_effect=RuntimeError('synthetic rollback')):
            with self.assertRaises(RuntimeError):
                with app.test_request_context(f'/admin/national/applications/{row.id}',method='POST',data={
                    '_csrf':'market-csrf','decision':'rejected','private_notes':'reviewed','response_message':'Please revise.'}):
                    from flask import session
                    from national_coverage import review
                    from admin_session_security import current_password_fingerprint
                    session.update(admin_authenticated=True,admin_login_at=time.time()-1,
                        admin_password_fingerprint=current_password_fingerprint(),_csrf='market-csrf')
                    review(row.id)
        db.session.refresh(row);self.assertEqual(row.status,'pending');self.assertEqual(MarketReview.query.count(),0)

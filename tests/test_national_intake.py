import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import json
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import app,db,Contractor,ContractorOrigin,Lead,LeadMarket,MarketApplication,MarketReview,Delivery
from national_markets import STATES
from contractor_matching import contractor_matches
from national_coverage import national_report


class NationalIntakeTests(unittest.TestCase):
    def setUp(self):
        self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()
        with self.client.session_transaction() as s:s['_csrf']='intake-csrf'

    def tearDown(self):db.session.remove();self.ctx.pop()

    def registration(self,**extra):
        data=dict(_csrf='intake-csrf',company_name='Synthetic National Business',contact_name='Owner',email='owner@example.com',
            phone='2145550100',license_number='STATE-REGISTRATION',zip_codes='75201,77002',
            services=['Fire Damage Restoration','Mold Remediation'],approval_required='yes')
        data.update(extra);return data

    def request_data(self,**extra):
        data=dict(name='Consumer',phone='2145550199',email='consumer@example.com',zip_code='75201',
            service_needed='Fire Damage Restoration',description='Synthetic request',state='TX')
        data.update(extra);return data

    def test_closed_states_reject_all_public_forms_and_direct_api_no_side_effects(self):
        for slug,market in STATES.items():
            if slug=='minnesota':continue
            for suffix in ('request','contractors/apply'):
                self.assertEqual(self.client.get('/usa/'+slug+'/'+suffix).status_code,404)
            self.assertEqual(self.client.post('/usa/'+slug+'/contractors/apply',data=self.registration()).status_code,404)
            self.assertEqual(self.client.post('/api/leads',json=self.request_data(state=market[0])).status_code,400)
        self.assertEqual(Contractor.query.count(),0);self.assertEqual(Lead.query.count(),0);self.assertEqual(Delivery.query.count(),0)

    def test_minnesota_routes_redirect_to_retained_forms(self):
        self.assertEqual(self.client.get('/usa/minnesota/request').location,'/#request')
        self.assertEqual(self.client.get('/usa/minnesota/contractors/apply').location,'/contractor-signup')

    def test_future_launched_states_create_inactive_state_scoped_applications(self):
        with patch('national_intake.enabled',return_value=True):
            for slug,market in STATES.items():
                if slug=='minnesota':continue
                response=self.client.post('/usa/'+slug+'/contractors/apply',data=self.registration(email=slug+'@example.com'))
                self.assertEqual(response.status_code,303,slug)
                c=Contractor.query.filter_by(email=slug+'@example.com').one()
                self.assertFalse(c.active);self.assertFalse(c.verified);self.assertFalse(c.sms_consent)
                self.assertEqual(c.zip_codes,'');self.assertEqual(db.session.get(ContractorOrigin,c.id).state_code,market[0])
                application=MarketApplication.query.filter_by(contractor_id=c.id).one()
                self.assertEqual(application.state_code,market[0]);self.assertEqual(application.status,'pending')
                self.assertEqual(set(application.services),{'Mold Remediation','Fire Damage Restoration'})
        report=national_report();self.assertEqual(report['MN']['contractors'],0)
        for code in ('TX','FL','NC','GA','WI'):self.assertEqual(report[code]['contractors'],1)

    def test_initial_signup_cannot_self_approve_forge_origin_or_bypass_csrf(self):
        with patch('national_intake.enabled',return_value=True):
            self.assertEqual(self.client.post('/usa/texas/contractors/apply',data=self.registration(_csrf='bad')).status_code,400)
            response=self.client.post('/usa/texas/contractors/apply',data=self.registration(active='true',verified='true',state_code='MN'))
            self.assertEqual(response.status_code,303)
            c=Contractor.query.one();self.assertFalse(c.active);self.assertFalse(c.verified)
            self.assertEqual(db.session.get(ContractorOrigin,c.id).state_code,'TX')

    def test_duplicate_and_invalid_initial_application_leave_no_partial_records(self):
        with patch('national_intake.enabled',return_value=True):
            for extra in ({'services':['Not a service']},{'zip_codes':'bad'},{'approval_required':'no'},
                          {'email':'bad'},{'license_number':''},{'company_name':'x'*151}):
                self.assertEqual(self.client.post('/usa/texas/contractors/apply',data=self.registration(**extra)).status_code,400)
            self.assertEqual(Contractor.query.count(),0)
            self.assertEqual(self.client.post('/usa/texas/contractors/apply',data=self.registration()).status_code,303)
            self.assertEqual(self.client.post('/usa/florida/contractors/apply',data=self.registration()).status_code,400)
            self.assertEqual(Contractor.query.count(),1);self.assertEqual(MarketApplication.query.count(),1)

    def test_national_signup_notification_failure_rolls_back_all_application_tables(self):
        with patch('national_intake.enabled',return_value=True),patch('communications.queue_email',side_effect=RuntimeError('synthetic rollback')):
            from national_intake import register
            from flask import session
            with app.test_request_context('/usa/texas/contractors/apply',method='POST',data=self.registration()):
                session['_csrf']='intake-csrf'
                with self.assertRaises(RuntimeError):register('texas')
        self.assertEqual(Contractor.query.count(),0);self.assertEqual(ContractorOrigin.query.count(),0)
        self.assertEqual(MarketApplication.query.count(),0)

    def test_future_public_requests_store_trusted_state_and_use_usa_receipt_domain(self):
        with patch('national_markets.enabled',return_value=True):
            self.assertEqual(self.client.post('/api/leads',json=self.request_data()).status_code,201)
        lead=Lead.query.one();self.assertEqual(db.session.get(LeadMarket,lead.id).state_code,'TX')
        self.assertIn('https://RestorationContractorsUSA.com/request-status',Delivery.query.one().body)
        self.assertNotIn('Synthetic request',Delivery.query.one().body)

    def test_future_request_validation_retains_state_and_form_values(self):
        with patch('national_markets.enabled',return_value=True):
            response=self.client.post('/api/leads',data=self.request_data(phone='bad',description='KEEP THIS DRAFT'))
            self.assertEqual(response.status_code,400);self.assertIn('KEEP THIS DRAFT',response.text)
            self.assertIn('name="state" value="TX"',response.text);self.assertIn('Texas property',response.text)
            self.assertEqual(self.client.post('/api/leads',json=self.request_data(service_needed='made up')).status_code,400)
        self.assertEqual(Lead.query.count(),0)

    def test_non_minnesota_origin_cannot_gain_minnesota_eligibility_by_editing_legacy_fields(self):
        with patch('national_intake.enabled',return_value=True):
            self.client.post('/usa/texas/contractors/apply',data=self.registration())
        c=Contractor.query.one();c.active=True;c.verified=True;c.zip_codes='55401';c.service_type='Mold Remediation';db.session.commit()
        lead=Lead(homeowner_name='MN Consumer',phone='6125550199',zip_code='55401',service_needed='Mold Remediation',status='New')
        db.session.add(lead);db.session.commit();self.assertFalse(contractor_matches(c,lead))
        row=MarketApplication(contractor_id=c.id,state_code='MN',zip_codes='55401',services_json=json.dumps(['Mold Remediation']),
            license_number='MN-TEST',applicant_notes='Separate Minnesota application',status='approved')
        db.session.add(row);db.session.flush();future=(datetime.now(timezone.utc)+timedelta(days=30)).date()
        db.session.add(MarketReview(application_id=row.id,decision='approved',license_reference='MN evidence',insurance_reference='MN insurance',
            scope_reference='MN scope',license_expires=future,insurance_expires=future,private_notes='Checked',response_message='Reviewed'))
        db.session.commit();self.assertTrue(contractor_matches(c,lead))

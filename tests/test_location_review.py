import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import time
import unittest
from unittest.mock import patch
from app import app,db,Lead,LeadMarket,LeadLocationReview,Delivery,Contractor,LeadOffer,ConsumerRequestUpdate
from location_review import needs_location_review,REVIEW_STATUS,postal_reference
from contractor_matching import contractor_matches


class LocationReviewTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-admin'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()

    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()

    def submit(self,zip_code='75201',base_url='https://restorationcontractorsmn.com'):
        return self.client.post('/api/leads',json=dict(name='PRIVATE CONSUMER',phone='6125550199',
            email='consumer@example.com',zip_code=zip_code,service_needed='Mold Remediation',state='MN'),base_url=base_url)

    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as s:
            s.clear();s.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint(),_csrf='location-csrf')

    def review(self,lead_id,**extra):
        data=dict(_csrf='location-csrf',state_code='MN',decision='approved',evidence_reference='PRIVATE PROPERTY EVIDENCE',
            private_notes='PRIVATE ADMIN NOTES',jurisdiction_checked='yes')
        data.update(extra);return self.client.post(f'/admin/leads/{lead_id}/location',data=data)

    def test_postal_facility_reference_is_not_a_single_authoritative_state_mapping(self):
        self.assertFalse(needs_location_review('55401','MN'));self.assertTrue(needs_location_review('75201','MN'))
        self.assertTrue(needs_location_review('00000','MN'))
        for code in ('56520','56721'):
            self.assertEqual(set(postal_reference()['facility_states_by_zip'][code]),{'MN','ND'})
            self.assertFalse(needs_location_review(code,'MN'))

    def test_obvious_state_mismatch_or_unknown_zip_is_saved_without_automatic_matching(self):
        for zip_code in ('75201','00000'):
            response=self.submit(zip_code);self.assertEqual(response.status_code,201)
            self.assertEqual(response.json['assignment_status'],'review')
        self.assertEqual({lead.status for lead in Lead.query.all()},{REVIEW_STATUS})
        contractor=Contractor(company_name='Synthetic',contact_name='Owner',email='owner@example.com',phone='6125550100',
            zip_codes='75201,00000',service_type='Mold Remediation',active=True,verified=True,is_test=False)
        db.session.add(contractor);db.session.commit()
        for lead in Lead.query.all():self.assertFalse(contractor_matches(contractor,lead))
        self.assertEqual(LeadOffer.query.count(),0)

    def test_normal_minnesota_and_border_zip_retain_new_request_flow(self):
        for zip_code in ('55401','56520','56721'):
            response=self.submit(zip_code);self.assertEqual(response.status_code,201)
            self.assertEqual(response.json['assignment_status'],'pending')
        self.assertEqual({lead.status for lead in Lead.query.all()},{'New'})

    def test_client_cannot_self_approve_or_create_a_location_review(self):
        self.submit();lead=Lead.query.one()
        self.assertEqual(self.review(lead.id).status_code,403);self.assertEqual(LeadLocationReview.query.count(),0)
        self.admin();self.assertEqual(self.review(lead.id,_csrf='wrong').status_code,400)
        for extra in ({'evidence_reference':''},{'private_notes':''},{'jurisdiction_checked':'no'}):
            self.assertEqual(self.review(lead.id,**extra).status_code,400)
        self.assertEqual(LeadLocationReview.query.count(),0)

    def test_closed_state_cannot_be_approved_and_can_be_recorded_unavailable(self):
        self.submit();lead=Lead.query.one();self.admin()
        self.assertEqual(self.review(lead.id,state_code='TX').status_code,400)
        self.assertEqual(self.review(lead.id,state_code='TX',decision='unavailable').status_code,303)
        self.assertEqual(LeadLocationReview.query.one().previous_state_code,'MN')
        db.session.refresh(lead);self.assertEqual(lead.status,'Cancelled')
        scope=db.session.get(LeadMarket,lead.id);self.assertEqual(scope.state_code,'TX');self.assertEqual(scope.intake_brand,'MN')
        update=ConsumerRequestUpdate.query.one();delivery=db.session.get(Delivery,update.delivery_id)
        self.assertIn('https://RestorationContractorsMN.com/request-status',delivery.body)
        self.assertNotIn('PRIVATE PROPERTY EVIDENCE',delivery.body)

    def test_documented_open_state_review_can_release_and_replays_cannot_change_decision(self):
        self.submit('54016');lead=Lead.query.one();self.admin()
        self.assertEqual(self.review(lead.id).status_code,303)
        db.session.refresh(lead);self.assertEqual(lead.status,'New');self.assertEqual(lead.zip_code,'54016')
        self.assertEqual(self.review(lead.id,state_code='WI',decision='unavailable').status_code,409)
        self.assertEqual(LeadLocationReview.query.count(),1)
        self.assertIn('PRIVATE PROPERTY EVIDENCE',self.client.get(f'/admin/leads/{lead.id}/location').text)

    def test_location_hold_and_private_evidence_are_not_exposed_to_consumer(self):
        self.submit(base_url='http://localhost');lead=Lead.query.one()
        page=self.client.get('/request-status');self.assertIn('Your property location needs review',page.text)
        self.assertNotIn('PRIVATE CONSUMER',page.text)
        self.admin();self.review(lead.id)
        self.assertEqual(self.client.get(f'/admin/leads/{lead.id}/location').status_code,200)
        self.client=app.test_client();self.assertEqual(self.client.get(f'/admin/leads/{lead.id}/location').status_code,302)

    def test_consumer_can_cancel_held_request_without_waiting_for_review(self):
        self.submit(base_url='http://localhost');lead=Lead.query.one()
        self.assertEqual(self.client.get('/request-status/stop-matching').status_code,200)
        with self.client.session_transaction() as s:s['_csrf']='location-csrf'
        response=self.client.post('/request-status/stop-matching',data=dict(_csrf='location-csrf',
            request_reference=str(lead.id),confirm_stop='yes'))
        self.assertEqual(response.status_code,303);db.session.refresh(lead);self.assertEqual(lead.status,'Cancelled')

    def test_review_notification_failure_rolls_back_location_and_status(self):
        self.submit();lead=Lead.query.one()
        from location_review import review
        from flask import session
        from admin_session_security import current_password_fingerprint
        with app.test_request_context(f'/admin/leads/{lead.id}/location',method='POST',data=dict(
                _csrf='location-csrf',state_code='TX',decision='unavailable',evidence_reference='Synthetic',
                private_notes='Synthetic',jurisdiction_checked='yes')):
            session.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint(),_csrf='location-csrf')
            with patch('consumer_requests.queue_request_update',side_effect=RuntimeError('synthetic rollback')):
                with self.assertRaises(RuntimeError):review(lead.id)
        db.session.refresh(lead);self.assertEqual(lead.status,REVIEW_STATUS)
        self.assertEqual(LeadLocationReview.query.count(),0);self.assertIsNone(db.session.get(LeadMarket,lead.id))

    def test_intake_brand_remains_usa_when_state_is_minnesota(self):
        response=self.submit('55401',base_url='https://restorationcontractorsusa.com')
        self.assertEqual(response.status_code,201)
        scope=LeadMarket.query.one();self.assertEqual(scope.state_code,'MN');self.assertEqual(scope.intake_brand,'USA')
        self.assertIn('https://RestorationContractorsUSA.com/request-status',Delivery.query.one().body)

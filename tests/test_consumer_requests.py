import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import app, db, Lead, LeadOffer, Contractor, Delivery, ConsumerRequestUpdate
from consumer_requests import remember_request
from contractor_session_security import create_contractor_session_data


class ConsumerRequestTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'test-admin-config',
            'EMAIL_SENDING_ENABLED':'true','RESEND_API_KEY':'re_dummy','RESEND_FROM_EMAIL':'sender@example.com',
            'SMS_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push()
        db.drop_all();db.create_all();self.client=app.test_client()
        self.lead=Lead(homeowner_name='PRIVATE HOMEOWNER',phone='6125550199',email='consumer@example.com',
            zip_code='55401',service_needed='Mold Remediation',description='PRIVATE PROJECT DESCRIPTION',status='New')
        self.contractor=Contractor(company_name='Matched Restoration Business',contact_name='Business Owner',
            email='contractor@example.com',phone='(612) 555-0100',zip_codes='55401',service_type='Mold Remediation',
            active=True,verified=True,is_test=False,password_hash='synthetic-password-hash')
        db.session.add_all([self.lead,self.contractor]);db.session.commit()

    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()

    def owner(self, lead_id=None, issued=None):
        with self.client.session_transaction() as state:
            state['last_lead_reference']=self.lead.id if lead_id is None else lead_id
            state['last_lead_status_at']=(issued or datetime.now(timezone.utc)).isoformat()

    def offer(self, status='accepted'):
        offer=LeadOffer(lead_id=self.lead.id,contractor_id=self.contractor.id,status=status,
            offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        if status=='accepted':offer.accepted_at=datetime.now(timezone.utc)
        db.session.add(offer);db.session.commit();return offer

    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as state:
            state.update(admin_authenticated=True,admin_login_at=time.time()-1,
                         admin_password_fingerprint=current_password_fingerprint(),_csrf='csrf-test')

    def contractor_session(self):
        with self.client.session_transaction() as state:
            state.update(create_contractor_session_data(self.contractor.id))
            state['contractor_password_fingerprint']=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest()
            state['_csrf']='csrf-test'

    def test_no_claim_cannot_access_by_id_email_or_phone(self):
        self.offer()
        page=self.client.get(f'/request-status?lead_id={self.lead.id}&email=consumer@example.com&phone=6125550199')
        self.assertEqual(page.status_code,200)
        for private in ('Matched Restoration Business','55401','Mold Remediation','PRIVATE HOMEOWNER','6125550199'):
            self.assertNotIn(private,page.text)
        self.assertIn('No current request',page.text)

    def test_own_request_only_and_sensitive_fields_omitted(self):
        other=Lead(homeowner_name='OTHER HOMEOWNER',phone='6125550133',zip_code='55999',service_needed='OTHER PRIVATE SERVICE')
        db.session.add(other);db.session.commit();self.owner()
        page=self.client.get(f'/request-status?lead_id={other.id}')
        self.assertIn('Mold Remediation',page.text);self.assertIn('Looking for a contractor',page.text)
        for private in ('OTHER PRIVATE SERVICE','PRIVATE HOMEOWNER','PRIVATE PROJECT DESCRIPTION','6125550199','consumer@example.com'):
            self.assertNotIn(private,page.text)
        self.assertIn('no-store',page.headers['Cache-Control'])
        self.assertEqual(page.headers['Referrer-Policy'],'no-referrer')
        self.assertEqual(page.headers['X-Robots-Tag'],'noindex, nofollow')

    def test_expired_future_invalid_and_deleted_claims_show_no_details(self):
        for issued in (datetime.now(timezone.utc)-timedelta(days=7,seconds=1),
                       datetime.now(timezone.utc)+timedelta(minutes=5)):
            self.owner(issued=issued)
            self.assertNotIn('Mold Remediation',self.client.get('/request-status').text)
        for lead_id in (True,-1,'1',2**64):
            self.owner(lead_id=lead_id)
            self.assertNotIn('Mold Remediation',self.client.get('/request-status').text)
        self.owner()
        with self.client.session_transaction() as state:state['last_lead_status_at']='invalid'
        self.assertNotIn('Mold Remediation',self.client.get('/request-status').text)
        self.owner();db.session.delete(self.lead);db.session.commit()
        self.assertNotIn('Mold Remediation',self.client.get('/request-status').text)

    def test_intake_sets_claim_for_both_json_and_html_without_client_ids(self):
        data={'name':'New Consumer','phone':'6125550111','zip_code':'55101','service_needed':'Mold Remediation','lead_id':self.lead.id}
        response=self.client.post('/api/leads',json=data)
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json['status_url'],'/request-status')
        self.assertNotEqual(response.json['lead_id'],self.lead.id)
        self.assertIn('55101',self.client.get('/request-status').text)
        with self.client.session_transaction() as state:state.clear()
        response=self.client.post('/api/leads',data=data)
        self.assertEqual(response.status_code,302);self.assertTrue(response.location.endswith('/request-received'))
        receipt=self.client.get(response.location)
        self.assertIn('/request-status',receipt.text);self.assertIn('no-store',receipt.headers['Cache-Control'])
        self.assertIn('55101',self.client.get('/request-status').text)

    def test_accepted_contact_is_visible_only_while_account_is_eligible(self):
        self.offer();self.owner()
        page=self.client.get('/request-status')
        self.assertIn('Matched Restoration Business',page.text)
        self.assertIn('href="tel:6125550100"',page.text)
        self.assertIn('mailto:contractor@example.com',page.text)
        self.contractor.active=False;db.session.commit()
        page=self.client.get('/request-status')
        self.assertIn('Your match needs review',page.text)
        self.assertNotIn('contractor@example.com',page.text)
        self.assertNotIn('Matched Restoration Business',page.text)

    def test_terminal_and_unknown_states_do_not_display_contractor_contacts(self):
        self.offer();self.owner()
        for state,title in (('Closed','Your request is closed'),('Cancelled','Your request is cancelled'),('Unexpected','Your request is under review')):
            self.lead.status=state;db.session.commit()
            page=self.client.get('/request-status')
            self.assertIn(title,page.text);self.assertNotIn('contractor@example.com',page.text)

    def test_multiple_accepted_legacy_records_require_review(self):
        self.offer();self.offer();self.owner()
        page=self.client.get('/request-status')
        self.assertIn('Your match needs review',page.text);self.assertNotIn('contractor@example.com',page.text)

    def test_acceptance_queues_one_private_consumer_update(self):
        offer=self.offer('pending');self.contractor_session()
        for _ in range(2):
            self.assertEqual(self.client.post(f'/contractor/offers/{offer.id}/accept',data={'_csrf':'csrf-test'}).status_code,302)
        event=ConsumerRequestUpdate.query.one();delivery=db.session.get(Delivery,event.delivery_id)
        self.assertEqual(event.status,'accepted');self.assertEqual(event.offer_id,offer.id)
        for private in ('PRIVATE HOMEOWNER','PRIVATE PROJECT DESCRIPTION','55401','contractor@example.com'):
            self.assertNotIn(private,delivery.body)
        self.assertIn('original browser',delivery.body)

    def test_closure_supersedes_unsent_acceptance_notice(self):
        from communications import deliver_pending
        offer=self.offer('pending');self.contractor_session()
        self.client.post(f'/contractor/offers/{offer.id}/accept',data={'_csrf':'csrf-test'})
        self.admin()
        response=self.client.post(f'/admin/leads/{self.lead.id}/status',data={'_csrf':'csrf-test','status':'Closed'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(ConsumerRequestUpdate.query.count(),2)
        self.assertEqual(self.client.post(f'/admin/leads/{self.lead.id}/status',data={'_csrf':'csrf-test','status':'Closed'}).status_code,409)
        self.assertEqual(ConsumerRequestUpdate.query.count(),2)
        self.assertIn('Consumer email updates',self.client.get(f'/admin/leads/{self.lead.id}').text)
        self.assertEqual(Delivery.query.filter_by(status='cancelled').count(),1)
        with patch('communications.resend_email',return_value='consumer-closed') as send:
            self.assertEqual(deliver_pending()['sent'],1)
            self.assertIn('request is closed',send.call_args.args[0].body)

    def test_invalid_match_and_changed_recipient_cancel_pending_notices(self):
        from communications import deliver_pending
        from consumer_requests import queue_request_update
        offer=self.offer();queue_request_update(self.lead,'accepted',offer.id);db.session.commit()
        self.contractor.verified=False;db.session.commit()
        with patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['cancelled'],1);send.assert_not_called()
        self.lead.status='Cancelled';queue_request_update(self.lead,'cancelled');db.session.commit()
        self.lead.email='changed@example.com';db.session.commit()
        with patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['cancelled'],1);send.assert_not_called()

    def test_status_notification_failure_rolls_back_acceptance(self):
        offer=self.offer('pending');self.contractor_session()
        with patch('consumer_requests.queue_request_update',side_effect=RuntimeError('synthetic failure')),self.assertLogs('app',level='ERROR'):
            response=self.client.post(f'/contractor/offers/{offer.id}/accept',data={'_csrf':'csrf-test'})
        self.assertEqual(response.status_code,503)
        db.session.refresh(offer);self.assertEqual(offer.status,'pending')
        self.assertEqual(ConsumerRequestUpdate.query.count(),0)

    def test_no_email_does_not_block_lead_operations_or_create_sms(self):
        self.lead.email=None;db.session.commit();self.admin()
        response=self.client.post(f'/admin/leads/{self.lead.id}/status',data={'_csrf':'csrf-test','status':'Cancelled'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(ConsumerRequestUpdate.query.count(),0);self.assertEqual(Delivery.query.count(),0)

    def test_status_notification_failure_rolls_back_closure_and_offer_cancellation(self):
        offer=self.offer('pending');self.admin()
        with patch('consumer_requests.queue_request_update',side_effect=RuntimeError('synthetic failure')),self.assertLogs('app',level='ERROR'):
            response=self.client.post(f'/admin/leads/{self.lead.id}/status',data={'_csrf':'csrf-test','status':'Cancelled'})
        self.assertEqual(response.status_code,500)
        db.session.refresh(self.lead);db.session.refresh(offer)
        self.assertEqual(self.lead.status,'New');self.assertEqual(offer.status,'pending')
        self.assertEqual(ConsumerRequestUpdate.query.count(),0);self.assertEqual(Delivery.query.count(),0)


if __name__=='__main__':unittest.main()

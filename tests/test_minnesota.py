import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import re
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import app, db, Contractor, ContractorPasswordSetupToken, Lead, LeadOffer
from contractor_password_security import hash_contractor_password
from contractor_session_security import create_contractor_session_data

class MinnesotaFlows(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'STRIPE_WEBHOOK_SECRET':'whsec_synthetic', 'ADMIN_PASSWORD_HASH': generate_password_hash('administrator-test-password'), 'CONTRACTOR_LOGIN_LOCK_SECRET': 's'*40, 'RESEND_API_KEY':'re_test', 'RESEND_FROM_EMAIL':'sender@example.com', 'TWILIO_ACCOUNT_SID':'ACtest', 'TWILIO_AUTH_TOKEN':'twilio_test', 'TWILIO_MESSAGING_SERVICE_SID':'MGtest', 'TWILIO_STATUS_WEBHOOK_URL':'https://example.com/webhooks/twilio/status'})
        self.env.start()
        self.ctx = app.app_context(); self.ctx.push()
        db.drop_all(); db.create_all()
        self.client = app.test_client()
        self.contractor = Contractor(company_name='MN Restoration', contact_name='Owner', email='owner@example.com', phone='6125550100', zip_codes='55401', service_type='Mold Remediation', license_number='TEST', active=True, verified=True, is_test=False, password_hash=hash_contractor_password('initial-test-password'))
        db.session.add(self.contractor); db.session.commit()
    def tearDown(self):
        db.session.remove(); self.ctx.pop(); self.env.stop()
    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as s:
            s.update(admin_authenticated=True, admin_login_at=datetime.now(timezone.utc).timestamp()-1, admin_password_fingerprint=current_password_fingerprint(), _csrf='csrf-test')
    def contractor_session(self):
        with self.client.session_transaction() as s:
            s.update(create_contractor_session_data(self.contractor.id))
            s['contractor_password_fingerprint'] = hashlib.sha256(self.contractor.password_hash.encode()).hexdigest()
            s['_csrf'] = 'csrf-test'
    def setup_link(self):
        from app import AccessRecoveryToken, Delivery
        with self.client.session_transaction() as state: state['_csrf']='csrf-test'
        r = self.client.post('/contractor/forgot-password',data={'_csrf':'csrf-test','email':'owner@example.com'})
        self.assertEqual(r.status_code,303)
        token=AccessRecoveryToken.query.order_by(AccessRecoveryToken.id.desc()).first()
        body=db.session.get(Delivery,token.delivery_id).body
        return re.search(r'https://www\.restorationcontractorsmn\.com([^\s]+)',body).group(1)
    def test_setup_login_reuse_and_reset_revocation(self):
        self.contractor_session()
        link = self.setup_link()
        r = self.client.post(link, data={'_csrf':'csrf-test','password':'replacement-password','confirm_password':'replacement-password'})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.client.post(link, data={'_csrf':'csrf-test','password':'replacement-password','confirm_password':'replacement-password'}).status_code, 400)
        r = self.client.post('/contractor/login', data={'_csrf':'csrf-test','email':'owner@example.com','password':'replacement-password'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.location, '/contractor/dashboard')
        self.assertEqual(self.client.get('/contractor/dashboard').status_code, 200)
        self.contractor.password_hash = hash_contractor_password('another-test-password'); db.session.commit()
        self.assertEqual(self.client.get('/contractor/dashboard').status_code, 302)
    def test_expired_link_csrf_and_reissue(self):
        first = self.setup_link(); second = self.setup_link()
        self.assertEqual(self.client.post(first, data={'_csrf':'csrf-test','password':'replacement-password','confirm_password':'replacement-password'}).status_code, 400)
        self.assertEqual(self.client.post(second, data={'password':'replacement-password'}).status_code, 400)
        from app import AccessRecoveryToken
        row = AccessRecoveryToken.query.order_by(AccessRecoveryToken.id.desc()).first()
        row.expires_at = datetime.now(timezone.utc)-timedelta(minutes=1); db.session.commit()
        self.assertEqual(self.client.post(second, data={'_csrf':'csrf-test','password':'replacement-password','confirm_password':'replacement-password'}).status_code, 400)
    def test_admin_password_change_blocks_owner_report(self):
        self.admin()
        os.environ['ADMIN_PASSWORD_HASH'] = generate_password_hash('changed-administrator-password')
        self.assertEqual(self.client.get('/admin/owner-command-center').status_code, 302)
    def test_accepted_offer_contact_and_pending_privacy(self):
        self.contractor_session()
        lead = Lead(homeowner_name='Private Homeowner', phone='6125550199', zip_code='55401', service_needed='Mold Remediation')
        db.session.add(lead); db.session.flush()
        offer = LeadOffer(lead_id=lead.id, contractor_id=self.contractor.id, status='pending', expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
        db.session.add(offer); db.session.commit()
        r=self.client.get('/contractor/dashboard'); self.assertEqual(r.status_code, 200)
        self.assertNotIn('Private Homeowner', r.text)
        offer.status='accepted'; db.session.commit()
        self.assertIn('Private Homeowner', self.client.get('/contractor/dashboard').text)
    def test_local_login_lockout(self):
        with self.client.session_transaction() as s: s['_csrf']='csrf-test'
        for _ in range(5):
            r=self.client.post('/contractor/login', data={'_csrf':'csrf-test','email':'owner@example.com','password':'wrong'})
            self.assertEqual(r.status_code, 302)
        r=self.client.post('/contractor/login', data={'_csrf':'csrf-test','email':'owner@example.com','password':'initial-test-password'})
        self.assertEqual(r.location, '/contractor/login')

    def test_accept_and_decline_offers(self):
        self.contractor_session()
        for action in ('accept', 'decline'):
            lead=Lead(homeowner_name='Homeowner', phone='6125550199', zip_code='55401', service_needed='Mold Remediation')
            db.session.add(lead); db.session.flush()
            offer=LeadOffer(lead_id=lead.id, contractor_id=self.contractor.id, status='pending', offered_at=datetime.now(timezone.utc)-timedelta(seconds=2), expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
            db.session.add(offer); db.session.commit()
            response=self.client.post(f'/contractor/offers/{offer.id}/{action}', data={'_csrf':'csrf-test'})
            self.assertEqual(response.status_code, 302)
            db.session.refresh(offer)
            self.assertEqual(offer.status, 'accepted' if action == 'accept' else 'declined')
    def test_admin_pages_and_template_compilation(self):
        self.admin()
        for template in app.jinja_env.list_templates():
            app.jinja_env.get_template(template)
        for path in ('/admin', '/admin/national', '/admin/owner-command-center', '/signup', '/privacy', '/terms', '/sms-policy'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
    def test_lead_submission_validation(self):
        self.assertEqual(self.client.post('/api/leads', json={'name':'Homeowner'}).status_code, 400)
        response=self.client.post('/api/leads', json={'name':'Homeowner','phone':'6125550199','zip_code':'55401','service_needed':'Mold Remediation'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['assignment_status'], 'pending')
        self.assertEqual(Lead.query.count(), 1)

    def test_registration_approval_and_duplicate_email(self):
        with self.client.session_transaction() as state: state['_csrf']='csrf-test'
        data={'_csrf':'csrf-test', 'company_name':'New Company', 'contact_name':'Owner', 'email':'new@example.com', 'phone':'6125550123','zip_codes':'55401,55402', 'license_number':'MN-TEST', 'service_type':'Mold Remediation'}
        self.assertEqual(self.client.post('/signup',data=data).status_code, 302)
        applicant=Contractor.query.filter_by(email='new@example.com').one()
        self.assertFalse(applicant.active); self.assertFalse(applicant.verified)
        self.client.post('/signup',data=data)
        self.assertEqual(Contractor.query.filter_by(email='new@example.com').count(),1)
        self.admin()
        self.record_review(applicant.id)
        self.assertEqual(self.client.post(f'/admin/contractors/{applicant.id}/status',data={'_csrf':'csrf-test','action':'approve'}).status_code,302)
        db.session.refresh(applicant)
        self.assertTrue(applicant.active); self.assertTrue(applicant.verified)
    def approve_for_account_notice(self):
        self.contractor.active=False;self.contractor.verified=False;db.session.commit()
        self.admin();self.assertEqual(self.record_review().status_code,302)
        return self.client.post(f'/admin/contractors/{self.contractor.id}/status',
            data={'_csrf':'csrf-test','action':'approve'})

    def test_approval_notice_requires_final_activation_and_deduplicates(self):
        from app import ContractorAccountEvent,Delivery
        self.contractor.active=False;self.contractor.verified=False;db.session.commit();self.admin()
        path=f'/admin/contractors/{self.contractor.id}/status'
        self.assertEqual(self.client.post(path,data={'_csrf':'csrf-test','action':'approve'}).status_code,409)
        self.assertEqual(Delivery.query.count(),0)
        self.assertEqual(self.record_review().status_code,302)
        self.assertEqual(Delivery.query.count(),0)  # Credential review alone cannot grant access.
        for _ in range(2):
            self.assertEqual(self.client.post(path,data={'_csrf':'csrf-test','action':'approve'}).status_code,302)
        event=ContractorAccountEvent.query.one();delivery=db.session.get(Delivery,event.delivery_id)
        self.assertEqual(event.status,'approved');self.assertEqual(delivery.channel,'email')
        self.assertIn('No charge has been made',delivery.body)
        self.assertNotIn('test-license-record',delivery.body)
        self.assertEqual(Delivery.query.count(),1)

    def test_deactivation_cancels_pending_but_preserves_accepted_history(self):
        from app import ContractorAccountEvent,Delivery
        payment=self.add_invoice()
        lead=Lead(homeowner_name='Pending homeowner',phone='6125550111',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.flush()
        pending=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='pending',
            offered_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(pending);db.session.commit();self.admin()
        path=f'/admin/contractors/{self.contractor.id}/status'
        for _ in range(2):
            self.assertEqual(self.client.post(path,data={'_csrf':'csrf-test','action':'deactivate'}).status_code,302)
        db.session.refresh(pending);self.assertEqual(pending.status,'cancelled')
        self.assertEqual(db.session.get(LeadOffer,payment.offer_id).status,'accepted')
        db.session.refresh(payment);self.assertEqual(payment.status,'open')
        self.assertEqual(ContractorAccountEvent.query.one().status,'deactivated')
        self.assertEqual(Delivery.query.count(),1)

    def test_latest_account_notice_supersedes_unsent_older_decisions(self):
        from app import ContractorAccountEvent,Delivery
        from communications import deliver_pending
        self.assertEqual(self.approve_for_account_notice().status_code,302)
        path=f'/admin/contractors/{self.contractor.id}/status'
        for action in ('deactivate','approve'):
            self.assertEqual(self.client.post(path,data={'_csrf':'csrf-test','action':action}).status_code,302)
        self.assertEqual(ContractorAccountEvent.query.count(),3)
        self.assertEqual(Delivery.query.filter_by(status='cancelled').count(),2)
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true'}),patch('communications.resend_email',return_value='approved-notice') as send:
            self.assertEqual(deliver_pending()['sent'],1)
            self.assertEqual(send.call_count,1)
            self.assertIn('is approved',send.call_args.args[0].subject)
        page=self.client.get(f'/admin/contractors/{self.contractor.id}/verification')
        self.assertEqual(page.status_code,200);self.assertIn('Account activity',page.text)

    def test_rejection_notice_can_reach_inactive_account_without_private_notes(self):
        from app import ContractorAccountEvent,Delivery
        from communications import deliver_pending
        self.admin()
        for _ in range(2):
            self.assertEqual(self.record_review(decision='rejected').status_code,302)
        self.assertEqual(ContractorAccountEvent.query.count(),1)
        notice=Delivery.query.one()
        self.assertNotIn('Manually checked test evidence',notice.body)
        self.assertNotIn('test-insurance-record',notice.body)
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true'}),patch('communications.resend_email',return_value='rejected-notice') as send,patch('communications.twilio_sms') as sms:
            self.assertEqual(deliver_pending()['sent'],1);self.assertEqual(send.call_count,1);sms.assert_not_called()
        db.session.refresh(self.contractor);self.assertFalse(self.contractor.active)
        self.contractor_session();self.assertEqual(self.client.get('/contractor/billing').status_code,302)

    def test_notice_subject_or_key_cannot_bypass_inactive_recipient_check(self):
        from app import Delivery
        from communications import deliver_pending
        self.contractor.active=False;self.contractor.verified=False
        db.session.add(Delivery(event_key='account-status:fake',channel='email',recipient=self.contractor.email,
            contractor_id=self.contractor.id,subject='Your contractor account is approved',body='Forged notice'))
        db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true'}),patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['suppressed'],1);send.assert_not_called()

    def test_account_notice_failure_rolls_back_account_change(self):
        from app import ContractorAccountEvent,Delivery
        self.admin()
        with patch('contractor_account_notifications.queue_account_notice',side_effect=RuntimeError('synthetic failure')),self.assertLogs('app',level='ERROR'):
            response=self.client.post(f'/admin/contractors/{self.contractor.id}/status',data={'_csrf':'csrf-test','action':'deactivate'})
        self.assertEqual(response.status_code,500)
        db.session.refresh(self.contractor);self.assertTrue(self.contractor.active)
        self.assertEqual(ContractorAccountEvent.query.count(),0);self.assertEqual(Delivery.query.count(),0)

    def test_expired_credentials_cancel_queued_approval_notice(self):
        from app import CredentialReview,Delivery
        from communications import deliver_pending
        self.assertEqual(self.approve_for_account_notice().status_code,302)
        review=CredentialReview.query.one();review.insurance_expires=(datetime.now(timezone.utc)-timedelta(days=1)).date();db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true'}),patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['cancelled'],1);send.assert_not_called()
        self.assertEqual(Delivery.query.one().status,'cancelled')

    def test_only_one_offer_can_be_accepted(self):
        from contractor_offer_transactions import accept_contractor_offer
        lead=Lead(homeowner_name='Homeowner',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead); db.session.flush()
        offers=[LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='pending',offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)) for _ in range(2)]
        db.session.add_all(offers); db.session.commit()
        self.assertIsNotNone(accept_contractor_offer(db.session,offers[0].id,self.contractor.id)); db.session.commit()
        self.assertIsNone(accept_contractor_offer(db.session,offers[1].id,self.contractor.id)); db.session.rollback()

    def test_friendly_form_errors_keep_details(self):
        response=self.client.post('/api/leads',data={'name':'Homeowner','phone':'bad','zip_code':'55401','service_needed':'Mold Remediation','description':'Please retain my details'})
        self.assertEqual(response.status_code,400)
        self.assertIn('Please retain my details',response.text)
        self.assertIn('value="Homeowner"',response.text)
        self.assertIn('Please enter your name',response.text)
    def test_homepage_avoids_unsubstantiated_claims(self):
        page=self.client.get('/').text
        self.assertNotIn('guaranteed to respond',page)
        self.assertNotIn('cdn.tailwindcss.com',page)
        self.assertIn('No payment details needed',page)

    def test_mobile_markup_across_page_families(self):
        import re
        from restoration_landing_pages import LANDING_PAGES
        from restoration_landing_legacy import PAGES
        self.admin(); self.contractor_session()
        routes=['/','/signup','/contractor-signup','/contractors/apply','/request-received','/privacy','/terms','/sms-policy','/admin/login','/contractor/login','/contractor/dashboard','/admin','/admin/national','/admin/owner-command-center','/usa','/usa/minnesota','/usa/minnesota/twin-cities','/contractor/forgot-password']
        routes += ['/services/'+slug for slug in LANDING_PAGES]
        routes += ['/'+slug for slug in PAGES]
        for route in routes:
            response=self.client.get(route)
            self.assertEqual(response.status_code,200,route)
            self.assertRegex(response.text,r'meta name=[\"\']viewport[\"\']',route)
            self.assertIn('/static/css/compatibility.css',response.text,route)
    def test_responsive_errors_preserve_http_status_and_api_format(self):
        response=self.client.get('/missing-page')
        self.assertEqual(response.status_code,404)
        self.assertIn('/static/css/compatibility.css',response.text)
        response=self.client.get('/api/leads')
        self.assertEqual(response.status_code,405)
        self.assertTrue(response.is_json)
        self.assertIn('POST',response.headers['Allow'])

    def test_contractor_can_manage_own_coverage_only(self):
        self.contractor_session()
        response=self.client.post('/contractor/settings',data={'_csrf':'csrf-test','zip_codes':'55402, 55403,55402','contractor_id':'999'})
        self.assertEqual(response.status_code,302)
        db.session.refresh(self.contractor)
        self.assertEqual(self.contractor.zip_codes,'55402,55403')
        self.assertEqual(self.contractor.service_radius_zip,'55402')
        self.assertTrue(self.contractor.active)
        self.assertEqual(self.client.get('/contractor/settings').status_code,200)
    def test_invalid_coverage_and_csrf_do_not_modify_account(self):
        self.contractor_session()
        self.assertEqual(self.client.post('/contractor/settings',data={'zip_codes':'55402'}).status_code,400)
        response=self.client.post('/contractor/settings',data={'_csrf':'csrf-test','zip_codes':'wrong,55402'})
        self.assertEqual(response.status_code,400)
        db.session.refresh(self.contractor)
        self.assertEqual(self.contractor.zip_codes,'55401')
        with self.client.session_transaction() as state: state.clear()
        self.assertEqual(self.client.get('/contractor/settings').status_code,302)
    def test_admin_matching_preview_has_no_side_effects(self):
        self.admin()
        lead=Lead(homeowner_name='Homeowner',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.commit()
        response=self.client.get(f'/admin/leads/{lead.id}')
        self.assertEqual(response.status_code,200)
        self.assertIn('MN Restoration',response.text)
        self.assertEqual(LeadOffer.query.count(),0)
    def test_cancel_request_cancels_pending_and_preserves_history(self):
        from contractor_offer_transactions import accept_contractor_offer
        self.admin()
        lead=Lead(homeowner_name='Homeowner',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.flush()
        offer=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='pending',offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer);db.session.commit()
        response=self.client.post(f'/admin/leads/{lead.id}/status',data={'_csrf':'csrf-test','status':'Cancelled'})
        self.assertEqual(response.status_code,302)
        db.session.refresh(lead);db.session.refresh(offer)
        self.assertEqual(lead.status,'Cancelled');self.assertEqual(offer.status,'cancelled')
        self.assertIsNone(accept_contractor_offer(db.session,offer.id,self.contractor.id))
        db.session.rollback()
        self.assertEqual(Lead.query.count(),1);self.assertEqual(LeadOffer.query.count(),1)
        self.assertEqual(self.client.post(f'/admin/leads/{lead.id}/status',data={'_csrf':'csrf-test','status':'Closed'}).status_code,409)
    def test_lead_controls_require_admin_and_csrf(self):
        lead=Lead(homeowner_name='Homeowner',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.commit()
        self.assertEqual(self.client.get(f'/admin/leads/{lead.id}').status_code,302)
        self.admin()
        self.assertEqual(self.client.post(f'/admin/leads/{lead.id}/status',data={'status':'Closed'}).status_code,400)
        self.assertEqual(self.client.post(f'/admin/leads/{lead.id}/status',data={'_csrf':'csrf-test','status':'New'}).status_code,400)
        db.session.refresh(lead);self.assertEqual(lead.status,'New')

    def record_review(self, contractor_id=None, decision='approved'):
        contractor_id = contractor_id or self.contractor.id
        expiry = (datetime.now(timezone.utc)+timedelta(days=30)).date().isoformat()
        return self.client.post(f'/admin/contractors/{contractor_id}/verification',data={
            '_csrf':'csrf-test','decision':decision,'notes':'Manually checked test evidence',
            'license_reference':'test-license-record','insurance_reference':'test-insurance-record',
            'license_checked':'yes','insurance_checked':'yes','license_expires':expiry,'insurance_expires':expiry})
    def test_activation_requires_current_credential_review(self):
        self.admin()
        self.contractor.active=False;self.contractor.verified=False;db.session.commit()
        response=self.client.post(f'/admin/contractors/{self.contractor.id}/status',data={'_csrf':'csrf-test','action':'approve'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.record_review().status_code,302)
        response=self.client.post(f'/admin/contractors/{self.contractor.id}/status',data={'_csrf':'csrf-test','action':'approve'})
        self.assertEqual(response.status_code,302)
        db.session.refresh(self.contractor);self.assertTrue(self.contractor.active)
    def test_expired_review_blocks_session_and_matching(self):
        from app import CredentialReview
        from contractor_matching import contractor_matches
        from contractor_login_security import contractor_login_allowed
        self.admin();self.record_review();self.contractor_session()
        review=CredentialReview.query.one()
        review.insurance_expires=(datetime.now(timezone.utc)-timedelta(days=1)).date();db.session.commit()
        lead=Lead(homeowner_name='Homeowner',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        self.assertFalse(contractor_matches(self.contractor,lead))
        self.assertFalse(contractor_login_allowed(self.contractor,'initial-test-password'))
        self.assertEqual(self.client.get('/contractor/dashboard').status_code,302)
    def test_rejected_review_retains_history_and_deactivates(self):
        from app import CredentialReview
        self.admin();self.record_review()
        self.assertEqual(self.record_review(decision='rejected').status_code,302)
        db.session.refresh(self.contractor)
        self.assertFalse(self.contractor.active);self.assertFalse(self.contractor.verified)
        self.assertEqual(CredentialReview.query.count(),2)
    def test_review_requires_admin_csrf_and_evidence(self):
        from app import CredentialReview
        path=f'/admin/contractors/{self.contractor.id}/verification'
        self.assertEqual(self.client.get(path).status_code,302)
        self.admin()
        self.assertEqual(self.client.post(path,data={'decision':'approved'}).status_code,400)
        self.assertEqual(self.client.post(path,data={'_csrf':'csrf-test','decision':'approved','notes':'Missing evidence'}).status_code,400)
        self.assertEqual(CredentialReview.query.count(),0)
    def test_license_change_invalidates_previous_review(self):
        self.admin();self.record_review()
        self.assertTrue(self.contractor.credential_review_current)
        self.contractor.license_number='CHANGED';db.session.commit()
        self.assertFalse(self.contractor.credential_review_current)

    def test_expired_evidence_cannot_be_recorded_as_approved(self):
        from app import CredentialReview
        self.admin()
        yesterday=(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat()
        response=self.client.post(f'/admin/contractors/{self.contractor.id}/verification',data={
            '_csrf':'csrf-test','decision':'approved','notes':'Expired test evidence',
            'license_reference':'test','insurance_reference':'test','license_checked':'yes',
            'insurance_checked':'yes','license_expires':yesterday,'insurance_expires':yesterday})
        self.assertEqual(response.status_code,400)
        self.assertEqual(CredentialReview.query.count(),0)

    def add_invoice(self):
        from app import Payment,MarketBenchmark
        lead=Lead(homeowner_name='Buyer',phone='6125550100',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.flush()
        offer=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='accepted',accepted_at=datetime.now(timezone.utc),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer);db.session.flush()
        evidence=MarketBenchmark(state_code='MN',service_name='Mold Remediation',zip_code='55401',observed_at=datetime.now(timezone.utc),angi_cents=4000,thumbtack_cents=2942,angi_reference='synthetic-angi',thumbtack_reference='synthetic-thumbtack',comparison_basis='comparable_contractor_lead_fee',import_key='test-observation')
        db.session.add(evidence);db.session.flush()
        payment=Payment(offer_id=offer.id,contractor_id=self.contractor.id,amount_cents=2500,currency='usd',price_id=f'market:{evidence.id}',market_benchmark_id=evidence.id,quote_expires_at=datetime.now(timezone.utc)+timedelta(hours=1),session_id='cs_test_1',status='open')
        db.session.add(payment);db.session.commit()
        return payment
    def test_unapproved_contractors_cannot_quote_or_purchase_leads(self):
        payment=self.add_invoice()
        self.contractor_session()
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'test','STRIPE_SECRET_KEY':'sk_test_example','PUBLIC_SITE_URL':'https://example.com','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}
        with patch.dict(os.environ,config),patch('billing.create_checkout') as create,patch('billing.retrieve_checkout') as retrieve:
            for active,verified in ((False,False),(True,False),(False,True)):
                with self.subTest(active=active,verified=verified):
                    self.contractor.active=active;self.contractor.verified=verified;db.session.commit()
                    # Even an earlier session, accepted offer and saved quote grant no access.
                    for path in ('/contractor/billing',f'/contractor/offers/{payment.offer_id}/quote',f'/contractor/offers/{payment.offer_id}/checkout'):
                        response=self.client.get(path) if path.endswith('billing') else self.client.post(path,data={'_csrf':'csrf-test'})
                        self.assertEqual(response.status_code,302)
                        self.assertTrue(response.location.endswith('/contractor/login'))
            create.assert_not_called();retrieve.assert_not_called()
        db.session.refresh(payment);self.assertEqual(payment.status,'open')

    def test_admin_deactivation_blocks_purchase_with_existing_session(self):
        payment=self.add_invoice()
        self.contractor_session();self.admin()
        self.assertEqual(self.client.post(f'/admin/contractors/{self.contractor.id}/status',data={'_csrf':'csrf-test','action':'deactivate'}).status_code,302)
        with patch('billing.create_checkout') as create,patch('billing.retrieve_checkout') as retrieve:
            for action in ('quote','checkout'):
                response=self.client.post(f'/contractor/offers/{payment.offer_id}/{action}',data={'_csrf':'csrf-test'})
                self.assertEqual(response.status_code,302)
                self.assertTrue(response.location.endswith('/contractor/login'))
            create.assert_not_called();retrieve.assert_not_called()

    def stripe_post(self,payment,event_id='evt_test',amount=2500,kind='checkout.session.completed',payment_status='paid'):
        import json,time,hmac
        obj={'id':payment.session_id,'mode':'payment','payment_status':payment_status,'amount_total':amount,'currency':'usd','payment_intent':'pi_test','metadata':{'payment_id':str(payment.id),'contractor_id':str(payment.contractor_id)}}
        from app import Payment
        stored=db.session.get(Payment,payment.id)
        if stored.market_benchmark_id:obj['metadata']['benchmark_id']=str(stored.market_benchmark_id)
        if kind=='charge.refunded':obj={'id':'ch_test','payment_intent':'pi_test','amount_refunded':amount}
        raw=json.dumps({'id':event_id,'type':kind,'livemode':False,'data':{'object':obj}})
        stamp=str(int(time.time()));signature=hmac.new(b'whsec_test',(stamp+'.'+raw).encode(),hashlib.sha256).hexdigest()
        with patch.dict(os.environ,{'STRIPE_WEBHOOK_SECRET':'whsec_test','STRIPE_MODE':'test'}):
            return self.client.post('/webhooks/stripe',data=raw,content_type='application/json',headers={'Stripe-Signature':'t='+stamp+',v1='+signature})
    def test_signed_stripe_payment_replay_and_refund(self):
        from app import Delivery
        payment=self.add_invoice()
        self.assertEqual(self.stripe_post(payment).status_code,204)
        self.assertEqual(self.stripe_post(payment).status_code,204)
        self.assertEqual(self.stripe_post(payment,event_id='evt_second').status_code,204)
        db.session.refresh(payment);self.assertEqual(payment.status,'paid')
        self.assertEqual(Delivery.query.filter_by(event_key=f'payment:{payment.id}:receipt').count(),1)
        self.assertEqual(self.stripe_post(payment,event_id='evt_refund',kind='charge.refunded').status_code,204)
        db.session.refresh(payment);self.assertEqual(payment.status,'refunded')
        self.assertEqual(self.stripe_post(payment,event_id='evt_late').status_code,204)
        db.session.refresh(payment);self.assertEqual(payment.status,'refunded')
    def test_stripe_rejects_forgery_and_amount_mismatch(self):
        from app import ProviderEvent
        payment=self.add_invoice()
        with patch.dict(os.environ,{'STRIPE_WEBHOOK_SECRET':'whsec_test'}):
            self.assertEqual(self.client.post('/webhooks/stripe',json={},headers={'Stripe-Signature':'forged'}).status_code,400)
        self.assertEqual(self.stripe_post(payment,amount=1).status_code,400)
        db.session.refresh(payment);self.assertEqual(payment.status,'open')
        self.assertEqual(ProviderEvent.query.count(),0)
    def test_resend_queue_disabled_and_duplicate_safe(self):
        from app import Delivery
        from communications import queue_email,deliver_pending
        queue_email('test-email','recipient@example.com','Receipt','Saved request');db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'false'}),patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['disabled'],1);send.assert_not_called()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true'}),patch('communications.resend_email',return_value='resend_test') as send:
            self.assertEqual(deliver_pending()['sent'],1)
            self.assertEqual(deliver_pending()['sent'],0)
            self.assertEqual(send.call_count,1)
        self.assertEqual(Delivery.query.one().status,'sent')
    def test_uncertain_delivery_is_not_auto_retried(self):
        from app import Delivery
        from communications import queue_email,deliver_pending
        queue_email('test-timeout','recipient@example.com','Receipt','Saved request');db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true'}),patch('communications.resend_email',side_effect=TimeoutError) as send:
            self.assertEqual(deliver_pending()['uncertain'],1)
            self.assertEqual(deliver_pending()['uncertain'],0)
            self.assertEqual(send.call_count,1)
        self.assertEqual(Delivery.query.one().status,'uncertain')
    def test_sms_requires_consent_at_delivery(self):
        from app import Delivery
        from communications import queue_offer,deliver_pending
        payment=self.add_invoice();offer=db.session.get(LeadOffer,payment.offer_id);offer.status='pending'
        queue_offer(offer,self.contractor);db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'false','SMS_SENDING_ENABLED':'true'}),patch('communications.twilio_sms') as send:
            self.assertEqual(deliver_pending()['suppressed'],1);send.assert_not_called()
        self.assertEqual(Delivery.query.filter_by(channel='sms').one().status,'suppressed')
    def test_twilio_signed_status_cannot_regress(self):
        from app import Delivery
        from twilio.request_validator import RequestValidator
        row=Delivery(event_key='sms:test',channel='sms',recipient='6125550100',subject='Offer',body='Test',provider_id='SMtest',status='sent')
        db.session.add(row);db.session.commit()
        url='https://example.com/webhooks/twilio/status'
        with patch.dict(os.environ,{'TWILIO_STATUS_WEBHOOK_URL':url,'TWILIO_AUTH_TOKEN':'twilio_test'}):
            self.assertEqual(self.client.post('/webhooks/twilio/status',data={'MessageSid':'SMtest','MessageStatus':'delivered'}).status_code,403)
            for status in ['delivered','failed']:
                data={'MessageSid':'SMtest','MessageStatus':status}
                sig=RequestValidator('twilio_test').compute_signature(url,data)
                self.assertEqual(self.client.post('/webhooks/twilio/status',data=data,headers={'X-Twilio-Signature':sig}).status_code,204)
        db.session.refresh(row);self.assertEqual(row.status,'delivered')
    def test_stripe_checkout_uses_server_price_and_session(self):
        import stripe
        from app import Payment
        payment=self.add_invoice();payment.session_id=None;payment.status='creating';db.session.commit()
        self.contractor_session()
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'test','STRIPE_SECRET_KEY':'sk_test_example','PUBLIC_SITE_URL':'https://example.com','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}
        with patch.dict(os.environ,config),patch('billing.create_checkout',return_value={'id':'cs_test_new','url':'https://checkout.stripe.com/test'}) as create,patch('billing.retrieve_checkout',return_value={'status':'open','url':'https://checkout.stripe.com/test'}):
            data={'_csrf':'csrf-test','amount':'1','contractor_id':'999'}
            url=f'/contractor/offers/{payment.offer_id}/checkout'
            self.assertEqual(self.client.post(url,data=data).status_code,303)
            self.assertEqual(self.client.post(url,data=data).status_code,303)
            self.assertEqual(create.call_count,1)
            self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['unit_amount'],2500)
            self.assertNotIn('payment_method_types',create.call_args.kwargs)
    def test_live_stripe_requires_separate_enable_and_integrations_hide_keys(self):
        import stripe
        payment=self.add_invoice();self.contractor_session()
        with patch.dict(os.environ,{'PAYMENTS_ENABLED':'true','STRIPE_MODE':'live','STRIPE_LIVE_PAYMENTS_ENABLED':'false','STRIPE_SECRET_KEY':'sk_live_hidden'}),patch('billing.create_checkout') as create:
            self.assertEqual(self.client.post(f'/contractor/offers/{payment.offer_id}/checkout',data={'_csrf':'csrf-test'}).status_code,503)
            create.assert_not_called()
            self.admin();response=self.client.get('/admin/integrations')
            self.assertEqual(response.status_code,200);self.assertNotIn('sk_live_hidden',response.text)

    def test_consumer_and_contractor_receipts_both_use_resend(self):
        import io, json
        from app import Delivery
        from communications import deliver_pending
        self.assertEqual(self.client.post('/api/leads',json={
            'name':'Consumer','phone':'6125550100','email':'consumer@example.com',
            'zip_code':'55401','service_needed':'Mold Remediation'}).status_code,201)
        with self.client.session_transaction() as state: state['_csrf']='csrf-test'
        self.assertEqual(self.client.post('/signup',data={
            '_csrf':'csrf-test','company_name':'Applicant','contact_name':'Owner',
            'email':'applicant@example.com','phone':'6125550123','zip_codes':'55401',
            'license_number':'TEST-APPLICATION','service_type':'Mold Remediation'}).status_code,302)
        self.assertEqual({row.recipient for row in Delivery.query.all()},
                         {'consumer@example.com','applicant@example.com'})
        self.assertTrue(all(row.channel=='email' for row in Delivery.query.all()))
        responses=[io.BytesIO(b'{"id":"consumer-receipt"}'),io.BytesIO(b'{"id":"contractor-receipt"}')]
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true','SMS_SENDING_ENABLED':'false'}),patch('communications.urlopen',side_effect=responses) as send:
            self.assertEqual(deliver_pending()['sent'],2)
            self.assertEqual(send.call_count,2)
            recipients=set()
            for call in send.call_args_list:
                req=call.args[0]
                self.assertEqual(req.full_url,'https://api.resend.com/emails')
                recipients.update(json.loads(req.data)['to'])
            self.assertEqual(recipients,{'consumer@example.com','applicant@example.com'})
        self.assertTrue(all(row.status=='sent' for row in Delivery.query.all()))

    def test_resend_adapter_uses_transactional_payload_and_key(self):
        import io,json
        from app import Delivery
        from communications import resend_email
        row=Delivery(event_key='receipt:1',channel='email',recipient='recipient@example.com',subject='Receipt',body='Saved')
        with patch.dict(os.environ,{'RESEND_API_KEY':'re_dummy','RESEND_FROM_EMAIL':'Restoration <sender@example.com>'}),patch('communications.urlopen',return_value=io.BytesIO(b'{"id":"resend_dummy"}')) as send:
            self.assertEqual(resend_email(row),'resend_dummy')
            req=send.call_args.args[0]
            self.assertEqual(req.full_url,'https://api.resend.com/emails')
            self.assertEqual(req.get_header('Idempotency-key'),'receipt:1')
            self.assertEqual(json.loads(req.data)['to'],['recipient@example.com'])
    def test_early_sms_callback_survives_send_completion(self):
        from app import Delivery
        from sqlalchemy import update
        from twilio.request_validator import RequestValidator
        row=Delivery(event_key='early-sms',channel='sms',recipient='6125550100',subject='Offer',body='Test',status='sending')
        db.session.add(row);db.session.commit()
        base='https://example.com/webhooks/twilio/status';url=base+'?delivery_id='+str(row.id)
        data={'MessageSid':'SMearly','MessageStatus':'delivered'}
        with patch.dict(os.environ,{'TWILIO_STATUS_WEBHOOK_URL':base,'TWILIO_AUTH_TOKEN':'twilio_test'}):
            sig=RequestValidator('twilio_test').compute_signature(url,data)
            response=self.client.post('/webhooks/twilio/status?delivery_id='+str(row.id),data=data,headers={'X-Twilio-Signature':sig})
            self.assertEqual(response.status_code,204)
        db.session.execute(update(Delivery).where(Delivery.id==row.id,Delivery.status=='sending').values(status='sent',provider_id='SMearly'));db.session.commit()
        db.session.refresh(row);self.assertEqual(row.status,'delivered')

    def test_early_stripe_webhook_cannot_be_downgraded_by_checkout(self):
        import stripe
        from app import Payment
        payment=self.add_invoice();payment.session_id=None;payment.status='creating';db.session.commit()
        self.contractor_session()
        def create_session(**kwargs):
            from types import SimpleNamespace
            event_payment=SimpleNamespace(id=payment.id,contractor_id=payment.contractor_id,session_id='cs_early')
            self.assertEqual(self.stripe_post(event_payment,event_id='evt_early').status_code,204)
            return {'id':'cs_early','url':'https://checkout.stripe.com/test'}
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'test','STRIPE_SECRET_KEY':'sk_test_example','PUBLIC_SITE_URL':'https://example.com','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}
        with patch.dict(os.environ,config),patch('billing.create_checkout',side_effect=create_session):
            response=self.client.post(f'/contractor/offers/{payment.offer_id}/checkout',data={'_csrf':'csrf-test'})
            self.assertEqual(response.status_code,303)
        db.session.refresh(payment);self.assertEqual(payment.status,'paid');self.assertEqual(payment.session_id,'cs_early')

    def test_daily_market_quote_uses_evidence_not_assigned_prices(self):
        from app import Payment,LeadPrice,MarketBenchmark
        old=self.add_invoice();offer_id=old.offer_id;db.session.delete(old);db.session.commit()
        db.session.add(LeadPrice(state_code='MN',service_name='Mold Remediation',mode='test',stripe_price_id='price_ignored'))
        db.session.commit();self.contractor_session()
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'test','STRIPE_SECRET_KEY':'sk_test_example','PUBLIC_SITE_URL':'https://example.com','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}
        with patch.dict(os.environ,config),patch('market_pricing.quote_from_benchmark',return_value=(2500,datetime.now(timezone.utc)+timedelta(hours=1))):
            response=self.client.post(f'/contractor/offers/{offer_id}/quote',data={'_csrf':'csrf-test','state':'TX','amount':'1'})
            self.assertEqual(response.status_code,200)
            self.assertIn('15%',response.text)
        row=Payment.query.one();self.assertEqual(row.amount_cents,2500);self.assertIsNotNone(row.market_benchmark_id)
        self.assertNotEqual(row.price_id,'price_ignored')
    def test_assigned_price_mapping_is_disabled(self):
        from app import LeadPrice
        self.admin()
        response=self.client.post('/admin/pricing',data={'_csrf':'csrf-test','state':'MN','service':'Mold Remediation','stripe_price_id':'price_mn'})
        self.assertEqual(response.status_code,409);self.assertEqual(LeadPrice.query.count(),0)
        self.assertIn('Daily market pricing',self.client.get('/admin/pricing').text)
    def test_expansion_state_cannot_enter_minnesota_intake(self):
        response=self.client.post('/api/leads',json={'name':'Homeowner','phone':'6125550100','zip_code':'55401','service_needed':'Mold Remediation','state':'TX'})
        self.assertEqual(response.status_code,400);self.assertEqual(Lead.query.count(),0)

    def test_missing_email_configuration_does_not_consume_queue(self):
        from app import Delivery
        from communications import queue_email,deliver_pending
        queue_email('missing-config','recipient@example.com','Receipt','Saved');db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true','RESEND_FROM_EMAIL':''}),patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['disabled'],1);send.assert_not_called()
        self.assertEqual(Delivery.query.one().status,'pending')

    def test_market_formula_is_15_percent_below_both_and_rounds_down(self):
        from market_pricing import quote_from_benchmark
        from types import SimpleNamespace
        now=datetime(2026,11,1,18,tzinfo=timezone.utc)
        row=SimpleNamespace(observed_at=now,angi_cents=10001,thumbtack_cents=9001,angi_reference='source-a',thumbtack_reference='source-b',comparison_basis='comparable_contractor_lead_fee')
        amount,expires=quote_from_benchmark(row,now)
        self.assertEqual(amount,7650);self.assertLessEqual(amount*100,9001*85)
        row.observed_at=now-timedelta(days=1)
        from werkzeug.exceptions import ServiceUnavailable
        with self.assertRaises(ServiceUnavailable):quote_from_benchmark(row,now)
    def test_market_data_missing_blocks_quote_without_fallback(self):
        from app import Payment,MarketBenchmark
        old=self.add_invoice();offer_id=old.offer_id;db.session.delete(old);db.session.commit()
        evidence=MarketBenchmark.query.one();evidence.observed_at=datetime.now(timezone.utc)-timedelta(days=1);db.session.commit()
        self.contractor_session()
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'test','STRIPE_SECRET_KEY':'sk_test_example','PUBLIC_SITE_URL':'https://example.com','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}
        with patch.dict(os.environ,config):
            self.assertEqual(self.client.post(f'/contractor/offers/{offer_id}/quote',data={'_csrf':'csrf-test'}).status_code,503)
        self.assertEqual(Payment.query.count(),0)
    def test_expired_quote_cannot_start_checkout(self):
        payment=self.add_invoice();payment.quote_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.session.commit();self.contractor_session()
        config={'PAYMENTS_ENABLED':'true','STRIPE_MODE':'test','STRIPE_SECRET_KEY':'sk_test_example','PUBLIC_SITE_URL':'https://example.com','PAYMENTS_ACTIVATION_UTC':'2020-01-01T00:00:00Z'}
        with patch.dict(os.environ,config),patch('billing.create_checkout') as create:
            self.assertEqual(self.client.post(f'/contractor/offers/{payment.offer_id}/checkout',data={'_csrf':'csrf-test'}).status_code,409);create.assert_not_called()
    def test_async_payment_confirms_only_after_paid_event(self):
        from app import Delivery
        payment=self.add_invoice()
        self.assertEqual(self.stripe_post(payment,payment_status='unpaid').status_code,204)
        db.session.refresh(payment);self.assertEqual(payment.status,'awaiting_payment');self.assertEqual(Delivery.query.count(),0)
        self.assertEqual(self.stripe_post(payment,event_id='evt_async',kind='checkout.session.async_payment_succeeded').status_code,204)
        db.session.refresh(payment);self.assertEqual(payment.status,'paid');self.assertEqual(Delivery.query.count(),1)
    def test_unconfigured_daily_collector_cannot_invent_observations(self):
        from market_pricing import refresh_benchmarks
        from app import MarketBenchmark
        with patch.dict(app.config,{'MARKET_BENCHMARK_COLLECTOR':None}):
            with self.assertRaises(RuntimeError):refresh_benchmarks()
        self.assertEqual(MarketBenchmark.query.count(),0)

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
        self.env = patch.dict(os.environ, {'ADMIN_PASSWORD_HASH': generate_password_hash('administrator-test-password'), 'CONTRACTOR_LOGIN_LOCK_SECRET': 's'*40})
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
            s.update(admin_authenticated=True, admin_login_at=datetime.now(timezone.utc).timestamp(), admin_password_fingerprint=current_password_fingerprint(), _csrf='csrf-test')
    def contractor_session(self):
        with self.client.session_transaction() as s:
            s.update(create_contractor_session_data(self.contractor.id))
            s['contractor_password_fingerprint'] = hashlib.sha256(self.contractor.password_hash.encode()).hexdigest()
            s['_csrf'] = 'csrf-test'
    def setup_link(self):
        self.admin()
        r = self.client.post(f'/admin/contractors/{self.contractor.id}/password-setup', data={'_csrf':'csrf-test'})
        self.assertEqual(r.status_code, 200)
        return re.search(r'href="(/contractor/password-setup/[^"]+)"', r.text).group(1)
    def test_setup_login_reuse_and_reset_revocation(self):
        self.contractor_session()
        link = self.setup_link()
        r = self.client.post(link, data={'_csrf':'csrf-test','password':'replacement-password','confirm_password':'replacement-password'})
        self.assertEqual(r.status_code, 302)
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
        row = ContractorPasswordSetupToken.query.order_by(ContractorPasswordSetupToken.id.desc()).first()
        row.expires_at = datetime.now(timezone.utc)-timedelta(minutes=1); db.session.commit()
        self.assertEqual(self.client.post(second, data={'_csrf':'csrf-test','password':'replacement-password','confirm_password':'replacement-password'}).status_code, 400)
    def test_admin_password_change_blocks_owner_report(self):
        self.admin()
        os.environ['ADMIN_PASSWORD_HASH'] = generate_password_hash('changed-administrator-password')
        self.assertEqual(self.client.get('/admin/owner-command-center').status_code, 403)
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
        self.assertEqual(self.client.post(f'/admin/contractors/{applicant.id}/status',data={'_csrf':'csrf-test','action':'approve'}).status_code,302)
        db.session.refresh(applicant)
        self.assertTrue(applicant.active); self.assertTrue(applicant.verified)
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
        routes=['/','/signup','/contractor-signup','/contractors/apply','/request-received','/privacy','/terms','/sms-policy','/admin/login','/contractor/login','/contractor/dashboard','/admin','/admin/national','/admin/owner-command-center','/usa','/usa/minnesota','/usa/minnesota/twin-cities','/contractor/password-setup/preview']
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

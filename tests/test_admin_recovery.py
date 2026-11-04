import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import re
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import app, db, AdminCredential, AdminRecoveryToken as Token, Delivery
from admin_auth import verify_admin_password
from admin_session_security import current_password_fingerprint, session_password_valid
from communications import deliver_pending

class AdminRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,dict(ADMIN_OWNER_EMAIL='owner@example.com',
            ADMIN_PASSWORD_HASH=generate_password_hash('original-owner-password'), EMAIL_TEST_ONLY='true',
            EMAIL_TEST_RECIPIENTS='owner@example.com',EMAIL_SENDING_ENABLED='true',
            SMS_SENDING_ENABLED='false',RESEND_API_KEY='synthetic',RESEND_FROM_EMAIL='sender@example.com'))
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()
    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()
    def csrf(self, client=None):
        with (client or self.client).session_transaction() as state:state['_csrf']='admin-recovery-test'
        return {'_csrf':'admin-recovery-test'}
    def issue(self,email='owner@example.com'):
        return self.client.post('/admin/forgot-password',data={**self.csrf(),'email':email},follow_redirects=True)
    def link(self):
        token=Token.query.order_by(Token.id.desc()).first()
        return re.search(r'https://www.restorationcontractorsmn.com(\S+)',db.session.get(Delivery,token.delivery_id).body).group(1)
    def save(self,link,**extra):
        return self.client.post(link,data={**self.csrf(),'password':'new-owner-password','confirm_password':'new-owner-password',**extra})
    def test_owner_only_generic_responses_fixed_origin_and_private_headers(self):
        known=self.issue(' OWNER@example.com ');link=self.link()
        self.assertEqual(known.status_code,200);self.assertEqual(known.text,self.issue('unknown@example.com').text)
        self.assertNotIn(link,known.text);self.assertEqual(Token.query.count(),1)
        self.assertIn('no-store',known.headers['Cache-Control'])
        self.assertIn('no-referrer',self.client.get(link).headers['Referrer-Policy'])
        self.assertNotIn(link.rsplit('/',1)[1],Token.query.one().token_hash)
        self.assertIn('/admin/forgot-password',self.client.get('/admin/login').text)
    def test_single_use_changes_login_revokes_sessions_and_confirms_by_email(self):
        old=current_password_fingerprint();self.issue();link=self.link()
        self.assertEqual(self.client.get(link).status_code,200);self.assertIsNone(Token.query.one().used_at)
        self.assertEqual(self.save(link).status_code,303)
        self.assertTrue(verify_admin_password('new-owner-password'));self.assertFalse(verify_admin_password('original-owner-password'))
        self.assertFalse(session_password_valid(old));self.assertEqual(self.save(link).status_code,400)
        self.assertEqual(self.client.get(link).status_code,400)
        self.assertEqual(Delivery.query.filter_by(subject='Your administrator password was changed').count(),1)
        response=self.client.post('/admin/login',data={**self.csrf(),'email':'owner@example.com','password':'new-owner-password'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get('/admin').status_code,200)
    def test_csrf_validation_and_password_confirmation_do_not_consume_link(self):
        self.assertEqual(self.client.post('/admin/forgot-password',data={'email':'owner@example.com'}).status_code,400)
        self.issue();link=self.link()
        self.assertEqual(self.client.post(link,data={'password':'new-owner-password'}).status_code,400)
        for extra in ({'password':'short','confirm_password':'short'},{'confirm_password':'mismatched'}):
            self.assertEqual(self.save(link,**extra).status_code,400);self.assertIsNone(Token.query.one().used_at)
        self.assertEqual(self.save(link).status_code,303)
    def test_reissue_expiry_and_delivery_guard(self):
        self.issue();old=self.link();self.issue();new=self.link()
        self.assertEqual(self.client.get(old).status_code,400)
        with patch('communications.resend_email',return_value='synthetic-provider') as send:
            result=deliver_pending();self.assertEqual(result['sent'],1);self.assertEqual(result['cancelled'],1)
            self.assertIn(new,send.call_args.args[0].body)
        row=Token.query.order_by(Token.id.desc()).first();row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.session.commit()
        self.assertEqual(self.save(new).status_code,400)
    def test_configuration_rotation_invalidates_override_links_and_sessions(self):
        self.issue();self.save(self.link());saved=current_password_fingerprint();self.issue();link=self.link()
        for changes in ({'ADMIN_OWNER_EMAIL':'changed@example.com'}, {'ADMIN_PASSWORD_HASH':generate_password_hash('rotated-owner-password')}):
            with patch.dict(os.environ,changes):
                self.assertEqual(self.save(link).status_code,400)
                self.assertFalse(verify_admin_password('new-owner-password'))
                self.assertFalse(session_password_valid(saved))
        with patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':generate_password_hash('rotated-owner-password')}):
            self.issue();self.assertEqual(self.save(self.link()).status_code,303)
            self.assertTrue(verify_admin_password('new-owner-password'))
    def test_disabled_unconfigured_and_non_allowlisted_never_issue(self):
        for changes in ({'ADMIN_OWNER_EMAIL':''},{'ADMIN_PASSWORD_HASH':''},{'EMAIL_TEST_RECIPIENTS':'other@example.com'}):
            with patch.dict(os.environ,changes):
                self.assertEqual(self.issue().status_code,200);self.assertEqual(Token.query.count(),0)
    def test_worker_sends_without_administrator_environment_credentials(self):
        self.issue();link=self.link()
        with patch.dict(os.environ,{'ADMIN_OWNER_EMAIL':'','ADMIN_PASSWORD_HASH':''}), patch('communications.resend_email',return_value='synthetic-worker-provider') as send:
            result=deliver_pending();self.assertEqual(result['sent'],1)
            self.assertIn(link,send.call_args.args[0].body)
        self.save(link)
        self.issue();new=self.link();self.save(new)
        with patch.dict(os.environ,{'ADMIN_OWNER_EMAIL':'','ADMIN_PASSWORD_HASH':''}), patch('communications.resend_email',return_value='synthetic-confirmation'):
            # Used reset links are cancelled even without web-only secrets.
            self.assertFalse(__import__('admin_recovery').admin_recovery_notice_current(Delivery.query.filter(Delivery.event_key.like('admin-recovery:%')).first()))

    def test_rate_limit_is_persistent_and_no_reset_by_get(self):
        for _ in range(5):self.assertEqual(self.issue().status_code,200)
        self.assertEqual(Token.query.count(),3)
        link=self.link();self.client.get(link);self.assertTrue(verify_admin_password('original-owner-password'))

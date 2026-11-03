import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import time
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import app,db

class AdminAccessMessageTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':generate_password_hash('synthetic-owner-password'),'ADMIN_OWNER_EMAIL':'owner@example.com'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()
    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()
    def login(self,**extra):
        with self.client.session_transaction() as state:state['_csrf']='synthetic-owner-csrf'
        data=dict(email='owner@example.com',password='synthetic-owner-password',_csrf='synthetic-owner-csrf')
        data.update(extra);return self.client.post('/admin/login',data=data)
    def test_private_get_and_post_show_signin_without_granting_access_or_replaying_forms(self):
        response=self.client.get('/admin/pricing')
        self.assertEqual(response.status_code,302)
        self.assertIn('/admin/login?next=',response.location)
        login=self.client.get(response.location)
        self.assertIn('one hour',login.text)
        self.assertIn('name="email"',login.text)
        self.assertNotIn('Validate and import evidence',response.text)
        self.assertIn('no-store',response.headers['Cache-Control'])
        response=self.client.post('/admin/pricing/import',data={'authorized':'yes'})
        self.assertEqual(response.status_code,403)
        self.assertIn('review the form before submitting it again',response.text)
        self.assertNotIn('<form',response.text)
        api=self.client.get('/admin/pricing',json={})
        self.assertEqual(api.status_code,403);self.assertTrue(api.is_json)
        self.assertNotIn('<html',api.text)
    def test_other_errors_keep_their_status_and_do_not_request_admin_signin(self):
        response=self.client.get('/no-such-page')
        self.assertEqual(response.status_code,404)
        self.assertNotIn('Sign in as administrator',response.text)
    def test_owner_email_and_password_are_both_required_and_email_is_case_insensitive(self):
        for changes in ({'email':''},{'email':'other@example.com'},{'email':'\u2603@example.com'},{'password':'wrong'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.login(**changes).status_code,401)
                self.assertEqual(self.client.get('/admin/access').status_code,302)
        self.assertEqual(self.login(email=' OWNER@EXAMPLE.COM ').status_code,302)
        response=self.client.get('/admin/access')
        self.assertEqual(response.status_code,200);self.assertIn('owner@example.com',response.text)
        self.assertIn('Master administration',response.text)
        self.assertIn('no-store',response.headers['Cache-Control'])
    def test_successful_login_returns_to_requested_admin_page_and_blocks_external_redirects(self):
        destination='/admin/finance?mode=test&state=MN'
        self.assertEqual(self.login(next=destination).location,destination)
        for value in ('https://example.com','//example.com','/\\example.com','/contractor/dashboard',
                      '/admin/login','/admin/logout','https://[broken','/admin/not-a-route','/admin\r\nLocation:example.com',
                      '/admin/contractors/1/status','/admin#fragment'):
            with self.subTest(value=value):
                self.assertEqual(self.login(next=value).location,'/admin')
    def test_password_rotation_expiry_and_malformed_sessions_require_signin_again(self):
        from admin_session_security import current_password_fingerprint
        for at in (time.time()-3601,time.time()+30,True,float('nan'),'timestamp'):
            with self.client.session_transaction() as state:
                state.update(admin_authenticated=True,admin_login_at=at,admin_password_fingerprint=current_password_fingerprint())
            self.assertEqual(self.client.get('/admin/access').status_code,302)
        self.login()
        with patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':generate_password_hash('synthetic-rotated-password')}):
            self.assertEqual(self.client.get('/admin/access').status_code,302)
    def test_master_directory_links_all_sections_and_previews_without_opening_markets(self):
        self.login();response=self.client.get('/admin/access')
        routes=('/admin','/admin/owner-command-center','/admin/finance','/admin/finance/export.csv',
                '/admin/integrations','/admin/pricing','/admin/national','/admin/national/applications',
                '/admin/service-requests','/admin/rewards')
        for path in routes:
            with self.subTest(path=path):
                self.assertIn('href="'+path+'"',response.text)
                self.assertEqual(self.client.get(path).status_code,200)
        from national_markets import STATES,enabled
        for slug in STATES:
            self.assertIn('/admin/national/preview/'+slug,response.text)
            self.assertEqual(self.client.get('/admin/national/preview/'+slug).status_code,200)
            if slug!='minnesota':self.assertFalse(enabled(slug))
    def test_csrf_still_required_and_public_pages_do_not_show_owner_identity(self):
        self.assertEqual(self.client.post('/admin/login',data={'email':'owner@example.com','password':'synthetic-owner-password'}).status_code,400)
        self.login()
        self.assertNotIn('owner@example.com',self.client.get('/').text)

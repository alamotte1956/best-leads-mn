import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import re
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import app,db,Contractor,Lead,Delivery,AccessRecoveryToken as Token,AccessRecoveryAttempt as Attempt,ContractorPasswordSetupToken
from account_recovery import ACK
from communications import deliver_pending
from contractor_password_security import hash_contractor_password,verify_contractor_password
from contractor_session_security import create_contractor_session_data,contractor_session_valid


class AccountRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'EMAIL_TEST_ONLY':'false','EMAIL_SENDING_ENABLED':'true',
            'SMS_SENDING_ENABLED':'false','RESEND_API_KEY':'synthetic','RESEND_FROM_EMAIL':'sender@example.com'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.client=app.test_client()
        self.contractor=Contractor(company_name='Synthetic',contact_name='Owner',email='owner@example.com',
            phone='6125550100',zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,
            is_test=False,password_hash=hash_contractor_password('old-synthetic-password'))
        self.lead=Lead(homeowner_name='Private Owner',email='home@example.com',phone='6125550199',zip_code='55401',service_needed='Mold Remediation',status='New')
        db.session.add_all([self.contractor,self.lead]);db.session.commit()

    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()

    def csrf(self,client=None):
        with (client or self.client).session_transaction() as state:
            state['_csrf']='recovery-test'
        return {'_csrf':'recovery-test'}

    def issue(self,kind='contractor',email=None):
        path='/contractor/forgot-password' if kind=='contractor' else '/request-access'
        data=self.csrf();data['email']=email or ('owner@example.com' if kind=='contractor' else 'home@example.com')
        return self.client.post(path,data=data,follow_redirects=True)

    def link(self,kind='contractor'):
        row=Token.query.filter_by(purpose=kind).order_by(Token.id.desc()).first()
        body=db.session.get(Delivery,row.delivery_id).body
        return re.search(r'https://www\.restorationcontractorsmn\.com([^\s]+)',body).group(1)

    def test_known_unknown_and_throttled_accounts_get_identical_public_response(self):
        known=self.issue(email=' OWNER@EXAMPLE.COM ')
        self.assertEqual(known.status_code,200);self.assertIn(ACK,known.text)
        self.assertEqual(known.text,self.issue(email='missing@example.com').text)
        self.assertNotIn(self.link(),known.text)
        self.assertEqual(Token.query.count(),1)
        for _ in range(4): self.assertEqual(self.issue().text,known.text)
        self.assertEqual(Token.query.count(),3)
        self.assertTrue(all(len(r.identifier_hash)==64 for r in Attempt.query.all()))

    def test_reset_is_single_use_revokes_old_sessions_and_admin_setup_links(self):
        old=self.contractor.password_hash
        state=create_contractor_session_data(self.contractor.id)
        state['contractor_password_fingerprint']=hashlib.sha256(old.encode()).hexdigest()
        db.session.add(ContractorPasswordSetupToken(contractor_id=self.contractor.id,token_hash='a'*64,
            expires_at=datetime.now(timezone.utc)+timedelta(hours=1)));db.session.commit()
        self.issue();link=self.link();self.assertEqual(self.client.get(link).status_code,200)
        self.assertIsNone(Token.query.one().used_at)
        data={**self.csrf(),'password':'new-synthetic-password','confirm_password':'new-synthetic-password'}
        self.assertEqual(self.client.post(link,data=data).status_code,303)
        db.session.refresh(self.contractor)
        self.assertTrue(verify_contractor_password(self.contractor.password_hash,'new-synthetic-password'))
        self.assertFalse(contractor_session_valid(state,self.contractor))
        self.assertIsNotNone(ContractorPasswordSetupToken.query.one().used_at)
        self.assertEqual(self.client.post(link,data=data).status_code,400)
        self.assertEqual(self.client.get(link).status_code,400)
        self.assertEqual(Delivery.query.filter_by(subject='Your contractor password was changed').count(),1)

    def test_csrf_and_password_validation_do_not_consume_token(self):
        self.issue();link=self.link()
        self.assertEqual(self.client.post(link,data={'password':'new-synthetic-password'}).status_code,400)
        for password,confirm in [('short','short'),('new-synthetic-password','different-password')]:
            self.assertEqual(self.client.post(link,data={**self.csrf(),'password':password,'confirm_password':confirm}).status_code,400)
        self.assertIsNone(Token.query.one().used_at)
        self.assertEqual(self.client.post('/contractor/forgot-password',data={'email':'owner@example.com'}).status_code,400)

    def test_reissue_cancels_old_notice_and_sends_only_current_link(self):
        self.issue();old=self.link();self.issue();new=self.link()
        self.assertNotEqual(old,new);self.assertEqual(self.client.get(old).status_code,400)
        with patch('communications.resend_email',return_value='synthetic-provider') as send:
            result=deliver_pending();self.assertEqual(result['cancelled'],1);self.assertEqual(result['sent'],1)
            self.assertIn(new,send.call_args.args[0].body)

    def test_expired_or_changed_account_notices_are_cancelled(self):
        for change in ('expired','email','password','inactive'):
            with self.subTest(change=change):
                self.contractor.email='owner@example.com';self.contractor.active=True;db.session.commit()
                self.issue();row=Token.query.order_by(Token.id.desc()).first();link=self.link()
                if change=='expired': row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
                elif change=='email': self.contractor.email='changed@example.com'
                elif change=='password': self.contractor.password_hash='different-synthetic-hash'
                else: self.contractor.active=False
                db.session.commit()
                self.assertEqual(self.client.get(link).status_code,400)
                with patch('communications.resend_email') as send:
                    self.assertEqual(deliver_pending()['sent'],0);send.assert_not_called()

    def test_consumer_email_link_opens_only_matching_latest_request_after_confirmation(self):
        other=Lead(homeowner_name='Other Private Owner',email='other@example.com',phone='6125550111',zip_code='55101',service_needed='Roof Leak Repair',status='New')
        db.session.add(other);db.session.commit()
        self.issue('consumer');link=self.link('consumer');fresh=app.test_client()
        self.assertEqual(fresh.get(link).status_code,200)
        self.assertIn('No current request',fresh.get('/request-status').text)
        data=self.csrf(fresh)
        self.assertEqual(fresh.post(link,data=data).status_code,303)
        page=fresh.get('/request-status');self.assertIn('Mold Remediation',page.text)
        self.assertNotIn('Roof Leak Repair',page.text);self.assertNotIn('Private Owner',page.text)
        self.assertEqual(app.test_client().get(link).status_code,400)
        self.lead.email='changed@example.com';db.session.commit()
        self.assertIn('No current request',fresh.get('/request-status').text)

    def test_link_purposes_cannot_be_swapped_and_consumers_have_no_password_form(self):
        self.issue('consumer');link=self.link('consumer')
        self.assertNotIn('type="password"',self.client.get(link).text)
        self.assertEqual(self.client.get(link.replace('/request-access/','/contractor/reset-password/')).status_code,400)
        self.assertEqual(self.client.get('/request-access/'+('x'*43)).status_code,400)

    def test_token_and_notice_creation_roll_back_together(self):
        with patch('app.Delivery',side_effect=RuntimeError('synthetic queue failure')),self.assertLogs('app',level='ERROR'):
            self.assertIn(ACK,self.issue().text)
        self.assertEqual(Token.query.count(),0);self.assertEqual(Delivery.query.count(),0)

    def test_test_mode_does_not_issue_links_for_other_destinations(self):
        with patch.dict(os.environ,{'EMAIL_TEST_ONLY':'true','EMAIL_TEST_RECIPIENTS':'designated@example.com'}):
            self.assertIn(ACK,self.issue().text)
        self.assertEqual(Token.query.count(),0);self.assertEqual(Delivery.query.count(),0)

    def test_host_header_does_not_control_email_links_and_responses_are_private(self):
        evil=app.test_client()
        form=evil.get('/contractor/forgot-password',base_url='https://untrusted.example')
        csrf=re.search(r'name="_csrf" value="([^"]+)"',form.text).group(1)
        response=evil.post('/contractor/forgot-password',base_url='https://untrusted.example',
            data={'_csrf':csrf,'email':'owner@example.com'})
        self.assertEqual(response.status_code,303)
        self.assertNotIn('untrusted.example',Delivery.query.one().body)
        for path in ('/contractor/forgot-password','/request-access',self.link()):
            response=self.client.get(path)
            self.assertIn('no-store',response.headers['Cache-Control'])
            self.assertEqual(response.headers['Referrer-Policy'],'no-referrer')

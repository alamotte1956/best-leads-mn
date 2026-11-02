import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import base64
import hashlib
import hmac
import io
import json
import time
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from app import app, db, Delivery, ResendEvent, EmailSuppression
from communications import deliver_pending, queue_email
from email_delivery import verify_signature

TEST_KEY = b'resend-webhook-test-secret-only!!'
TEST_SECRET = 'whsec_' + base64.b64encode(TEST_KEY).decode()


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'RESEND_WEBHOOK_SECRET': TEST_SECRET, 'RESEND_API_KEY': 're_dummy',
            'RESEND_FROM_EMAIL': 'sender@example.com', 'EMAIL_SENDING_ENABLED': 'true',
            'SMS_SENDING_ENABLED': 'false', 'ADMIN_PASSWORD_HASH': 'test-admin-config',
        })
        self.env.start()
        self.ctx = app.app_context(); self.ctx.push()
        db.drop_all(); db.create_all()
        self.client = app.test_client()
        self.row = Delivery(event_key='test-receipt', channel='email', recipient='consumer@example.com',
            subject='Request received', body='Your request was saved.', status='sent', provider_id='email-test')
        db.session.add(self.row); db.session.commit()

    def tearDown(self):
        db.session.remove(); self.ctx.pop(); self.env.stop()

    def post(self, kind='email.delivered', identifier='msg_test', recipient='consumer@example.com',
             provider_id='email-test', tags=None, stamp=None, bounce=None, raw=None, client=None):
        data = {'email_id': provider_id, 'to': [recipient]}
        if tags is not None: data['tags'] = tags
        if bounce is not None: data['bounce'] = bounce
        payload = raw if raw is not None else json.dumps({
            'type': kind, 'created_at': datetime.now(timezone.utc).isoformat(), 'data': data}).encode()
        timestamp = str(int(time.time()) if stamp is None else stamp)
        signature = base64.b64encode(hmac.new(TEST_KEY,
            f'{identifier}.{timestamp}.'.encode() + payload, hashlib.sha256).digest()).decode()
        return (client or self.client).post('/webhooks/resend', data=payload, headers={
            'svix-id': identifier, 'svix-timestamp': timestamp, 'svix-signature': 'v1,'+signature},
            content_type='application/json')

    def test_official_svix_signature_vector_and_multiple_signatures(self):
        headers = {'svix-id': 'msg_loFOjxBNrRLzqYUf', 'svix-timestamp': '1731705121',
            'svix-signature': 'v1,invalid v2,ignored v1,rAvfW3dJ/X/qxhsaXPOyyCGmRKsaKWcsNccKXlIktD0='}
        payload = b'{"event_type":"ping","data":{"success":true}}'
        self.assertTrue(verify_signature(payload, headers, 'whsec_plJ3nmyCDGBKInavdOK15jsl', now=1731705121))
        self.assertFalse(verify_signature(payload+b' ', headers, 'whsec_plJ3nmyCDGBKInavdOK15jsl', now=1731705121))

    def test_rejects_forged_stale_future_and_unconfigured_requests(self):
        self.assertEqual(self.client.post('/webhooks/resend', json={}).status_code, 400)
        for offset in (-600, 600):
            self.assertEqual(self.post(stamp=int(time.time())+offset).status_code, 400)
        with patch.dict(os.environ, {'RESEND_WEBHOOK_SECRET': ''}):
            self.assertEqual(self.post().status_code, 503)
        self.assertEqual(ResendEvent.query.count(), 0)

    def test_delivery_and_duplicate_events_are_durable(self):
        self.assertEqual(self.post().status_code, 204)
        self.assertEqual(self.post().status_code, 204)
        db.session.refresh(self.row)
        self.assertEqual(self.row.status, 'delivered')
        self.assertEqual(ResendEvent.query.count(), 1)
        self.assertEqual(self.post('email.sent', identifier='msg_older').status_code, 204)
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'delivered')

    def test_hard_bounce_blocks_future_sends_case_insensitively(self):
        self.assertEqual(self.post('email.bounced', bounce={'type': 'Permanent'}).status_code, 204)
        self.assertEqual(EmailSuppression.query.one().email, 'consumer@example.com')
        queue_email('next-receipt', 'Consumer@Example.COM', 'Receipt', 'Saved'); db.session.commit()
        with patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['suppressed'], 1); send.assert_not_called()
        self.assertEqual(self.post(identifier='msg_late_delivery').status_code, 204)
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'bounced')
        self.assertEqual(EmailSuppression.query.count(), 1)

    def test_complaint_after_delivery_is_terminal(self):
        self.post()
        self.assertEqual(self.post('email.complained', identifier='msg_complaint').status_code, 204)
        self.assertEqual(self.post('email.failed', identifier='msg_late_failed').status_code, 204)
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'complained')
        self.assertEqual(EmailSuppression.query.one().reason, 'complained')

    def test_temporary_delay_does_not_permanently_suppress(self):
        self.assertEqual(self.post('email.bounced', bounce={'type': 'Temporary'}).status_code, 204)
        self.assertEqual(EmailSuppression.query.count(), 0)
        self.assertEqual(self.post(identifier='msg_delivered').status_code, 204)
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'delivered')

    def test_early_callback_survives_provider_send_response(self):
        self.row.provider_id = None; self.row.status = 'pending'; db.session.commit()
        def response(req, **kwargs):
            payload = json.loads(req.data)
            self.assertEqual(payload['tags'], [{'name':'delivery_id','value':str(self.row.id)}])
            self.assertEqual(self.post(tags={'delivery_id':str(self.row.id)}).status_code, 204)
            return io.BytesIO(b'{"id":"email-test"}')
        with patch('communications.urlopen', side_effect=response):
            self.assertEqual(deliver_pending()['sent'], 1)
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'delivered')

    def test_early_complaint_survives_provider_timeout(self):
        self.row.provider_id = None; self.row.status = 'pending'; db.session.commit()
        def response(req, **kwargs):
            self.assertEqual(self.post('email.complained', tags={'delivery_id':str(self.row.id)}).status_code, 204)
            raise TimeoutError()
        with patch('communications.urlopen', side_effect=response):
            deliver_pending()
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'complained')
        self.assertEqual(EmailSuppression.query.count(), 1)

    def test_mismatched_recipient_or_tag_cannot_mutate_delivery(self):
        self.assertEqual(self.post(recipient='unrelated@example.com').status_code, 400)
        self.assertEqual(self.post(tags={'delivery_id':'999'}).status_code, 400)
        self.assertEqual(ResendEvent.query.count(), 0)
        db.session.refresh(self.row); self.assertEqual(self.row.status, 'sent')

    def test_unknown_mail_and_unrelated_events_are_ignored(self):
        self.assertEqual(self.post(provider_id='another-app-email').status_code, 204)
        self.assertEqual(self.post('email.opened').status_code, 204)
        self.assertEqual(ResendEvent.query.count(), 0)

    def test_provider_suppression_blocks_later_mail_but_failed_does_not(self):
        self.assertEqual(self.post('email.failed').status_code, 204)
        self.assertEqual(EmailSuppression.query.count(), 0)
        self.assertEqual(self.post('email.suppressed', identifier='msg_suppression').status_code, 204)
        self.assertEqual(EmailSuppression.query.count(), 1)

    def test_invalid_payload_and_size_are_rejected(self):
        for payload in (b'[]', b'{', b'{"type":"email.delivered","data":null}', b'null'):
            self.assertEqual(self.post(raw=payload).status_code, 400)
        self.assertEqual(self.post(raw=b'x'*262145).status_code, 413)

    def test_admin_tracking_is_protected_and_secrets_hidden(self):
        self.post('email.complained')
        self.assertEqual(self.client.get('/admin/integrations').status_code, 403)
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as state:
            state.update(admin_authenticated=True, admin_login_at=time.time()-1,
                         admin_password_fingerprint=current_password_fingerprint())
        page = self.client.get('/admin/integrations')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Blocked email addresses', page.text)
        self.assertIn('consumer@example.com', page.text)
        self.assertNotIn(TEST_SECRET, page.text)

    def test_concurrent_callbacks_deduplicate_and_preserve_complaint(self):
        from flask import Flask
        from email_delivery import email_delivery
        with tempfile.TemporaryDirectory() as directory:
            isolated = Flask('concurrent-email-test')
            isolated.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///'+directory.replace('\\','/')+'/email.db',
                                  SQLALCHEMY_ENGINE_OPTIONS={'connect_args':{'timeout':30}})
            db.init_app(isolated)
            isolated.register_blueprint(email_delivery)
            with isolated.app_context():
                db.create_all()
                db.session.add(Delivery(event_key='parallel-mail',channel='email',recipient='consumer@example.com',
                    subject='Receipt',body='Saved',status='sent',provider_id='email-test'))
                db.session.commit()
            events = ['email.sent','email.delivered','email.bounced','email.complained']*2
            def deliver(kind):
                with isolated.test_client() as client:
                    return self.post(kind,identifier='msg_parallel_'+kind.split('.')[1],
                        bounce={'type':'Permanent'},client=client).status_code
            with ThreadPoolExecutor(max_workers=4) as workers:
                self.assertEqual(list(workers.map(deliver,events)),[204]*8)
            with isolated.app_context():
                self.assertEqual(Delivery.query.one().status,'complained')
                self.assertEqual(EmailSuppression.query.count(),1)
                self.assertEqual(ResendEvent.query.count(),4)
                db.session.remove();db.engine.dispose()


if __name__ == '__main__':
    unittest.main()

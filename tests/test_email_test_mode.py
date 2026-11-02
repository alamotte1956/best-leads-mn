"""Temporary recipient restrictions must not reroute or release real customer mail."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import io
import json
import unittest
from unittest.mock import patch
from app import app, db, Delivery
from communications import deliver_pending, queue_email, resend_email


class EmailTestModeTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context(); self.ctx.push(); db.drop_all(); db.create_all()
        self.env = patch.dict(os.environ, {
            'EMAIL_SENDING_ENABLED': 'true', 'RESEND_API_KEY': 're_synthetic',
            'RESEND_FROM_EMAIL': 'sender@example.com', 'SMS_SENDING_ENABLED': 'false',
            'EMAIL_TEST_ONLY': 'true',
            'EMAIL_TEST_RECIPIENTS': 'consumer@example.com,contractor@example.com',
        }); self.env.start()

    def tearDown(self):
        db.session.remove(); self.ctx.pop(); self.env.stop()

    def test_blocked_backlog_does_not_starve_allowed_email_or_reroute_customer_mail(self):
        for i in range(25):
            queue_email(f'customer:{i}', 'other@example.com', 'Receipt', 'Private request')
        db.session.flush()
        queue_email('consumer', 'Consumer@Example.COM', 'Receipt', 'Request saved')
        queue_email('contractor', 'contractor@example.com', 'Receipt', 'Application saved')
        db.session.commit()
        with patch('communications.resend_email', side_effect=['provider-consumer','provider-contractor']) as send:
            result = deliver_pending(limit=2)
            self.assertEqual(result['sent'], 2); self.assertEqual(result['disabled'], 25)
            self.assertEqual([c.args[0].recipient for c in send.call_args_list],
                             ['Consumer@Example.COM', 'contractor@example.com'])
        self.assertEqual(Delivery.query.filter_by(recipient='other@example.com',status='pending').count(),25)

    def test_empty_or_malformed_allowlist_fails_closed(self):
        queue_email('receipt','consumer@example.com','Receipt','Saved'); db.session.commit()
        for value in ('', 'consumer@example.com,', 'invalid', 'Name <consumer@example.com>'):
            with self.subTest(value=value), patch.dict(os.environ, {'EMAIL_TEST_RECIPIENTS': value}), patch('communications.resend_email') as send:
                self.assertEqual(deliver_pending()['sent'],0); send.assert_not_called()
                self.assertEqual(Delivery.query.one().status,'pending')

    def test_direct_provider_send_rejects_blocked_recipient_before_network(self):
        row = Delivery(event_key='direct', channel='email',recipient='other@example.com',subject='Receipt',body='Private')
        with patch('communications.urlopen') as network:
            with self.assertRaises(ValueError): resend_email(row)
            network.assert_not_called()

    def test_provider_payload_marks_test_without_altering_saved_content(self):
        row=Delivery(id=7,event_key='payload',channel='email',recipient='consumer@example.com',subject='Receipt',body='Saved')
        with patch('communications.urlopen',return_value=io.BytesIO(b'{"id":"synthetic"}')) as network:
            self.assertEqual(resend_email(row),'synthetic')
        data=json.loads(network.call_args.args[0].data)
        headers={name.lower():value for name,value in network.call_args.args[0].header_items()}
        self.assertEqual(headers['accept'],'application/json')
        self.assertEqual(headers['user-agent'],
            'RestorationContractorsMN/1.0 (+https://www.restorationcontractorsmn.com)')
        self.assertEqual(headers['idempotency-key'],'payload')
        self.assertEqual(data['to'],['consumer@example.com'])
        self.assertEqual(data['subject'],'[TEST] Receipt')
        self.assertTrue(data['text'].startswith('TEST MESSAGE:'))
        self.assertEqual((row.subject,row.body),('Receipt','Saved'))

    def test_allowlist_change_after_claim_returns_message_to_pending(self):
        queue_email('receipt','consumer@example.com','Receipt','Saved'); db.session.commit()
        calls=[]
        def check(_):
            calls.append(1)
            if len(calls)==2: os.environ['EMAIL_TEST_RECIPIENTS']='contractor@example.com'
            return False
        with patch('email_delivery.email_suppressed',side_effect=check),patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['disabled'],1); send.assert_not_called()
        self.assertEqual(Delivery.query.one().status,'pending')

    def test_normal_mode_retains_original_recipients_and_subject(self):
        row=Delivery(id=8,event_key='normal',channel='email',recipient='other@example.com',subject='Receipt',body='Saved')
        with patch.dict(os.environ,{'EMAIL_TEST_ONLY':'false'}),patch('communications.urlopen',return_value=io.BytesIO(b'{"id":"synthetic"}')) as network:
            resend_email(row)
        data=json.loads(network.call_args.args[0].data)
        self.assertEqual((data['to'],data['subject'],data['text']),(['other@example.com'],'Receipt','Saved'))

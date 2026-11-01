import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import unittest
from unittest.mock import patch
from app import app,db,Delivery
from communications import deliver_pending,queue_email


class EmailOnlyDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.env=patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'true','RESEND_API_KEY':'re_synthetic',
            'RESEND_FROM_EMAIL':'sender@example.com','SMS_SENDING_ENABLED':'false'})
        self.env.start()

    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()

    def test_disabled_sms_backlog_cannot_starve_consumer_or_contractor_email(self):
        db.session.add_all(Delivery(event_key='sms:'+str(i),channel='sms',recipient='6125550100',
            subject='Old SMS',body='Synthetic') for i in range(35))
        db.session.flush()
        queue_email('consumer:received','consumer@example.com','Consumer receipt','Request received')
        queue_email('contractor:received','contractor@example.com','Application receipt','Application received')
        db.session.commit()
        with patch('communications.resend_email',side_effect=['email-consumer','email-contractor']) as email,patch('communications.twilio_sms') as sms:
            result=deliver_pending(limit=2)
            self.assertEqual(result['sent'],2);self.assertEqual(result['disabled'],35)
            self.assertEqual(email.call_count,2);sms.assert_not_called()
        self.assertEqual(Delivery.query.filter_by(channel='sms',status='pending').count(),35)

    def test_unconfigured_enabled_sms_and_unknown_channel_also_cannot_starve_email(self):
        db.session.add(Delivery(event_key='unconfigured:sms',channel='sms',recipient='6125550100',subject='SMS',body='Synthetic'))
        db.session.add(Delivery(event_key='unknown:channel',channel='other',recipient='none',subject='Unknown',body='Synthetic'))
        db.session.flush();queue_email('email:ready','consumer@example.com','Receipt','Received');db.session.commit()
        with patch.dict(os.environ,{'SMS_SENDING_ENABLED':'true','TWILIO_ACCOUNT_SID':'','TWILIO_AUTH_TOKEN':''}),patch(
                'communications.resend_email',return_value='email-ready'),patch('communications.twilio_sms') as sms:
            result=deliver_pending(limit=1);self.assertEqual(result['sent'],1);self.assertEqual(result['disabled'],2);sms.assert_not_called()

    def test_disabled_email_does_not_send_or_consume_delivery(self):
        queue_email('email:off','consumer@example.com','Receipt','Received');db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'false'}),patch('communications.resend_email') as email:
            result=deliver_pending();self.assertEqual(result['sent'],0);self.assertEqual(result['disabled'],1);email.assert_not_called()
        self.assertEqual(Delivery.query.one().status,'pending')

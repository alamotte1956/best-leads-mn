import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import app, db, Contractor, Lead, LeadOffer, Delivery, NotificationPreference, NotificationPreferenceEvent
from contractor_session_security import create_contractor_session_data
from communications import queue_offer, queue_email, deliver_pending


class NotificationPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-admin',
            'EMAIL_SENDING_ENABLED':'true','RESEND_API_KEY':'re_dummy','RESEND_FROM_EMAIL':'sender@example.com',
            'SMS_SENDING_ENABLED':'true','TWILIO_ACCOUNT_SID':'ACdummy','TWILIO_AUTH_TOKEN':'dummy',
            'TWILIO_MESSAGING_SERVICE_SID':'MGdummy','TWILIO_STATUS_WEBHOOK_URL':'https://example.com/status'})
        self.env.start();self.ctx=app.app_context();self.ctx.push()
        db.drop_all();db.create_all();self.client=app.test_client()
        self.contractor=Contractor(company_name='Restoration Company',contact_name='Owner',email='owner@example.com',
            phone='6125550100',zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,
            password_hash='synthetic-hash',sms_consent=True,sms_consent_at=datetime.now(timezone.utc),sms_consent_method='synthetic-opt-in')
        db.session.add(self.contractor);db.session.commit();self.owner()

    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()

    def owner(self):
        with self.client.session_transaction() as state:
            state.clear();state.update(create_contractor_session_data(self.contractor.id))
            state.update(_csrf='alerts-csrf',contractor_password_fingerprint=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest())

    def data(self,email=False,sms=False,version=0,**extra):
        data={'_csrf':'alerts-csrf','version':str(version)}
        if email:data['lead_email']='yes'
        if sms:data['lead_sms']='yes'
        data.update(extra);return data

    def offer(self):
        lead=Lead(homeowner_name='Synthetic',phone='6125550199',zip_code='55401',service_needed='Mold Remediation',status='New')
        db.session.add(lead);db.session.flush()
        offer=LeadOffer(lead_id=lead.id,contractor_id=self.contractor.id,status='pending',
            offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer);db.session.commit();return offer

    def test_defaults_preserve_alert_queue_behavior(self):
        from notification_preferences import current_choices
        self.assertEqual(current_choices(self.contractor.id),{'lead_email':True,'lead_sms':True,'version':0})
        offer=self.offer();queue_offer(offer,self.contractor);db.session.commit()
        self.assertEqual({row.channel for row in Delivery.query.all()},{'email','sms'})
        self.assertIn('no-store',self.client.get('/contractor/notifications').headers['Cache-Control'])

    def test_pausing_stops_queued_alerts_but_retains_offers_and_other_email(self):
        offer=self.offer();queue_offer(offer,self.contractor)
        queue_email('account-notice','owner@example.com','Account update','Your account record was updated.')
        db.session.commit()
        self.assertEqual(self.client.post('/contractor/notifications',data=self.data()).status_code,303)
        self.assertEqual(Delivery.query.filter_by(status='suppressed').count(),2)
        db.session.refresh(offer);self.assertEqual(offer.status,'pending')
        db.session.refresh(self.contractor);self.assertTrue(self.contractor.active);self.assertTrue(self.contractor.verified)
        self.assertEqual(NotificationPreferenceEvent.query.count(),1)
        with patch('communications.resend_email',return_value='account-email') as send,patch('communications.twilio_sms') as sms:
            self.assertEqual(deliver_pending()['sent'],1)
            self.assertEqual(send.call_args.args[0].subject,'Account update');sms.assert_not_called()

    def test_email_and_sms_choices_are_independent(self):
        self.client.post('/contractor/notifications',data=self.data(sms=True))
        offer=self.offer();queue_offer(offer,self.contractor);db.session.commit()
        self.assertEqual(Delivery.query.one().channel,'sms')
        with patch('communications.twilio_sms',return_value='SMalert') as sms,patch('communications.resend_email') as email:
            self.assertEqual(deliver_pending()['sent'],1);self.assertEqual(sms.call_count,1);email.assert_not_called()

    def test_resume_applies_to_future_offers_without_replaying_suppressed_alerts(self):
        queue_offer(self.offer(),self.contractor);db.session.commit()
        self.client.post('/contractor/notifications',data=self.data())
        self.client.post('/contractor/notifications',data=self.data(email=True,sms=True,version=1))
        self.assertEqual(Delivery.query.filter_by(status='suppressed').count(),2)
        queue_offer(self.offer(),self.contractor);db.session.commit()
        self.assertEqual(Delivery.query.filter_by(status='pending').count(),2)
        with patch('communications.resend_email',return_value='fresh-email'),patch('communications.twilio_sms',return_value='SMfresh'):
            self.assertEqual(deliver_pending()['sent'],2)
        self.assertEqual(Delivery.query.filter_by(status='suppressed').count(),2)

    def test_stale_form_cannot_overwrite_newer_choices_and_replay_is_safe(self):
        self.assertEqual(self.client.post('/contractor/notifications',data=self.data()).status_code,303)
        self.assertEqual(self.client.post('/contractor/notifications',data=self.data()).status_code,303)
        self.assertEqual(NotificationPreferenceEvent.query.count(),1)
        response=self.client.post('/contractor/notifications',data=self.data(email=True,sms=True))
        self.assertEqual(response.status_code,409)
        self.assertIn('current choices',response.text)
        row=NotificationPreference.query.one();self.assertFalse(row.lead_email);self.assertFalse(row.lead_sms)
        self.assertEqual(row.version,1)

    def test_cannot_change_another_account_or_bypass_csrf_and_approval(self):
        self.assertEqual(self.client.post('/contractor/notifications',data={'version':'0'}).status_code,400)
        self.client.post('/contractor/notifications',data=self.data(contractor_id='999'))
        self.assertEqual(NotificationPreference.query.one().contractor_id,self.contractor.id)
        self.contractor.active=False;db.session.commit()
        self.assertEqual(self.client.post('/contractor/notifications',data=self.data(email=True,version=1)).status_code,302)
        self.assertFalse(NotificationPreference.query.one().lead_email)

    def test_alert_choice_does_not_grant_sms_consent(self):
        self.contractor.sms_consent=False;self.contractor.sms_consent_at=None;self.contractor.sms_consent_method=None;db.session.commit()
        self.client.post('/contractor/notifications',data=self.data(email=True,sms=True,sms_consent='yes'))
        queue_offer(self.offer(),self.contractor);db.session.commit()
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'false'}),patch('communications.twilio_sms') as send:
            self.assertEqual(deliver_pending()['suppressed'],1);send.assert_not_called()
        db.session.refresh(self.contractor);self.assertFalse(self.contractor.sms_consent)

    def test_delivery_blocks_and_stop_records_survive_preferences_changes(self):
        from app import ResendEvent,EmailSuppression,SmsSuppression
        row=Delivery(event_key='block-source',channel='email',recipient=self.contractor.email,
            subject='Synthetic',body='Synthetic',status='bounced',provider_id='blocked-email')
        db.session.add(row);db.session.flush()
        db.session.add(ResendEvent(id='block-event',delivery_id=row.id,provider_id='blocked-email',
            event_type='email.bounced',occurred_at=datetime.now(timezone.utc)));db.session.flush()
        db.session.add(EmailSuppression(email=self.contractor.email,reason='bounced',source_event_id='block-event'))
        db.session.add(SmsSuppression(phone_normalized='6125550100',opted_out_at=datetime.now(timezone.utc)))
        db.session.commit()
        self.client.post('/contractor/notifications',data=self.data())
        self.client.post('/contractor/notifications',data=self.data(email=True,sms=True,version=1))
        queue_offer(self.offer(),self.contractor);db.session.commit()
        with patch('communications.resend_email') as email,patch('communications.twilio_sms') as sms:
            self.assertEqual(deliver_pending()['suppressed'],2);email.assert_not_called();sms.assert_not_called()
        self.assertEqual(EmailSuppression.query.count(),1);self.assertEqual(SmsSuppression.query.count(),1)

    def test_preference_update_failure_rolls_back_alert_suppression_and_history(self):
        queue_offer(self.offer(),self.contractor);db.session.commit()
        with patch.object(db.session,'commit',side_effect=RuntimeError('synthetic failure')),self.assertLogs('app',level='ERROR'):
            response=self.client.post('/contractor/notifications',data=self.data())
        self.assertEqual(response.status_code,500)
        self.assertEqual(NotificationPreference.query.count(),0)
        self.assertEqual(NotificationPreferenceEvent.query.count(),0)
        self.assertEqual(Delivery.query.filter_by(status='pending').count(),2)

    def test_worker_rechecks_a_pause_after_claiming_an_alert(self):
        from notification_preferences import lead_alert_enabled
        offer=self.offer()
        db.session.add(Delivery(event_key='race-email',channel='email',recipient=self.contractor.email,
            contractor_id=self.contractor.id,offer_id=offer.id,subject='Offer',body='Review your dashboard'))
        db.session.commit();calls=[]
        def interleave(identifier,channel):
            calls.append(channel)
            if len(calls)==2:
                self.assertEqual(self.client.post('/contractor/notifications',data=self.data(sms=True)).status_code,303)
            return lead_alert_enabled(identifier,channel)
        with patch('notification_preferences.lead_alert_enabled',side_effect=interleave),patch('communications.resend_email') as send:
            self.assertEqual(deliver_pending()['suppressed'],1);send.assert_not_called()
        self.assertEqual(Delivery.query.one().status,'suppressed')

    def test_administrator_inspection_is_read_only_and_owner_scoped(self):
        self.client.post('/contractor/notifications',data=self.data())
        path=f'/admin/contractors/{self.contractor.id}/notifications'
        self.assertEqual(self.client.get(path).status_code,302)
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as state:
            state.clear();state.update(admin_authenticated=True,admin_login_at=time.time()-1,
                                      admin_password_fingerprint=current_password_fingerprint())
        page=self.client.get(path);self.assertEqual(page.status_code,200)
        self.assertIn('Read-only view',page.text);self.assertIn('Email paused',page.text)
        self.assertEqual(self.client.post(path,data=self.data(email=True,sms=True)).status_code,405)
        self.assertFalse(NotificationPreference.query.one().lead_email)

    def test_legacy_sms_dispatch_also_respects_paused_alerts(self):
        from app import contractor_sms_eligible
        from sms_sender import dispatch_contractor_sms
        from unittest.mock import Mock
        self.client.post('/contractor/notifications',data=self.data(email=True))
        self.assertFalse(contractor_sms_eligible(self.contractor))
        self.assertTrue(contractor_sms_eligible(self.contractor,include_preferences=False))
        send=Mock()
        result=dispatch_contractor_sms(self.contractor.id,'55401','Mold Remediation','Synthetic alert',
            lambda identifier:db.session.get(Contractor,identifier),contractor_sms_eligible,send)
        self.assertEqual(result['status'],'blocked');send.assert_not_called()
        db.session.refresh(self.contractor);self.assertTrue(self.contractor.sms_consent)


if __name__=='__main__':unittest.main()

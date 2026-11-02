import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from app import app,db,Contractor,Lead,LeadOffer,ContractorLeadProgress as Progress,LeadProgressEvent,Payment,Delivery,ConsumerRequestUpdate
from contractor_session_security import create_contractor_session_data


class LeadProgressTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-admin'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.client=app.test_client()
        self.contractor=Contractor(company_name='Restoration Business',contact_name='Owner',email='owner@example.com',
            phone='6125550100',zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,password_hash='synthetic-hash')
        db.session.add(self.contractor);db.session.commit()
        self.lead,self.offer=self.add_offer('Primary Homeowner');self.owner()

    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()

    def add_offer(self,name,status='accepted',contractor_id=None):
        lead=Lead(homeowner_name=name,phone='6125550199',email='consumer@example.com',zip_code='55401',service_needed='Mold Remediation',status='New')
        db.session.add(lead);db.session.flush()
        offer=LeadOffer(lead_id=lead.id,contractor_id=contractor_id or self.contractor.id,status=status,
            offered_at=datetime.now(timezone.utc)-timedelta(minutes=1),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer);db.session.commit();return lead,offer

    def owner(self):
        with self.client.session_transaction() as state:
            state.clear();state.update(create_contractor_session_data(self.contractor.id))
            state.update(_csrf='progress-csrf',contractor_password_fingerprint=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest())

    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as state:
            state.clear();state.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint())

    def data(self,**extra):
        data={'_csrf':'progress-csrf','version':'0','stage':'contacted','next_follow_up':'2026-11-02','note':'Follow up after the estimate.'}
        data.update(extra);return data

    def save(self,**extra):
        return self.client.post(f'/contractor/offers/{self.offer.id}/follow-up',data=self.data(**extra))

    def test_owner_can_save_audited_progress_without_fulfillment_side_effects(self):
        self.assertEqual(self.save(contractor_id='999').status_code,303)
        row=Progress.query.one();event=LeadProgressEvent.query.one()
        self.assertEqual((row.stage,row.next_follow_up,row.version),('contacted',date(2026,11,2),1))
        self.assertEqual(event.contractor_id,self.contractor.id)
        db.session.refresh(self.lead);db.session.refresh(self.offer)
        self.assertEqual((self.lead.status,self.offer.status),('New','accepted'))
        self.assertEqual((Payment.query.count(),Delivery.query.count(),ConsumerRequestUpdate.query.count()),(0,0,0))
        self.assertIn('no-store',self.client.get(f'/contractor/offers/{self.offer.id}/follow-up').headers['Cache-Control'])

    def test_pending_and_declined_offers_cannot_expose_or_record_progress(self):
        for status in ('pending','declined'):
            lead,offer=self.add_offer('PRIVATE UNACCEPTED',status)
            path=f'/contractor/offers/{offer.id}/follow-up'
            page=self.client.get(path)
            self.assertEqual(page.status_code,404);self.assertNotIn('PRIVATE UNACCEPTED',page.text)
            self.assertEqual(self.client.post(path,data=self.data()).status_code,404)
        self.assertEqual(Progress.query.count(),0)

    def test_other_contractors_offer_is_not_accessible_by_id(self):
        other=Contractor(company_name='Other Business',contact_name='Other',email='other@example.com',phone='6125550111',zip_codes='55401')
        db.session.add(other);db.session.commit()
        lead,offer=self.add_offer('OTHER PRIVATE HOMEOWNER',contractor_id=other.id)
        path=f'/contractor/offers/{offer.id}/follow-up'
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.post(path,data=self.data(contractor_id=str(other.id))).status_code,404)
        self.assertNotIn('OTHER PRIVATE HOMEOWNER',self.client.get('/contractor/leads').text)

    def test_csrf_and_active_approval_are_required(self):
        self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/follow-up',data={'stage':'contacted'}).status_code,400)
        self.contractor.active=False;db.session.commit()
        self.assertEqual(self.save().status_code,302)
        self.assertEqual(self.client.get('/contractor/leads').status_code,302)
        self.assertEqual(Progress.query.count(),0)

    def test_invalid_fields_preserve_draft_without_saving(self):
        for fields in ({'stage':'invalid'},{'next_follow_up':'2026-02-30'},{'version':'bad'}):
            response=self.save(note='KEEP MY DRAFT',**fields)
            self.assertEqual(response.status_code,400);self.assertIn('KEEP MY DRAFT',response.text)
        self.assertEqual(self.save(note='x'*2001).status_code,400)
        self.assertEqual(Progress.query.count(),0)

    def test_replay_is_idempotent_and_stale_edits_preserve_latest_and_draft(self):
        for _ in range(2):self.assertEqual(self.save(note='SAVED NOTE').status_code,303)
        self.assertEqual(LeadProgressEvent.query.count(),1)
        response=self.save(stage='estimate_sent',note='UNSAVED DRAFT')
        self.assertEqual(response.status_code,409)
        self.assertIn('SAVED NOTE',response.text);self.assertIn('UNSAVED DRAFT',response.text)
        self.assertEqual(Progress.query.one().stage,'contacted')
        self.assertEqual(self.save(stage='estimate_sent',note='Reviewed update',version='1').status_code,303)
        self.assertEqual(LeadProgressEvent.query.count(),2)

    def test_admin_inspection_is_read_only_and_notes_are_escaped(self):
        self.save(note='<script>private-report</script>')
        path=f'/admin/offers/{self.offer.id}/follow-up'
        self.assertEqual(self.client.get(path).status_code,403)
        self.admin();page=self.client.get(path)
        self.assertEqual(page.status_code,200)
        self.assertIn('Read-only administrator view',page.text)
        self.assertNotIn('<script>private-report</script>',page.text)
        self.assertIn('&lt;script&gt;private-report&lt;/script&gt;',page.text)
        self.assertEqual(self.client.post(path,data=self.data()).status_code,405)
        self.assertIn('Contractor-reported follow-up',self.client.get(f'/admin/leads/{self.lead.id}').text)

    def test_stage_and_due_filters_include_untracked_accepted_leads(self):
        self.save(next_follow_up='2026-10-31')
        future,future_offer=self.add_offer('Future Homeowner')
        db.session.add(Progress(offer_id=future_offer.id,contractor_id=self.contractor.id,stage='estimate_sent',next_follow_up=date(2026,11,3),note='',version=1))
        untracked,_=self.add_offer('Untracked Homeowner');db.session.commit()
        with patch('lead_progress.followup_today',return_value=date(2026,11,1)):
            overdue=self.client.get('/contractor/leads?due=overdue').text
            self.assertIn('Primary Homeowner',overdue);self.assertNotIn('Future Homeowner',overdue)
            upcoming=self.client.get('/contractor/leads?due=upcoming').text
            self.assertIn('Future Homeowner',upcoming);self.assertNotIn('Primary Homeowner',upcoming)
            new=self.client.get('/contractor/leads?stage=new').text
            self.assertIn('Untracked Homeowner',new);self.assertNotIn('Primary Homeowner',new)

    def test_pipeline_is_paginated_and_rejects_invalid_filters(self):
        for index in range(21):self.add_offer('Paged Homeowner '+str(index))
        first=self.client.get('/contractor/leads');second=self.client.get('/contractor/leads?page=2')
        self.assertIn('Page 1 of 2',first.text);self.assertIn('Page 2 of 2',second.text)
        self.assertEqual(first.text.count('Open contact and follow-up'),20)
        for query in ('stage=invalid','due=invalid','page=0','page=-1','page=abc'):
            self.assertEqual(self.client.get('/contractor/leads?'+query).status_code,400)

    def test_failed_save_rolls_back_current_record_and_event(self):
        with patch.object(db.session,'commit',side_effect=RuntimeError('synthetic failure')),self.assertLogs('app',level='ERROR'):
            response=self.save()
        self.assertEqual(response.status_code,500)
        self.assertEqual(Progress.query.count(),0);self.assertEqual(LeadProgressEvent.query.count(),0)

    def test_accepted_history_can_be_logged_after_matching_stops_without_reopening(self):
        self.lead.status='Cancelled';db.session.commit()
        self.assertEqual(self.save(stage='not_proceeding',next_follow_up='').status_code,303)
        db.session.refresh(self.lead);self.assertEqual(self.lead.status,'Cancelled')
        self.assertEqual(ConsumerRequestUpdate.query.count(),0)

    def test_reported_completion_and_notes_are_not_consumer_status_or_notifications(self):
        self.save(stage='completed',note='PRIVATE FOLLOWUP NOTE',next_follow_up='')
        with self.client.session_transaction() as state:
            state.update(last_lead_reference=self.lead.id,last_lead_status_at=datetime.now(timezone.utc).isoformat())
        page=self.client.get('/request-status')
        self.assertIn('A contractor accepted your request',page.text)
        self.assertNotIn('PRIVATE FOLLOWUP NOTE',page.text)
        self.assertEqual((Delivery.query.count(),Payment.query.count()),(0,0))

    def test_unchanged_empty_form_does_not_create_a_report(self):
        self.assertEqual(self.save(stage='new',note='',next_follow_up='').status_code,303)
        self.assertEqual((Progress.query.count(),LeadProgressEvent.query.count()),(0,0))

    def test_email_contact_links_cannot_add_mail_headers(self):
        self.lead.email='person@example.com?bcc=other%40example.com';db.session.commit()
        page=self.client.get(f'/contractor/offers/{self.offer.id}/follow-up')
        self.assertIn('href="mailto:person@example.com%3Fbcc%3Dother%2540example.com"',page.text)
        self.assertNotIn('href="mailto:person@example.com?bcc=',page.text)
        self.contractor.email='business@example.com?subject=unexpected';db.session.commit()
        with self.client.session_transaction() as state:
            state.update(last_lead_reference=self.lead.id,last_lead_status_at=datetime.now(timezone.utc).isoformat())
        page=self.client.get('/request-status')
        self.assertIn('href="mailto:business@example.com%3Fsubject%3Dunexpected"',page.text)

    def test_contact_link_helper_rejects_controls_and_encodes_plus_addresses(self):
        from contact_links import mailto_address
        self.assertEqual(mailto_address('owner+restoration@example.com'),'mailto:owner%2Brestoration@example.com')
        self.assertIsNone(mailto_address('owner@example.com\r\nbcc:other@example.com'))
        self.assertIsNone(mailto_address(None))

    def test_concurrent_edits_keep_one_version_and_report_conflicts(self):
        from flask import Flask
        from lead_progress import lead_progress
        with tempfile.TemporaryDirectory() as directory:
            isolated=Flask('followup-concurrency',template_folder=os.path.join(app.root_path,'templates'))
            isolated.config.update(SECRET_KEY='synthetic-isolated',SQLALCHEMY_DATABASE_URI='sqlite:///'+directory.replace('\\','/')+'/progress.db',
                SQLALCHEMY_ENGINE_OPTIONS={'connect_args':{'timeout':30}})
            isolated.jinja_env.globals['csrf_token']=app.jinja_env.globals['csrf_token']
            db.init_app(isolated);isolated.register_blueprint(lead_progress)
            try:
                with isolated.app_context():
                    db.create_all()
                    contractor=Contractor(company_name='Synthetic',contact_name='Owner',email='isolated@example.com',phone='6125550100',zip_codes='55401',active=True,verified=True,is_test=False,password_hash='synthetic-hash')
                    lead=Lead(homeowner_name='Synthetic',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
                    db.session.add_all([contractor,lead]);db.session.flush()
                    offer=LeadOffer(contractor_id=contractor.id,lead_id=lead.id,status='accepted',expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
                    db.session.add(offer);db.session.commit();identifier=contractor.id;offer_id=offer.id
                def save(index):
                    with isolated.test_client() as client:
                        with client.session_transaction() as state:
                            state.update(create_contractor_session_data(identifier))
                            state.update(_csrf='parallel-csrf',contractor_password_fingerprint=hashlib.sha256(b'synthetic-hash').hexdigest())
                        return client.post(f'/contractor/offers/{offer_id}/follow-up',data={
                            '_csrf':'parallel-csrf','version':'0','stage':'contacted','note':'Draft '+str(index)}).status_code
                with ThreadPoolExecutor(max_workers=4) as workers:codes=list(workers.map(save,range(4)))
                self.assertEqual(codes.count(303),1);self.assertEqual(codes.count(409),3)
                with isolated.app_context():
                    self.assertEqual(Progress.query.one().version,1);self.assertEqual(LeadProgressEvent.query.count(),1)
            finally:
                with isolated.app_context():db.session.remove();db.engine.dispose()


if __name__=='__main__':unittest.main()

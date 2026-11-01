import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import time
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import app,db,Contractor,RewardIdentityApplication,RewardIdentityReview,RewardBusinessAccount,RewardBusiness,RewardCredit,RewardSpin,RewardMonth,Delivery
from contractor_session_security import create_contractor_session_data
from reward_review import current_business,identity_digest


class RewardReviewTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-admin','EMAIL_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.client=app.test_client();self.contractor=self.new_contractor('owner@example.com');self.owner()

    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()

    def new_contractor(self,email):
        c=Contractor(company_name='Synthetic Business',contact_name='Owner',email=email,phone='6125550100',
            zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,password_hash='synthetic-hash')
        db.session.add(c);db.session.commit();return c

    def owner(self):
        with self.client.session_transaction() as s:
            s.clear();s.update(create_contractor_session_data(self.contractor.id));s['_csrf']='reward-csrf'
            s['contractor_password_fingerprint']=hashlib.sha256(self.contractor.password_hash.encode()).hexdigest()

    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as s:
            s.clear();s.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint(),_csrf='reward-csrf')

    def submit(self,**extra):
        data=dict(_csrf='reward-csrf',legal_name='Synthetic Legal Business',jurisdiction='US-MN',
            registration_id='SYNTHETIC-123',notes='OWNER IDENTITY NOTES',identity_review='yes')
        data.update(extra);return self.client.post('/contractor/rewards',data=data)

    def application(self):
        self.owner();self.assertEqual(self.submit().status_code,303)
        return RewardIdentityApplication.query.order_by(RewardIdentityApplication.id.desc()).first()

    def review(self,identifier,**extra):
        data=dict(_csrf='reward-csrf',decision='approved',canonical_jurisdiction='US-MN',
            canonical_registration_id='SYNTHETIC-123',evidence_reference='PRIVATE REGISTRY AND ACCOUNT EVIDENCE',
            verified_until=(datetime.now(timezone.utc)+timedelta(days=30)).date().isoformat(),private_notes='PRIVATE REVIEW NOTES',
            response_message='Your business identity was reviewed.',identity_checked='yes',duplicates_checked='yes')
        data.update(extra);return self.client.post(f'/admin/rewards/identity/{identifier}',data=data)

    def test_identity_approval_does_not_issue_rewards(self):
        row=self.application();self.admin();self.assertEqual(self.review(row.id).status_code,303)
        self.assertIsNotNone(current_business(self.contractor.id));self.assertEqual(RewardBusiness.query.count(),1)
        self.assertEqual(RewardCredit.query.count(),0);self.assertEqual(RewardSpin.query.count(),0)
        self.owner();page=self.client.get('/contractor/rewards')
        self.assertIn('Business identity review is current',page.text);self.assertIn('Rewards is not open.',page.text)
        self.assertIn('no-store',page.headers['Cache-Control'])

    def test_all_real_entry_paths_fail_closed_even_with_override_fields(self):
        for path in ('spin','free-entry','redeem'):
            self.assertEqual(self.client.post('/contractor/rewards/'+path,json={
                'business_id':1,'credit_id':1,'approved':True,'prize_index':7}).status_code,503)
        self.assertEqual(RewardCredit.query.count(),0);self.assertEqual(RewardSpin.query.count(),0)

    def test_owner_and_admin_boundaries_csrf_and_pending_deduplication(self):
        self.assertEqual(self.submit(_csrf='wrong').status_code,400)
        self.assertEqual(self.submit(contractor_id=999,status='approved').status_code,303)
        row=RewardIdentityApplication.query.one();self.assertEqual(row.contractor_id,self.contractor.id);self.assertEqual(row.status,'pending')
        self.assertEqual(self.submit().status_code,400);self.assertEqual(self.review(row.id).status_code,403)
        self.assertEqual(self.client.get('/admin/rewards').status_code,403)
        self.admin();self.assertEqual(self.review(row.id,_csrf='wrong').status_code,400)

    def test_approval_requires_evidence_duplicate_check_account_control_and_expiry(self):
        row=self.application();self.admin()
        for extra in ({'evidence_reference':''},{'identity_checked':'no'},{'duplicates_checked':'no'},
                      {'canonical_registration_id':''},{'canonical_jurisdiction':'MN'},
                      {'verified_until':'2000-01-01'},{'response_message':''},{'private_notes':''}):
            self.assertEqual(self.review(row.id,**extra).status_code,400,extra)
        self.assertEqual(RewardBusiness.query.count(),0);self.assertEqual(RewardIdentityReview.query.count(),0)

    def test_same_legal_business_cannot_gain_second_account_or_format_alias(self):
        row=self.application();self.admin();self.review(row.id)
        self.contractor=self.new_contractor('second@example.com');row=self.application();self.admin()
        self.assertEqual(self.review(row.id,canonical_registration_id='synthetic 123').status_code,400)
        self.assertEqual(RewardBusiness.query.count(),1);self.assertEqual(RewardBusinessAccount.query.count(),1)

    def test_identity_switch_cannot_reset_monthly_counter(self):
        row=self.application();self.admin();self.review(row.id)
        account=RewardBusinessAccount.query.one();business_id=account.business_id
        db.session.add(RewardMonth(business_id=business_id,month='2026-11',used=10))
        account.verified_until=datetime(2000,1,1).date();db.session.commit()
        row=self.application();self.admin()
        self.assertEqual(self.review(row.id,canonical_registration_id='DIFFERENT-ENTITY').status_code,400)
        self.assertEqual(self.review(row.id).status_code,303)
        self.assertEqual(RewardBusiness.query.count(),1);self.assertEqual(RewardBusinessAccount.query.one().business_id,business_id)
        self.assertEqual(db.session.get(RewardMonth,(business_id,'2026-11')).used,10)

    def test_expired_or_revoked_identity_and_account_fail_closed(self):
        row=self.application();self.admin();self.review(row.id)
        account=RewardBusinessAccount.query.one();account.verified_until=datetime(2000,1,1).date();db.session.commit()
        self.assertIsNone(current_business(self.contractor.id))
        account.verified_until=(datetime.now(timezone.utc)+timedelta(days=30)).date();self.contractor.active=False;db.session.commit()
        self.assertIsNone(current_business(self.contractor.id))
        self.contractor.active=True;RewardBusiness.query.one().verified=False;db.session.commit()
        self.assertIsNone(current_business(self.contractor.id))

    def test_private_evidence_isolated_and_duplicate_review_idempotence(self):
        row=self.application();self.admin();self.review(row.id)
        self.assertEqual(self.review(row.id).status_code,409);self.assertEqual(RewardIdentityReview.query.count(),1)
        self.owner();page=self.client.get('/contractor/rewards').text
        for text in ('PRIVATE REGISTRY AND ACCOUNT EVIDENCE','PRIVATE REVIEW NOTES'):
            self.assertNotIn(text,page);self.assertNotIn(text,Delivery.query.one().body)
        self.contractor=self.new_contractor('other@example.com');self.owner()
        self.assertNotIn('Synthetic Legal Business',self.client.get('/contractor/rewards').text)

    def test_review_outbox_failure_rolls_back_identity_and_link(self):
        row=self.application();self.admin()
        with app.test_request_context(f'/admin/rewards/identity/{row.id}',method='POST',data={
                '_csrf':'reward-csrf','decision':'rejected','private_notes':'Notes','response_message':'Review result'}):
            from flask import session
            from admin_session_security import current_password_fingerprint
            from reward_review import review_identity
            session.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint(),_csrf='reward-csrf')
            with patch('communications.queue_email',side_effect=RuntimeError('synthetic rollback')):
                with self.assertRaises(RuntimeError):review_identity(row.id)
        db.session.refresh(row);self.assertEqual(row.status,'pending');self.assertEqual(RewardIdentityReview.query.count(),0)
        self.assertEqual(RewardBusinessAccount.query.count(),0)

    def test_registry_id_validation_and_non_entry_disclosure(self):
        for changes in ({'jurisdiction':'MN'},{'registration_id':'<script>'},{'legal_name':''},{'identity_review':'no'}):
            self.assertEqual(self.submit(**changes).status_code,400)
        self.assertEqual(identity_digest('us-mn','Ab-123'),identity_digest('US-MN','AB 123'))
        self.assertEqual(RewardIdentityApplication.query.count(),0)

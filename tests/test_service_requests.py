import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import app, db, Contractor, ContractorService, CredentialReview, ServiceRequest, Delivery, Lead
from contractor_session_security import create_contractor_session_data
from contractor_matching import contractor_matches


class ServiceRequestTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-admin-config','EMAIL_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push()
        db.drop_all();db.create_all();self.client=app.test_client()
        self.contractor=Contractor(company_name='Restoration Company',contact_name='Owner',email='owner@example.com',
            phone='6125550100',zip_codes='55401',service_type='Mold Remediation',license_number='SYNTHETIC-LICENSE',
            active=True,verified=True,is_test=False,password_hash='synthetic-password-hash')
        db.session.add(self.contractor);db.session.flush()
        self.original=ContractorService(contractor_id=self.contractor.id,service_name='Flood Damage Restoration')
        db.session.add(self.original);db.session.commit()

    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()

    def owner(self, contractor=None):
        contractor=contractor or self.contractor
        with self.client.session_transaction() as state:
            state.clear();state.update(create_contractor_session_data(contractor.id))
            state['_csrf']='service-csrf'
            state['contractor_password_fingerprint']=hashlib.sha256(contractor.password_hash.encode()).hexdigest()

    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as state:
            state.clear();state.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint(),_csrf='service-csrf')

    def submit(self, **extra):
        data={'_csrf':'service-csrf','service_name':'Fire Damage Restoration','contractor_notes':'OWNER REQUEST NOTE'}
        data.update(extra)
        return self.client.post('/contractor/services/request',data=data)

    def credentials(self):
        expiry=(datetime.now(timezone.utc)+timedelta(days=30)).date()
        row=CredentialReview(contractor_id=self.contractor.id,decision='approved',license_number=self.contractor.license_number,
            license_expires=expiry,insurance_expires=expiry,license_reference='synthetic-license-evidence',
            insurance_reference='synthetic-insurance-evidence',notes='Existing credential review')
        db.session.add(row);db.session.commit();return row

    def decision(self, row, action='approved', **extra):
        data={'_csrf':'service-csrf','decision':action,'private_review_notes':'PRIVATE ADMIN NOTES',
            'coverage_reference':'PRIVATE COVERAGE REFERENCE','license_scope_checked':'yes','insurance_scope_checked':'yes',
            'response_message':'PUBLIC CONTRACTOR MESSAGE'}
        data.update(extra)
        return self.client.post(f'/admin/service-requests/{row.id}',data=data)

    def test_pending_request_does_not_change_matching_or_self_approve(self):
        self.owner()
        self.assertEqual(self.submit(status='approved',contractor_id='999').status_code,303)
        row=ServiceRequest.query.one();self.assertEqual(row.status,'pending')
        self.assertEqual(row.contractor_id,self.contractor.id)
        services=[item.service_name for item in ContractorService.query.all()]
        self.assertFalse(contractor_matches(self.contractor,Lead(service_needed='Fire Damage Restoration',zip_code='55401'),services))
        self.assertEqual(self.decision(row).status_code,403)
        self.assertEqual(ContractorService.query.count(),1)

    def test_valid_admin_review_adds_one_service_and_preserves_existing_records(self):
        original_id=self.original.id
        self.owner();self.submit();row=ServiceRequest.query.one();self.credentials();self.admin()
        self.assertEqual(self.decision(row,service_name='Emergency Electrical Repair').status_code,303)
        self.assertEqual(self.decision(row).status_code,409)
        db.session.refresh(row);self.assertEqual(row.status,'approved');self.assertIsNone(row.pending_key)
        self.assertEqual(db.session.get(ContractorService,original_id).service_name,'Flood Damage Restoration')
        self.assertEqual(self.contractor.service_type,'Mold Remediation')
        names=[item.service_name for item in ContractorService.query.all()]
        self.assertEqual(len(names),2);self.assertIn('Fire Damage Restoration',names)
        self.assertNotIn('Emergency Electrical Repair',names)
        self.assertTrue(contractor_matches(self.contractor,Lead(service_needed='Fire Damage Restoration',zip_code='55401'),names))
        self.assertEqual(Delivery.query.count(),2)

    def test_approval_requires_current_credentials_and_service_scope_evidence(self):
        self.owner();self.submit();row=ServiceRequest.query.one();self.admin()
        self.assertEqual(self.decision(row).status_code,409)
        review=self.credentials()
        self.assertEqual(self.decision(row,insurance_scope_checked='').status_code,400)
        self.assertEqual(self.decision(row,coverage_reference='').status_code,400)
        review.insurance_expires=(datetime.now(timezone.utc)-timedelta(days=1)).date();db.session.commit()
        self.assertEqual(self.decision(row).status_code,409)
        db.session.refresh(row);self.assertEqual(row.status,'pending')
        self.assertEqual(ContractorService.query.count(),1)

    def test_deactivated_account_cannot_be_given_another_service(self):
        self.owner();self.submit();row=ServiceRequest.query.one();self.credentials()
        self.contractor.active=False;db.session.commit();self.admin()
        self.assertEqual(self.decision(row).status_code,409)
        self.assertEqual(ContractorService.query.count(),1)

    def test_duplicate_current_unknown_and_oversized_requests_are_rejected(self):
        self.owner()
        for data in ({'service_name':'Mold Remediation'},{'service_name':'Made Up Service'},
                     {'contractor_notes':'x'*1001}):
            self.assertEqual(self.submit(**data).status_code,400)
        self.assertEqual(ServiceRequest.query.count(),0)
        self.assertEqual(self.submit().status_code,303)
        page=self.submit(contractor_notes='Retain this invalid entry')
        self.assertEqual(page.status_code,400);self.assertIn('Retain this invalid entry',page.text)
        self.assertEqual(ServiceRequest.query.count(),1);self.assertEqual(Delivery.query.count(),1)

    def test_withdrawal_is_owner_scoped_and_allows_a_new_request(self):
        self.owner();self.submit();row=ServiceRequest.query.one()
        other=Contractor(company_name='Other',contact_name='Other',email='other@example.com',phone='6125550101',
            zip_codes='55401',active=True,verified=True,is_test=False,password_hash='other-synthetic-hash')
        db.session.add(other);db.session.commit();self.owner(other)
        path=f'/contractor/services/requests/{row.id}/withdraw'
        self.assertEqual(self.client.post(path,data={'_csrf':'service-csrf'}).status_code,404)
        self.owner()
        for _ in range(2):self.assertEqual(self.client.post(path,data={'_csrf':'service-csrf'}).status_code,303)
        db.session.refresh(row);self.assertEqual(row.status,'withdrawn');self.assertIsNone(row.pending_key)
        self.assertEqual(self.submit().status_code,303)
        self.assertEqual(ServiceRequest.query.count(),2);self.assertEqual(ContractorService.query.count(),1)

    def test_private_notes_stay_out_of_owner_pages_and_emails(self):
        self.owner();self.submit();row=ServiceRequest.query.one();self.admin()
        self.assertEqual(self.decision(row,action='rejected').status_code,303)
        self.owner();page=self.client.get('/contractor/settings')
        self.assertIn('PUBLIC CONTRACTOR MESSAGE',page.text)
        self.assertIn('no-store',page.headers['Cache-Control'])
        for private in ('PRIVATE ADMIN NOTES','PRIVATE COVERAGE REFERENCE'):
            self.assertNotIn(private,page.text)
            for delivery in Delivery.query.all():self.assertNotIn(private,delivery.body)
        self.assertIn('Mold Remediation',page.text);self.assertIn('Flood Damage Restoration',page.text)
        self.assertEqual(ContractorService.query.count(),1)

    def test_csrf_and_administrator_gates_cannot_be_bypassed(self):
        self.assertEqual(self.client.get('/contractor/services/request').status_code,302)
        self.assertEqual(self.client.get('/admin/service-requests').status_code,403)
        self.owner()
        self.assertEqual(self.client.post('/contractor/services/request',data={'service_name':'Fire Damage Restoration'}).status_code,400)
        self.submit();row=ServiceRequest.query.one();self.admin()
        self.assertEqual(self.client.post(f'/admin/service-requests/{row.id}',data={'decision':'approved'}).status_code,400)
        self.assertEqual(self.client.get('/admin/service-requests').status_code,200)
        self.assertEqual(self.client.get('/admin/service-requests?status=invalid').status_code,400)

    def test_approval_email_reservation_failure_rolls_back_service_addition(self):
        self.owner();self.submit();row=ServiceRequest.query.one();self.credentials();self.admin()
        with patch('communications.queue_email',side_effect=RuntimeError('synthetic failure')),self.assertLogs('app',level='ERROR'):
            response=self.decision(row)
        self.assertEqual(response.status_code,500)
        db.session.refresh(row);self.assertEqual(row.status,'pending');self.assertIsNotNone(row.pending_key)
        self.assertEqual(ContractorService.query.count(),1);self.assertEqual(Delivery.query.count(),1)

    def test_rejection_message_is_required_and_rejected_request_can_be_resubmitted(self):
        self.owner();self.submit();row=ServiceRequest.query.one();self.admin()
        self.assertEqual(self.decision(row,action='rejected',response_message='').status_code,400)
        self.assertEqual(self.decision(row,action='rejected').status_code,303)
        self.owner();self.assertEqual(self.submit().status_code,303)
        self.assertEqual(ServiceRequest.query.count(),2)
        self.assertEqual(ServiceRequest.query.filter_by(status='pending').count(),1)


if __name__=='__main__':unittest.main()

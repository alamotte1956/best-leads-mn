import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import hashlib
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import app,db,Lead,LeadOffer,Contractor,LeadMatchPreference,ConsumerRequestUpdate,MarketBenchmark,BenchmarkMatchType
from lead_choice import match_limit
from contractor_offer_transactions import accept_contractor_offer
from contractor_offer_creation import create_next_sequential_offer
from consumer_requests import request_status,queue_request_update
from contractor_session_security import create_contractor_session_data

class LeadChoiceTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'false','SMS_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client()
        self.lead=Lead(homeowner_name='Private Choice Homeowner',phone='6125550199',email='consumer@example.com',zip_code='55401',service_needed='Mold Remediation',status='New')
        self.contractors=[Contractor(company_name='Synthetic Choice '+str(i),contact_name='Owner',email=f'choice{i}@example.com',phone='6125550100',zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,password_hash='synthetic-hash') for i in range(5)]
        db.session.add_all([self.lead]+self.contractors);db.session.commit()
    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()
    def choose(self,limit):db.session.add(LeadMatchPreference(lead_id=self.lead.id,contractor_limit=limit));db.session.commit()
    def offer(self,c):
        row=LeadOffer(lead_id=self.lead.id,contractor_id=c.id,status='pending',offered_at=datetime.now(timezone.utc)-timedelta(seconds=2),expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(row);db.session.commit();return row
    def test_native_forms_offer_one_or_three_and_invalid_values_never_save(self):
        for path in ('/','/services/roof-repair'):
            html=self.client.get(path).text;self.assertIn('name="contractor_limit"',html);self.assertIn('Up to three contractors',html)
        payload=dict(name='Synthetic',phone='6125550199',zip_code='55401',service_needed='Mold Remediation')
        for value in (0,2,4,True,'3.0','',[],{}):
            self.assertEqual(self.client.post('/api/leads',json=dict(payload,contractor_limit=value)).status_code,400)
        for value in (None,1,3,'3'):
            data=dict(payload)
            if value is not None:data['contractor_limit']=value
            response=self.client.post('/api/leads',json=data);self.assertEqual(response.status_code,201)
            self.assertEqual(match_limit(db.session.get(Lead,response.json['lead_id'])),1 if value is None else int(value))
    def test_single_and_legacy_requests_never_accept_a_second_contractor(self):
        self.assertEqual(match_limit(self.lead),1)
        offers=[self.offer(c) for c in self.contractors[:2]]
        self.assertIsNotNone(accept_contractor_offer(db.session,offers[0].id,self.contractors[0].id));db.session.commit()
        self.assertIsNone(accept_contractor_offer(db.session,offers[1].id,self.contractors[1].id));db.session.commit()
    def test_shared_request_accepts_three_different_contractors_but_not_four_or_duplicates(self):
        self.choose(3);offers=[self.offer(c) for c in self.contractors[:4]]
        for offer,c in zip(offers[:3],self.contractors):self.assertIsNotNone(accept_contractor_offer(db.session,offer.id,c.id));db.session.commit()
        self.assertIsNone(accept_contractor_offer(db.session,offers[3].id,self.contractors[3].id));db.session.commit()
        self.assertEqual(LeadOffer.query.filter_by(status='accepted').count(),3)
    def test_sequential_matching_continues_after_first_shared_acceptance_and_stops_at_cap(self):
        self.choose(3)
        for index in range(3):
            row=create_next_sequential_offer(db.session,self.lead,self.contractors,LeadOffer);db.session.commit()
            self.assertIsNotNone(row);self.assertIsNotNone(accept_contractor_offer(db.session,row.id,row.contractor_id));db.session.commit()
        self.assertIsNone(create_next_sequential_offer(db.session,self.lead,self.contractors,LeadOffer))
    def test_all_accepted_businesses_are_shown_privately_and_email_notice_does_not_duplicate(self):
        self.choose(3)
        for c in self.contractors[:3]:
            row=self.offer(c);accept_contractor_offer(db.session,row.id,c.id);queue_request_update(self.lead,'accepted',row.id);db.session.commit()
        self.assertEqual(ConsumerRequestUpdate.query.count(),1)
        with self.client.session_transaction() as s:s.update(last_lead_reference=self.lead.id,last_lead_status_at=datetime.now(timezone.utc).isoformat())
        page=self.client.get('/request-status');self.assertIn('Shared lead',page.text)
        for c in self.contractors[:3]:self.assertIn(c.company_name,page.text)
        self.assertNotIn('Private Choice Homeowner',page.text)
        with self.client.session_transaction() as s:s.clear()
        self.assertNotIn(self.contractors[0].company_name,self.client.get('/request-status').text)
    def test_contractors_see_type_before_accepting_and_contact_remains_hidden(self):
        self.choose(3);row=self.offer(self.contractors[0]);c=self.contractors[0]
        with self.client.session_transaction() as s:
            s.update(create_contractor_session_data(c.id));s['contractor_password_fingerprint']=hashlib.sha256(c.password_hash.encode()).hexdigest()
        page=self.client.get('/contractor/dashboard');self.assertIn('Shared lead',page.text);self.assertNotIn('Private Choice Homeowner',page.text)
    def test_shared_quotes_require_shared_comparable_evidence(self):
        self.choose(3)
        evidence=MarketBenchmark(state_code='MN',service_name='Mold Remediation',zip_code='55401',observed_at=datetime.now(timezone.utc),angi_cents=10000,thumbtack_cents=8000,angi_reference='authorized synthetic evidence',thumbtack_reference='authorized synthetic evidence',comparison_basis='comparable_contractor_lead_fee',import_key='synthetic-choice-evidence')
        db.session.add(evidence);db.session.commit()
        from market_pricing import current_benchmark
        from werkzeug.exceptions import ServiceUnavailable
        with self.assertRaises(ServiceUnavailable):current_benchmark(self.lead)
        db.session.add(BenchmarkMatchType(benchmark_id=evidence.id,contractor_limit=3));db.session.commit()
        self.assertEqual(current_benchmark(self.lead).id,evidence.id)
    def test_closed_request_cannot_fill_shared_slots(self):
        self.choose(3);row=self.offer(self.contractors[0]);self.lead.status='Cancelled';db.session.commit()
        self.assertIsNone(accept_contractor_offer(db.session,row.id,self.contractors[0].id))

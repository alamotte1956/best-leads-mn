import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import csv
import io
import time
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from werkzeug.exceptions import HTTPException
from app import app,db,MarketBenchmark,BenchmarkMatchType,Lead,LeadMatchPreference
from market_pricing import current_benchmark,quote_from_benchmark,import_benchmark_records,MARKET_ZONE
from pricing_evidence import FIELDS,MAX_BYTES,parse_csv,import_csv,template_csv

class PricingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-pricing-admin','EMAIL_SENDING_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all();self.client=app.test_client();self.admin()
    def tearDown(self):
        db.session.remove();self.ctx.pop();self.env.stop()
    def admin(self):
        from admin_session_security import current_password_fingerprint
        with self.client.session_transaction() as s:
            s.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint(),_csrf='pricing-csrf')
    def row(self,**extra):
        data=dict(state_code='MN',service_name='Mold Remediation',zip_code='55401',contractor_limit='1',
            observed_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),currency='USD',
            angi_cents='10000',thumbtack_cents='8000',angi_reference='private-angi-record-001',
            thumbtack_reference='private-thumbtack-record-001',comparison_basis='comparable_contractor_lead_fee',import_key='synthetic-001')
        data.update(extra);return data
    def csv(self,rows):
        output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows);return output.getvalue().encode()
    def upload(self,raw,**extra):
        data=dict(_csrf='pricing-csrf',authorized='yes',evidence=(io.BytesIO(raw),'evidence.csv'));data.update(extra)
        return self.client.post('/admin/pricing/import',data=data,content_type='multipart/form-data')
    def test_admin_import_calculates_exact_fee_and_retries_without_overwriting(self):
        raw=self.csv([self.row()]);self.assertEqual(self.upload(raw).status_code,303)
        self.assertEqual(self.upload(raw).status_code,303);self.assertEqual(MarketBenchmark.query.count(),1)
        evidence=MarketBenchmark.query.one();self.assertEqual(evidence.angi_reference,'private-angi-record-001')
        # Noon makes this assertion independent of the current quote-window cutoff.
        noon=evidence.observed_at.replace(hour=18,minute=0,second=0,microsecond=0,tzinfo=timezone.utc)
        evidence.observed_at=noon-timedelta(seconds=1)
        self.assertEqual(quote_from_benchmark(evidence,noon)[0],6800)
    def test_conflicting_key_rolls_back_entire_batch_and_preserves_evidence(self):
        row=self.row();import_csv(self.csv([row]))
        changed=dict(row,thumbtack_cents='7000');new=self.row(import_key='synthetic-002')
        self.assertEqual(self.upload(self.csv([new,changed])).status_code,400)
        self.assertEqual(MarketBenchmark.query.count(),1);self.assertEqual(MarketBenchmark.query.one().thumbtack_cents,8000)
    def test_scope_and_sharing_are_never_substituted(self):
        import_csv(self.csv([self.row()]))
        lead=Lead(homeowner_name='Synthetic',phone='6125550100',zip_code='55401',service_needed='Mold Remediation')
        db.session.add(lead);db.session.flush();db.session.add(LeadMatchPreference(lead_id=lead.id,contractor_limit=3));db.session.commit()
        with self.assertRaises(HTTPException):current_benchmark(lead)
        import_csv(self.csv([self.row(import_key='shared-001',contractor_limit='3',thumbtack_cents='4000')]))
        self.assertEqual(current_benchmark(lead).thumbtack_cents,4000)
        lead.zip_code='55402'
        with self.assertRaises(HTTPException):current_benchmark(lead)
    def test_authorization_csrf_auth_and_private_headers(self):
        raw=self.csv([self.row()])
        self.assertEqual(self.upload(raw,authorized='no').status_code,400)
        self.assertEqual(self.upload(raw,_csrf='wrong').status_code,400)
        self.assertEqual(MarketBenchmark.query.count(),0)
        response=self.client.get('/admin/pricing/template.csv');self.assertEqual(response.status_code,200)
        self.assertEqual(response.text,template_csv());self.assertEqual(len(response.text.splitlines()),1)
        self.assertIn('no-store',response.headers['Cache-Control'])
        with self.client.session_transaction() as s:s.clear()
        self.assertEqual(self.upload(raw).status_code,403)
        self.assertEqual(self.client.get('/admin/pricing/template.csv').status_code,403)
        self.assertEqual(self.client.get('/admin/pricing').status_code,403)
    def test_invalid_values_rejected_without_echoing_uploaded_cells(self):
        bad_values=[('currency','CAD'),('contractor_limit','2'),('contractor_limit',''),('angi_cents','1.99'),
            ('thumbtack_cents','-1'),('angi_cents','2147483648'),('angi_cents','0'),('thumbtack_cents','NaN'),
            ('zip_code','５５４０１'),('zip_code','55401-1234'),('state_code','XX'),('service_name','unknown'),
            ('comparison_basis','homeowner_estimate'),('angi_reference',''),
            ('angi_reference','https://example.com/report?token=synthetic-private'),
            ('thumbtack_reference','https://person:secret@example.com'),('import_key',''),
            ('observed_at',datetime.now(timezone.utc).replace(tzinfo=None).isoformat()),
            ('observed_at',(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()),
            ('observed_at',(datetime.now(timezone.utc)-timedelta(days=1)).isoformat())]
        for key,value in bad_values:
            with self.subTest(key=key,value=value):
                response=self.upload(self.csv([self.row(**{key:value})]))
                self.assertEqual(response.status_code,400);self.assertNotIn('synthetic-private',response.text)
                self.assertEqual(MarketBenchmark.query.count(),0)
    def test_malformed_empty_oversized_and_oversized_row_count(self):
        for raw in (b'',template_csv().encode(),b'wrong,headers\n1,2\n',b'\xff',b'a'*(MAX_BYTES+1),
                    self.csv([self.row(import_key=f'synthetic-{i}') for i in range(501)])):
            with self.subTest(size=len(raw)):
                self.assertEqual(self.upload(raw).status_code,400);self.assertEqual(MarketBenchmark.query.count(),0)
    def test_invalid_later_row_and_same_file_conflict_are_atomic(self):
        rows=[self.row(),self.row(import_key='invalid',currency='EUR')]
        self.assertEqual(self.upload(self.csv(rows)).status_code,400);self.assertEqual(MarketBenchmark.query.count(),0)
        row=self.row();rows=[row,dict(row,angi_cents='5000')]
        self.assertEqual(self.upload(self.csv(rows)).status_code,400);self.assertEqual(MarketBenchmark.query.count(),0)
    def test_import_does_not_enable_closed_states_or_payment_switches(self):
        import_csv(self.csv([self.row(state_code='IN')]))
        from national_markets import code_enabled
        self.assertFalse(code_enabled('IN'));self.assertNotEqual(os.environ.get('PAYMENTS_ENABLED'),'true')
    def test_current_evidence_can_import_at_day_end_but_checkout_stays_closed(self):
        now=datetime(2026,11,2,23,45,tzinfo=MARKET_ZONE).astimezone(timezone.utc)
        record=parse_csv(self.csv([self.row()]))[0];record['observed_at']=now-timedelta(minutes=1)
        self.assertEqual(import_benchmark_records([record],now=now),1)
        with self.assertRaises(HTTPException):quote_from_benchmark(MarketBenchmark.query.one(),now)
    def test_admin_page_discloses_type_source_readiness_and_escapes_evidence(self):
        import_csv(self.csv([self.row(angi_reference='<script>synthetic()</script>',contractor_limit='3')]))
        response=self.client.get('/admin/pricing');self.assertEqual(response.status_code,200)
        self.assertIn('Shared lead: up to three contractors',response.text)
        self.assertIn('not connected',response.text);self.assertIn('private-thumbtack-record-001',response.text)
        self.assertNotIn('<script>synthetic()',response.text);self.assertIn('no-store',response.headers['Cache-Control'])

    def test_cli_requires_authorization_and_reuses_the_same_validation(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'synthetic.csv';path.write_bytes(self.csv([self.row()]))
            runner=app.test_cli_runner()
            result=runner.invoke(args=['import-market-benchmarks',str(path)])
            self.assertNotEqual(result.exit_code,0);self.assertEqual(MarketBenchmark.query.count(),0)
            result=runner.invoke(args=['import-market-benchmarks',str(path),'--authorized'])
            self.assertEqual(result.exit_code,0,result.output);self.assertEqual(MarketBenchmark.query.count(),1)
            result=runner.invoke(args=['import-market-benchmarks',str(path),'--authorized'])
            self.assertEqual(result.exit_code,0);self.assertIn("'imported': 0",result.output)
            path.write_bytes(self.csv([self.row(import_key='other',currency='EUR')]))
            self.assertNotEqual(runner.invoke(args=['import-market-benchmarks',str(path),'--authorized']).exit_code,0)
            self.assertEqual(MarketBenchmark.query.count(),1)

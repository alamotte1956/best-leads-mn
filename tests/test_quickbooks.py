import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import copy
import hashlib
import json
import time
import unittest
from datetime import datetime,timedelta,timezone,date
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from cryptography.fernet import Fernet
from app import app,db,QuickBooksConnection,QuickBooksOAuthAttempt,QuickBooksExport,FinanceEntry
import quickbooks_client as provider
from quickbooks import source_hash

class QuickBooksTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-qbo-admin','QBO_ENABLED':'true',
            'QBO_ENVIRONMENT':'sandbox','QBO_CLIENT_ID':'synthetic-client','QBO_CLIENT_SECRET':'synthetic-client-secret',
            'QBO_TOKEN_KEY':Fernet.generate_key().decode(),'QBO_LIVE_EXPORTS_ENABLED':'false'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.client=app.test_client();self.admin(self.client)
        self.tokens=dict(access_token='synthetic-access-token',refresh_token='synthetic-refresh-token',access_expires=time.time()+3600,refresh_expires=time.time()+86400)
        self.accounts={'QueryResponse':{'Account':[{'Id':'10','Name':'Hosting','AccountType':'Expense'},
            {'Id':'20','Name':'Company card','AccountType':'Credit Card'},{'Id':'30','Name':'Unrelated','AccountType':'Income'}]}}
    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()
    def admin(self,browser):
        from admin_session_security import current_password_fingerprint
        with browser.session_transaction() as state:state.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint(),_csrf='qbo-csrf')
    def post(self,path,**extra):return self.client.post(path,data={'_csrf':'qbo-csrf',**extra})
    def connection(self,confirmed=True):
        row=QuickBooksConnection(environment=provider.environment(),realm_id='93410001',company_name='Synthetic Company',
            client_binding=provider.binding(),encrypted_tokens=provider.seal(self.tokens),status='connected',confirmed_at=datetime.now(timezone.utc) if confirmed else None)
        db.session.add(row);db.session.commit();return row
    def expense(self,**extra):
        data=dict(entry_key='synthetic-expense-key',occurred_on=date(2026,11,2),kind='expense',category='Hosting',description='Synthetic hosting invoice',amount_cents=2525,mode='test')
        data.update(extra);row=FinanceEntry(**data);db.session.add(row);db.session.commit();return row
    def start(self):
        response=self.post('/admin/quickbooks/connect');self.assertEqual(response.status_code,303)
        return parse_qs(urlsplit(response.location).query)['state'][0]
    def callback(self,state,**extra):
        return self.client.get('/admin/quickbooks/callback',query_string={'state':state,'code':'synthetic-code','realmId':'93410001',**extra})
    def token_reply(self):return dict(access_token='synthetic-new-access',refresh_token='synthetic-new-refresh',expires_in=3600,x_refresh_token_expires_in=86400)
    def successful_callback(self,state):
        with patch.object(provider,'token_request',return_value=self.token_reply()),patch.object(provider,'raw_api',return_value={'CompanyInfo':{'Id':'1','CompanyName':'Synthetic Company'}}):
            return self.callback(state)
    def fake_api(self,cid,path,params=None,payload=None,**kwargs):
        if path=='/query':return self.accounts
        if path=='/preferences':return {'Preferences':{'CurrencyPrefs':{'HomeCurrency':{'value':'USD'}}}}
        if path=='/purchase':return {'Purchase':dict(copy.deepcopy(payload),Id='81')}
        raise AssertionError('Unexpected synthetic API operation '+path)
    def export(self,entry,**extra):
        return self.post(f'/admin/quickbooks/expenses/{entry.id}/export',source_hash=source_hash(entry),expense_account='10',funding_account='20',confirm_export='yes',**extra)
    def test_readiness_without_credentials_does_not_claim_connection(self):
        with patch.dict(os.environ,{'QBO_CLIENT_ID':'','QBO_ENABLED':'false'}):
            response=self.client.get('/admin/quickbooks')
            self.assertEqual(response.status_code,200);self.assertIn('Setup required — not connected',response.text)
            self.assertNotIn('>Connect to QuickBooks Online<',response.text)
            self.assertEqual(self.post('/admin/quickbooks/connect').status_code,503)
        self.assertIn('no-store',response.headers['Cache-Control'])
    def test_oauth_fixed_destination_single_use_encrypted_tokens_and_confirmation(self):
        state=self.start();attempt=QuickBooksOAuthAttempt.query.one()
        self.assertNotEqual(attempt.state_hash,state)
        response=self.successful_callback(state);self.assertEqual(response.status_code,303)
        row=QuickBooksConnection.query.one();self.assertIsNone(row.confirmed_at)
        self.assertNotIn('synthetic-new-access',row.encrypted_tokens)
        self.assertEqual(provider.unseal(row.encrypted_tokens)['refresh_token'],'synthetic-new-refresh')
        self.assertEqual(self.client.get('/admin/quickbooks/profit-and-loss').status_code,409)
        response=self.post('/admin/quickbooks/confirm',realm_id=row.realm_id,connection_id=str(row.id),confirm_company='yes')
        self.assertEqual(response.status_code,303);self.assertIsNotNone(row.confirmed_at)
        self.assertEqual(self.callback(state).status_code,400)
        self.assertNotIn('synthetic-new-access',self.client.get('/admin/quickbooks').text)
    def test_oauth_csrf_browser_expiry_password_rotation_and_no_code_redirect(self):
        self.assertEqual(self.client.post('/admin/quickbooks/connect').status_code,400)
        state=self.start();other=app.test_client();self.admin(other)
        self.assertEqual(other.get('/admin/quickbooks/callback',query_string={'state':state,'code':'private-code'}).status_code,400)
        attempt=QuickBooksOAuthAttempt.query.one();attempt.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.session.commit()
        self.assertEqual(self.callback(state).status_code,400)
        state=self.start()
        with patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-rotated'}):self.assertEqual(self.callback(state).status_code,400)
        anonymous=app.test_client();response=anonymous.get('/admin/quickbooks/callback?code=private-code&state=private-state')
        self.assertEqual(response.status_code,400);self.assertNotIn('private-code',response.text);self.assertNotIn('Location',response.headers)
    def test_denial_consumes_state_and_client_change_cannot_reuse_attempt(self):
        state=self.start()
        with patch.object(provider,'token_request') as token:
            self.assertEqual(self.callback(state,error='access_denied').status_code,303);token.assert_not_called()
        self.assertIsNotNone(QuickBooksOAuthAttempt.query.one().consumed_at)
        state=self.start()
        with patch.dict(os.environ,{'QBO_CLIENT_ID':'changed-client'}):self.assertEqual(self.callback(state).status_code,400)
    def test_refresh_rotation_persists_even_if_next_read_fails(self):
        self.tokens['access_expires']=time.time()-1;row=self.connection()
        with patch.object(provider,'token_request',return_value=self.token_reply()) as refresh,patch.object(provider,'raw_api',side_effect=provider.QBOError('Synthetic read failure')):
            with self.assertRaises(provider.QBOError):provider.api(row.id,'/preferences',expected_realm=row.realm_id)
            refresh.assert_called_once()
        db.session.refresh(row);self.assertEqual(provider.unseal(row.encrypted_tokens)['refresh_token'],'synthetic-new-refresh')
    def test_expired_or_failed_refresh_requires_reauthorization_without_retry(self):
        self.tokens['access_expires']=time.time()-1;row=self.connection()
        with patch.object(provider,'token_request',side_effect=provider.QBOError('Synthetic timeout')) as refresh:
            with self.assertRaises(provider.QBOError):provider.api(row.id,'/preferences')
            self.assertEqual(row.status,'reauthorize')
            with self.assertRaises(provider.QBOError):provider.api(row.id,'/preferences')
            refresh.assert_called_once()
    def test_currency_period_basis_and_no_data_are_not_invented(self):
        self.connection();report={'Header':{'ReportName':'ProfitAndLoss','ReportBasis':'Cash','StartPeriod':'2026-11-01','EndPeriod':'2026-11-02','Currency':'USD','Option':[{'Name':'NoReportData','Value':'true'}]},'Rows':{}}
        with patch.object(provider,'api',return_value=report) as api:
            response=self.client.get('/admin/quickbooks/profit-and-loss?start=2026-11-01&end=2026-11-02')
            self.assertEqual(response.status_code,200);self.assertIn('not a confirmed zero profit',response.text)
            self.assertIn('USD',response.text);self.assertIn('no-store',response.headers['Cache-Control'])
            self.assertEqual(api.call_args.args[1],'/reports/ProfitAndLoss')
        report['Header']['ReportBasis']='Accrual'
        with patch.object(provider,'api',return_value=report):self.assertEqual(self.client.get('/admin/quickbooks/profit-and-loss?start=2026-11-01&end=2026-11-02').status_code,502)
        for query in ('start=bad','start=2026-12-01&end=2026-11-01','basis=Invented','start=2020-01-01&end=2026-11-01'):
            self.assertEqual(self.client.get('/admin/quickbooks/profit-and-loss?'+query).status_code,400)
    def test_expense_export_is_exact_once_and_no_second_local_expense(self):
        row=self.connection();entry=self.expense()
        with patch.object(provider,'api',side_effect=self.fake_api) as api:
            self.assertEqual(self.export(entry).status_code,303)
            purchase=[call for call in api.call_args_list if call.args[1]=='/purchase'];self.assertEqual(len(purchase),1)
            self.assertEqual(purchase[0].args[3]['TotalAmt'],25.25)
            self.assertEqual(purchase[0].args[3]['PaymentType'],'CreditCard')
            self.assertEqual(purchase[0].kwargs['expected_realm'],row.realm_id)
            self.assertEqual(self.export(entry).status_code,303)
            self.assertEqual(len([c for c in api.call_args_list if c.args[1]=='/purchase']),1)
        self.assertEqual(FinanceEntry.query.count(),1);record=QuickBooksExport.query.one()
        self.assertEqual(record.status,'sent');self.assertEqual(record.external_id,'81')
    def test_unconfirmed_export_is_not_resent_and_can_only_match_existing_purchase(self):
        self.connection();entry=self.expense()
        def uncertain(cid,path,*args,**kwargs):
            if path=='/purchase':raise provider.QBOError('Synthetic timeout')
            return self.fake_api(cid,path,*args,**kwargs)
        with patch.object(provider,'api',side_effect=uncertain):self.assertEqual(self.export(entry).status_code,502)
        record=QuickBooksExport.query.one();self.assertEqual(record.status,'uncertain')
        with patch.object(provider,'api') as api:
            self.assertEqual(self.export(entry).status_code,409);api.assert_not_called()
        payload=json.loads(record.payload_json);actual=dict(payload,Id='81')
        with patch.object(provider,'api',return_value={'Purchase':dict(actual,TotalAmt=999)}):
            self.assertEqual(self.post(f'/admin/quickbooks/exports/{record.id}/reconcile',external_id='81').status_code,409)
        with patch.object(provider,'api',return_value={'Purchase':actual}):
            self.assertEqual(self.post(f'/admin/quickbooks/exports/{record.id}/reconcile',external_id='81').status_code,303)
        self.assertEqual(record.status,'sent')
        self.assertEqual(self.post(f'/admin/quickbooks/exports/{record.id}/reconcile',external_id='82').status_code,409)
    def test_mode_void_stale_account_and_foreign_currency_guards(self):
        self.connection();entry=self.expense(mode='live')
        self.assertEqual(self.export(entry).status_code,409)
        entry.mode='test';entry.voided_at=datetime.now(timezone.utc);db.session.commit();self.assertEqual(self.export(entry).status_code,409)
        entry.voided_at=None;db.session.commit()
        fields=dict(source_hash='stale',expense_account='10',funding_account='20',confirm_export='yes')
        self.assertEqual(self.post(f'/admin/quickbooks/expenses/{entry.id}/export',**fields).status_code,409)
        fields['source_hash']=source_hash(entry);fields['expense_account']='30'
        with patch.object(provider,'api',side_effect=self.fake_api):self.assertEqual(self.post(f'/admin/quickbooks/expenses/{entry.id}/export',**fields).status_code,400)
        def foreign(cid,path,*args,**kwargs):
            if path=='/preferences':return {'Preferences':{'CurrencyPrefs':{'HomeCurrency':{'value':'CAD'}}}}
            return self.fake_api(cid,path,*args,**kwargs)
        with patch.object(provider,'api',side_effect=foreign):self.assertEqual(self.export(entry).status_code,409)
        self.assertEqual(QuickBooksExport.query.count(),0)
    def test_production_exports_disabled_and_realm_change_blocks_api(self):
        with patch.dict(os.environ,{'QBO_ENVIRONMENT':'production'}):
            row=self.connection();entry=self.expense(mode='live')
            self.assertEqual(self.export(entry).status_code,503)
            with patch.object(provider,'raw_api') as raw:
                with self.assertRaises(provider.QBOError):provider.api(row.id,'/purchase',payload={},expected_realm='999')
                raw.assert_not_called()
    def test_disconnect_revokes_and_clears_local_secrets_even_after_provider_failure(self):
        row=self.connection()
        with patch.object(provider,'transport',side_effect=provider.QBOError('Synthetic revocation failure')):
            response=self.post('/admin/quickbooks/disconnect',connection_id=str(row.id),realm_id=row.realm_id)
            self.assertEqual(response.status_code,303)
        self.assertIsNone(row.encrypted_tokens);self.assertIsNone(row.confirmed_at);self.assertEqual(row.status,'disconnected')
    def test_encryption_key_change_never_silently_regenerates_tokens(self):
        row=self.connection()
        with patch.dict(os.environ,{'QBO_TOKEN_KEY':Fernet.generate_key().decode()}):
            with self.assertRaises(provider.QBOError):provider.unseal(row.encrypted_tokens)
    def test_transport_blocks_redirects_and_redacts_provider_errors(self):
        from urllib.error import HTTPError
        self.assertIsNone(provider.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))
        with patch.object(provider,'build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://example.com/private-token',401,'private-provider-body',None,None)
            with self.assertRaises(provider.QBOError) as error:provider.transport(provider.TOKEN)
            self.assertNotIn('private-token',str(error.exception));self.assertNotIn('private-provider-body',str(error.exception))
    def test_unauthorized_reads_redirect_and_writes_are_denied(self):
        with self.client.session_transaction() as state:state.clear()
        self.assertEqual(self.client.get('/admin/quickbooks').status_code,302)
        self.assertEqual(self.client.post('/admin/quickbooks/connect').status_code,403)

    def test_local_disconnect_still_works_when_provider_credentials_are_missing(self):
        row=self.connection()
        with patch.dict(os.environ,{'QBO_CLIENT_SECRET':'','QBO_ENABLED':'false'}),patch.object(provider,'transport') as transport:
            self.assertEqual(self.post('/admin/quickbooks/disconnect',connection_id=str(row.id),realm_id=row.realm_id).status_code,303)
            transport.assert_not_called()
        self.assertIsNone(row.encrypted_tokens);self.assertEqual(row.status,'disconnected')

    def test_provider_uncertainty_cannot_undo_a_concurrent_verified_reconciliation(self):
        self.connection();entry=self.expense()
        def reconciled_then_timeout(cid,path,*args,**kwargs):
            if path=='/purchase':
                record=QuickBooksExport.query.one();record.status='sent';record.external_id='81';db.session.commit()
                raise provider.QBOError('Synthetic lost response after reconciliation')
            return self.fake_api(cid,path,*args,**kwargs)
        with patch.object(provider,'api',side_effect=reconciled_then_timeout):self.assertEqual(self.export(entry).status_code,502)
        self.assertEqual(QuickBooksExport.query.one().status,'sent');self.assertEqual(QuickBooksExport.query.one().external_id,'81')

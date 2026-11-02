import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import hashlib
import hmac
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import stripe
from app import app, db, Contractor, Lead, LeadOffer, Payment, MarketBenchmark, ProviderEvent
from billing import offer_contact_available
from contractor_session_security import create_contractor_session_data
from checkout_reconciliation import reconcile_batch


class CheckoutReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'PAYMENTS_ACTIVATION_UTC': '2020-01-01T00:00:00Z', 'STRIPE_MODE': 'test',
            'PAYMENTS_ENABLED': 'true', 'CHECKOUT_RECONCILIATION_ENABLED': 'true',
            'STRIPE_SECRET_KEY': 'sk_test_synthetic', 'STRIPE_WEBHOOK_SECRET': 'whsec_synthetic',
            'PUBLIC_SITE_URL': 'https://example.com', 'EMAIL_SENDING_ENABLED': 'false',
        })
        self.env.start()
        self.ctx = app.app_context(); self.ctx.push()
        db.drop_all(); db.create_all()
        self.client = app.test_client()
        self.contractor = Contractor(company_name='Synthetic', contact_name='Owner', email='test@example.com',
            phone='6125550100', zip_codes='55401', service_type='Mold Remediation', active=True,
            verified=True, is_test=False, password_hash='synthetic-hash')
        self.lead = Lead(homeowner_name='PRIVATE NAME', phone='6125550199', zip_code='55401',
            service_needed='Mold Remediation', status='New')
        db.session.add_all([self.contractor, self.lead]); db.session.flush()
        self.offer = LeadOffer(contractor_id=self.contractor.id, lead_id=self.lead.id, status='accepted',
            accepted_at=datetime.now(timezone.utc), offered_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15))
        self.benchmark = MarketBenchmark(state_code='MN', service_name='Mold Remediation', zip_code='55401',
            observed_at=datetime.now(timezone.utc), angi_cents=4000, thumbtack_cents=3500,
            angi_reference='synthetic', thumbtack_reference='synthetic',
            comparison_basis='comparable_contractor_lead_fee', import_key='synthetic')
        db.session.add_all([self.offer, self.benchmark]); db.session.flush()
        self.payment = Payment(contractor_id=self.contractor.id, offer_id=self.offer.id,
            amount_cents=2500, currency='usd', price_id=f'market:{self.benchmark.id}',
            market_benchmark_id=self.benchmark.id, status='open', session_id='cs_test_synthetic',
            quote_expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.session.add(self.payment); db.session.commit()
        self.login(self.contractor)

    def tearDown(self):
        db.session.remove(); self.ctx.pop(); self.env.stop()

    def login(self, contractor):
        with self.client.session_transaction() as session:
            session.update(create_contractor_session_data(contractor.id))
            session['contractor_password_fingerprint'] = hashlib.sha256(contractor.password_hash.encode()).hexdigest()
            session['_csrf'] = 'test-csrf'

    def snapshot(self, status='open', payment_status='unpaid', **changes):
        value = {'id': self.payment.session_id, 'status': status, 'payment_status': payment_status,
            'mode': 'payment', 'livemode': False, 'amount_total': self.payment.amount_cents,
            'currency': self.payment.currency, 'metadata': {'payment_id': str(self.payment.id),
                'contractor_id': str(self.contractor.id), 'benchmark_id': str(self.benchmark.id)}}
        value.update(changes)
        return value

    def reconcile(self):
        return self.client.post(f'/contractor/payments/{self.payment.id}/reconcile', data={'_csrf': 'test-csrf'})

    def webhook(self, obj, kind='checkout.session.expired', identifier='evt_expired'):
        body = json.dumps({'id': identifier, 'type': kind, 'livemode': False, 'data': {'object': obj}})
        stamp = str(int(time.time()))
        signature = hmac.new(b'whsec_synthetic', (stamp+'.'+body).encode(), hashlib.sha256).hexdigest()
        return self.client.post('/webhooks/stripe', data=body, content_type='application/json',
            headers={'Stripe-Signature': 't='+stamp+',v1='+signature})

    def test_expired_quote_expires_hosted_url_and_preserves_original_order(self):
        self.payment.quote_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.session.commit()
        with patch('billing.retrieve_checkout', return_value=self.snapshot()), patch('billing.expire_checkout',
                return_value=self.snapshot('expired')) as expire, patch('billing.create_checkout') as create:
            self.assertEqual(self.reconcile().status_code, 303)
            expire.assert_called_once_with('cs_test_synthetic', api_key='sk_test_synthetic')
            create.assert_not_called()
        db.session.refresh(self.payment)
        self.assertEqual(self.payment.status, 'expired')
        self.assertEqual(self.payment.amount_cents, 2500)
        self.assertEqual(self.payment.session_id, 'cs_test_synthetic')
        self.assertFalse(offer_contact_available(self.offer))

    def test_closed_request_is_reconciled_even_though_it_cannot_start_new_checkout(self):
        for state in ('Cancelled', 'Closed'):
            self.lead.status = state; self.payment.status = 'open'; db.session.commit()
            with patch('billing.retrieve_checkout', return_value=self.snapshot()), patch('billing.expire_checkout',
                    return_value=self.snapshot('expired')) as expire:
                self.assertEqual(self.reconcile().status_code, 303); expire.assert_called_once()
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/checkout', data={'_csrf':'test-csrf'}).status_code, 409)

    def test_shutdown_can_close_old_checkout_without_enabling_new_payments(self):
        with patch.dict(os.environ, {'PAYMENTS_ENABLED':'false'}), patch('billing.retrieve_checkout', return_value=self.snapshot()), \
                patch('billing.expire_checkout', return_value=self.snapshot('expired')) as expire:
            self.assertEqual(self.reconcile().status_code, 303); expire.assert_called_once()
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/checkout', data={'_csrf':'test-csrf'}).status_code, 503)

    def test_current_quote_and_active_request_keep_the_existing_checkout(self):
        with patch('billing.retrieve_checkout', return_value=self.snapshot()), patch('billing.expire_checkout') as expire:
            self.assertEqual(self.reconcile().status_code, 303); expire.assert_not_called()
        db.session.refresh(self.payment); self.assertEqual(self.payment.status, 'open')

    def test_unverified_or_disabled_coverage_causes_worker_to_expire_open_checkout(self):
        self.contractor.active = False; db.session.commit()
        with patch('billing.retrieve_checkout', return_value=self.snapshot()), patch('billing.expire_checkout',
                return_value=self.snapshot('expired')) as expire:
            result = reconcile_batch(); expire.assert_called_once()
        self.assertEqual(result['results'], {'expired': 1})

    def test_provider_says_paid_but_only_signed_payment_webhook_unlocks_contact(self):
        with patch('billing.retrieve_checkout', return_value=self.snapshot('complete','paid')), patch('billing.expire_checkout') as expire:
            self.assertEqual(self.reconcile().status_code, 303); expire.assert_not_called()
        db.session.refresh(self.payment); self.assertEqual(self.payment.status, 'awaiting_confirmation')
        self.assertFalse(offer_contact_available(self.offer))
        self.assertEqual(self.webhook(self.snapshot('complete','paid',payment_intent='pi_paid'),
            kind='checkout.session.completed',identifier='evt_paid').status_code, 204)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status, 'paid')
        self.assertTrue(offer_contact_available(self.offer))

    def test_complete_unpaid_waits_for_async_confirmation_without_expiring(self):
        self.lead.status = 'Cancelled'; db.session.commit()
        with patch('billing.retrieve_checkout', return_value=self.snapshot('complete')), patch('billing.expire_checkout') as expire:
            self.assertEqual(self.reconcile().status_code, 303); expire.assert_not_called()
        db.session.refresh(self.payment); self.assertEqual(self.payment.status, 'awaiting_payment')
        self.assertFalse(offer_contact_available(self.offer))

    def test_signed_expiration_is_idempotent_and_never_downgrades_paid_or_refunded(self):
        obj = self.snapshot('expired')
        self.assertEqual(self.webhook(obj).status_code, 204)
        self.assertEqual(self.webhook(obj).status_code, 204)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status, 'expired')
        self.assertEqual(ProviderEvent.query.count(), 1)
        for status in ('paid','refunded','awaiting_payment','awaiting_confirmation'):
            self.payment.status=status; db.session.commit()
            self.assertEqual(self.webhook(obj, identifier='evt_'+status).status_code, 204)
            db.session.refresh(self.payment); self.assertEqual(self.payment.status,status)

    def test_forged_or_inconsistent_expiration_does_not_change_order(self):
        response=self.client.post('/webhooks/stripe',json={},headers={'Stripe-Signature':'forged'})
        self.assertEqual(response.status_code,400)
        for obj in (self.snapshot('expired', 'paid'), self.snapshot('open'), self.snapshot('expired', amount_total=1)):
            self.assertEqual(self.webhook(obj).status_code,400)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'open')
        self.assertEqual(ProviderEvent.query.count(),0)

    def test_early_expiration_links_only_the_creating_order(self):
        obj=self.snapshot('expired'); self.payment.session_id=None; self.payment.status='creating'; db.session.commit()
        self.assertEqual(self.webhook(obj).status_code,204)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'expired')
        self.assertEqual(self.payment.session_id,'cs_test_synthetic')

    def test_provider_timeout_never_proves_expiration(self):
        self.lead.status='Cancelled'; db.session.commit()
        with patch('billing.retrieve_checkout',return_value=self.snapshot()), patch('billing.expire_checkout',
                side_effect=stripe.APIConnectionError('synthetic timeout')):
            self.assertEqual(self.reconcile().status_code,503)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'open')

    def test_payment_can_win_expiration_race_without_replacement_or_contact_unlock(self):
        self.lead.status='Closed'; db.session.commit()
        with patch('billing.retrieve_checkout', side_effect=[self.snapshot(),self.snapshot('complete','paid')]), \
                patch('billing.expire_checkout',side_effect=stripe.InvalidRequestError('already complete',param=None)):
            self.assertEqual(self.reconcile().status_code,303)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'awaiting_confirmation')
        self.assertFalse(offer_contact_available(self.offer))

    def test_webhook_during_network_call_cannot_be_overwritten(self):
        self.lead.status='Closed'; db.session.commit()
        def expired_after_paid(*args,**kwargs):
            self.assertEqual(self.webhook(self.snapshot('complete','paid',payment_intent='pi_race'),
                kind='checkout.session.completed',identifier='evt_race').status_code,204)
            return self.snapshot('expired')
        with patch('billing.retrieve_checkout',return_value=self.snapshot()), patch('billing.expire_checkout',side_effect=expired_after_paid):
            self.assertEqual(self.reconcile().status_code,303)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'paid')

    def test_mismatched_provider_session_fails_closed_without_expiring_anything(self):
        for change in ({'id':'another_session'}, {'livemode':True}, {'livemode':None}, {'amount_total':1},
                       {'currency':'eur'}, {'metadata':{'payment_id':'999'}}):
            with self.subTest(change=change),patch('billing.retrieve_checkout',return_value=self.snapshot(**change)), \
                    patch('billing.expire_checkout') as expire:
                self.assertEqual(self.reconcile().status_code,409); expire.assert_not_called()
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'open')

    def test_unlinked_create_timeout_never_creates_replacement_or_assumes_expiry(self):
        self.payment.session_id=None; self.payment.status='creating'
        self.payment.quote_expires_at=datetime.now(timezone.utc)-timedelta(hours=1); db.session.commit()
        with patch('billing.retrieve_checkout') as retrieve, patch('billing.create_checkout') as create:
            self.assertEqual(self.reconcile().status_code,303)
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/quote',data={'_csrf':'test-csrf'}).status_code,409)
            retrieve.assert_not_called(); create.assert_not_called()
        self.assertEqual(self.payment.status,'creating')

    def test_only_proven_unused_expired_quote_can_refresh_from_current_evidence(self):
        self.payment.status='quoted'; self.payment.session_id=None
        self.payment.quote_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1); db.session.commit()
        with patch('market_pricing.quote_from_benchmark',return_value=(2975,datetime.now(timezone.utc)+timedelta(hours=1))), \
                patch('billing.create_checkout') as create:
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/quote',data={'_csrf':'test-csrf','amount':'1'}).status_code,200)
            create.assert_not_called()
        db.session.refresh(self.payment); self.assertEqual(self.payment.amount_cents,2975)
        self.assertEqual(self.payment.status,'quoted'); self.assertIsNone(self.payment.session_id)

    def test_attempt_is_persisted_before_create_timeout_preventing_unsafe_requote(self):
        self.payment.status='quoted'; self.payment.session_id=None; db.session.commit()
        def timeout(**kwargs):
            db.session.refresh(self.payment); self.assertEqual(self.payment.status,'creating')
            raise stripe.APIConnectionError('synthetic')
        with patch('billing.create_checkout',side_effect=timeout):
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/checkout',data={'_csrf':'test-csrf'}).status_code,503)
        self.payment.quote_expires_at=datetime.now(timezone.utc)-timedelta(hours=1); db.session.commit()
        self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/quote',data={'_csrf':'test-csrf'}).status_code,409)

    def test_new_market_quote_has_explicit_unused_state(self):
        db.session.delete(self.payment); db.session.commit()
        with patch('market_pricing.quote_from_benchmark',return_value=(2975,datetime.now(timezone.utc)+timedelta(hours=1))):
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/quote',data={'_csrf':'test-csrf'}).status_code,200)
        self.assertEqual(Payment.query.one().status,'quoted')

    def test_reconcile_requires_owner_post_csrf_and_current_approval(self):
        path=f'/contractor/payments/{self.payment.id}/reconcile'
        with patch('billing.retrieve_checkout') as retrieve:
            self.assertEqual(self.client.get(path).status_code,405)
            self.assertEqual(self.client.post(path,data={'_csrf':'wrong'}).status_code,400)
            self.assertEqual(self.client.post(f'/contractor/payments/{self.payment.id+1}/reconcile',data={'_csrf':'test-csrf'}).status_code,404)
            other=Contractor(company_name='Other',contact_name='Owner',email='other@example.com',phone='6125550101',
                zip_codes='55401',service_type='Mold Remediation',active=True,verified=True,is_test=False,password_hash='other-hash')
            db.session.add(other); db.session.commit(); self.login(other)
            self.assertEqual(self.reconcile().status_code,404)
            self.login(self.contractor); self.contractor.active=False; db.session.commit()
            self.assertEqual(self.reconcile().status_code,302); retrieve.assert_not_called()

    def test_disabled_switch_or_mismatched_mode_never_calls_provider(self):
        with patch('billing.retrieve_checkout') as retrieve:
            for values in ({'CHECKOUT_RECONCILIATION_ENABLED':'false'}, {'STRIPE_SECRET_KEY':''}, {'STRIPE_MODE':'invalid'}):
                with patch.dict(os.environ,values):
                    self.assertEqual(self.reconcile().status_code,503)
            self.payment.mode='live'; db.session.commit()
            self.assertEqual(self.reconcile().status_code,409); retrieve.assert_not_called()

    def test_worker_reports_errors_without_replacing_orders_and_accepts_cursor(self):
        with patch('billing.retrieve_checkout',side_effect=stripe.APIConnectionError('synthetic')):
            self.assertEqual(reconcile_batch(limit=1),{'processed':1,'results':{'error':1},'next_after_id':self.payment.id})
        self.assertEqual(reconcile_batch(after_id=self.payment.id)['processed'],0)
        for limit in (0,501,True):
            with self.assertRaises(ValueError): reconcile_batch(limit=limit)
        with patch.dict(os.environ,{'CHECKOUT_RECONCILIATION_ENABLED':'false'}),patch('billing.retrieve_checkout') as retrieve:
            result=app.test_cli_runner().invoke(args=['reconcile-checkouts'])
            self.assertNotEqual(result.exit_code,0); retrieve.assert_not_called()

    def test_billing_status_controls_are_private_and_hidden_when_disabled(self):
        response=self.client.get('/contractor/billing')
        self.assertIn('Check checkout status',response.text)
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertNotIn('PRIVATE NAME',response.text)
        with patch.dict(os.environ,{'CHECKOUT_RECONCILIATION_ENABLED':'false'}):
            self.assertNotIn('Check checkout status',self.client.get('/contractor/billing').text)

    def prepare_expired(self):
        self.payment.status='expired'
        self.payment.quote_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        db.session.commit()

    def refresh_quote(self):
        return self.client.post(f'/contractor/offers/{self.offer.id}/quote',data={'_csrf':'test-csrf'})

    def test_confirmed_expired_session_requotes_with_history_and_new_idempotency_key(self):
        from app import CheckoutQuoteHistory
        self.prepare_expired()
        with patch('billing.retrieve_checkout',return_value=self.snapshot('expired')), \
                patch('market_pricing.quote_from_benchmark',return_value=(2975,datetime.now(timezone.utc)+timedelta(hours=1))):
            self.assertEqual(self.refresh_quote().status_code,200)
        db.session.refresh(self.payment)
        self.assertEqual(self.payment.quote_version,2); self.assertEqual(self.payment.amount_cents,2975)
        self.assertEqual(self.payment.status,'quoted'); self.assertIsNone(self.payment.session_id)
        old=CheckoutQuoteHistory.query.one()
        self.assertEqual((old.quote_version,old.amount_cents,old.session_id,old.status),(1,2500,'cs_test_synthetic','expired'))
        with patch('billing.create_checkout',return_value={'id':'cs_test_revision2','url':'https://checkout.stripe.com/test'}) as create:
            self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/checkout',
                data={'_csrf':'test-csrf','quote_version':'2','amount':'1'}).status_code,303)
            self.assertEqual(create.call_args.kwargs['idempotency_key'],f'lead-payment:{self.payment.id}:v2')
            self.assertEqual(create.call_args.kwargs['metadata']['quote_version'],'2')
            self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['unit_amount'],2975)

    def test_expired_record_requires_actual_provider_expiry_before_replacement(self):
        from app import CheckoutQuoteHistory
        self.prepare_expired()
        for obj in (self.snapshot(),self.snapshot('complete','paid'),self.snapshot('expired',amount_total=1)):
            with patch('billing.retrieve_checkout',return_value=obj):
                self.assertEqual(self.refresh_quote().status_code,409)
        with patch('billing.retrieve_checkout',side_effect=stripe.APIConnectionError('synthetic')):
            self.assertEqual(self.refresh_quote().status_code,503)
        self.assertEqual(CheckoutQuoteHistory.query.count(),0)
        db.session.refresh(self.payment); self.assertEqual(self.payment.quote_version,1)

    def test_expired_replacement_requires_fresh_market_evidence(self):
        from app import CheckoutQuoteHistory
        self.prepare_expired(); self.benchmark.observed_at=datetime.now(timezone.utc)-timedelta(days=2); db.session.commit()
        with patch('billing.retrieve_checkout',return_value=self.snapshot('expired')):
            self.assertEqual(self.refresh_quote().status_code,503)
        self.assertEqual(CheckoutQuoteHistory.query.count(),0)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'expired')

    def test_requote_cannot_overwrite_a_payment_webhook_during_provider_read(self):
        from app import CheckoutQuoteHistory
        self.prepare_expired()
        def expired_after_payment(*args,**kwargs):
            obj=self.snapshot('expired')
            self.assertEqual(self.webhook(self.snapshot('complete','paid',payment_intent='pi_requote_race'),
                kind='checkout.session.completed',identifier='evt_requote_race').status_code,204)
            return obj
        with patch('billing.retrieve_checkout',side_effect=expired_after_payment), \
                patch('market_pricing.quote_from_benchmark',return_value=(2975,datetime.now(timezone.utc)+timedelta(hours=1))):
            self.assertEqual(self.refresh_quote().status_code,409)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'paid')
        self.assertEqual(self.payment.quote_version,1); self.assertEqual(CheckoutQuoteHistory.query.count(),0)

    def test_retired_expiration_replay_cannot_bind_to_a_new_creating_quote(self):
        self.prepare_expired(); old=self.snapshot('expired')
        with patch('billing.retrieve_checkout',return_value=old), \
                patch('market_pricing.quote_from_benchmark',return_value=(2500,datetime.now(timezone.utc)+timedelta(hours=1))):
            self.assertEqual(self.refresh_quote().status_code,200)
        self.payment.status='creating'; db.session.commit()
        self.assertEqual(self.webhook(old,identifier='evt_retired_expired').status_code,204)
        unexpected={**old,'status':'complete','payment_status':'paid','payment_intent':'pi_retired'}
        self.assertEqual(self.webhook(unexpected,kind='checkout.session.completed',identifier='evt_retired_paid').status_code,409)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'creating')
        self.assertIsNone(self.payment.session_id); self.assertFalse(offer_contact_available(self.offer))

    def test_stale_browser_quote_cannot_start_checkout_after_requote(self):
        self.payment.status='quoted'; self.payment.session_id=None; self.payment.quote_version=2; db.session.commit()
        with patch('billing.create_checkout') as create:
            for version in (None,'1','999'):
                data={'_csrf':'test-csrf'}
                if version is not None:data['quote_version']=version
                self.assertEqual(self.client.post(f'/contractor/offers/{self.offer.id}/checkout',data=data).status_code,409)
            create.assert_not_called()

    def test_unlinked_earlier_revision_webhook_cannot_confirm_new_quote(self):
        self.payment.status='creating'; self.payment.session_id=None; self.payment.quote_version=2; db.session.commit()
        obj=self.snapshot('complete','paid',id='cs_old_unknown',payment_intent='pi_old')
        self.assertEqual(self.webhook(obj,kind='checkout.session.completed',identifier='evt_old_revision').status_code,400)
        db.session.refresh(self.payment); self.assertEqual(self.payment.status,'creating')
        self.assertIsNone(self.payment.session_id)

"""Owner matching trials must never assign or reveal unrelated customers."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app import app, db, Contractor, Lead, LeadOffer, Delivery
from contractor_offer_creation import create_next_sequential_offer
from contractor_offer_transactions import accept_contractor_offer
from communications import deliver_pending
from scheduled_matching_worker import process_matching_batch


class MatchingTestModeTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context(); self.ctx.push(); db.drop_all(); db.create_all()
        self.env = patch.dict(os.environ, {
            'EMAIL_TEST_ONLY': 'true', 'EMAIL_TEST_RECIPIENTS': 'consumer@example.com,contractor@example.com',
            'ENABLE_LIVE_MATCHING': 'YES', 'MATCHING_ACTIVATION_UTC': '2026-01-01T00:00:00Z',
            'EMAIL_SENDING_ENABLED': 'true', 'RESEND_API_KEY': 're_synthetic',
            'RESEND_FROM_EMAIL': 'sender@example.com', 'SMS_SENDING_ENABLED': 'false',
        }); self.env.start()
        self.contractor = Contractor(company_name='Synthetic trial', contact_name='Owner',
            email='Contractor@Example.com', phone='6125550100', zip_codes='55401',
            service_type='Mold Remediation', active=True, verified=True, is_test=False)
        self.other = Contractor(company_name='Unrelated', contact_name='Owner',
            email='unrelated@example.com', phone='6125550101', zip_codes='55401',
            service_type='Mold Remediation', active=True, verified=True, is_test=False)
        self.lead = Lead(homeowner_name='Synthetic trial', email='Consumer@Example.com',
            phone='6125550199', zip_code='55401', service_needed='Mold Remediation', status='New')
        self.unrelated = Lead(homeowner_name='Private customer', email='private@example.com',
            phone='6125550198', zip_code='55401', service_needed='Mold Remediation', status='New')
        db.session.add_all([self.contractor, self.other, self.lead, self.unrelated]); db.session.commit()

    def tearDown(self):
        db.session.remove(); self.ctx.pop(); self.env.stop()

    def run_worker(self):
        # SQLite has no PostgreSQL transaction locks. Keep actual selection,
        # offer creation, outbox and acceptance; PostgreSQL CI covers the lock.
        def advance(session, lead, contractors, model, **kwargs):
            return {'expired_offer_ids': [], 'new_offer': create_next_sequential_offer(
                session, lead, contractors, model, **kwargs)}
        with patch('scheduled_matching_worker.advance_sequential_offer', side_effect=advance):
            return process_matching_batch()

    def test_allowed_matching_email_acceptance_and_consumer_notice_without_other_customers(self):
        from consumer_requests import queue_request_update
        result = self.run_worker()
        self.assertEqual((result['processed'], result['created'], result['failed']), (1, 1, 0))
        offer = LeadOffer.query.one()
        self.assertEqual((offer.lead_id, offer.contractor_id), (self.lead.id, self.contractor.id))
        with patch('communications.resend_email', return_value='synthetic-provider-id') as send:
            self.assertEqual(deliver_pending()['sent'], 1)
            self.assertEqual(send.call_args.args[0].recipient, self.contractor.email)
        self.assertIsNotNone(accept_contractor_offer(db.session, offer.id, self.contractor.id))
        queue_request_update(self.lead, 'accepted', offer.id); db.session.commit()
        with patch('communications.resend_email', return_value='synthetic-consumer-id') as send:
            self.assertEqual(deliver_pending()['sent'], 1)
            self.assertEqual(send.call_args.args[0].recipient, self.lead.email)
        self.assertEqual(self.run_worker()['created'], 0)
        self.assertEqual(LeadOffer.query.count(), 1)
        self.assertEqual(Delivery.query.filter_by(status='sent').count(), 2)

    def test_both_sides_must_be_allowlisted_and_old_offer_cannot_be_accepted(self):
        from national_coverage import market_eligible
        self.assertFalse(market_eligible(self.other, self.lead))
        self.assertFalse(market_eligible(self.contractor, self.unrelated))
        offer = LeadOffer(lead_id=self.unrelated.id, contractor_id=self.contractor.id, status='pending',
            offered_at=datetime.now(timezone.utc)-timedelta(seconds=1),
            expires_at=datetime.now(timezone.utc)+timedelta(minutes=15))
        db.session.add(offer); db.session.commit()
        self.assertIsNone(accept_contractor_offer(db.session, offer.id, self.contractor.id))
        self.assertEqual(offer.status, 'pending')

    def test_invalid_allowlists_leave_all_leads_and_existing_offers_untouched(self):
        for value in ('', 'invalid', 'consumer@example.com,'):
            with self.subTest(value=value), patch.dict(os.environ, {'EMAIL_TEST_RECIPIENTS': value}):
                self.assertEqual(self.run_worker()['processed'], 0)
                self.assertEqual(LeadOffer.query.count(), 0)

    def test_activation_excludes_backlog_and_approval_is_still_required(self):
        self.lead.submitted_at = datetime(2025, 12, 31, tzinfo=timezone.utc); db.session.commit()
        self.assertEqual(self.run_worker()['processed'], 0)
        self.lead.submitted_at = datetime.now(timezone.utc); self.contractor.verified = False; db.session.commit()
        self.assertEqual(self.run_worker()['created'], 0)

    def test_normal_mode_keeps_existing_matching_behavior(self):
        with patch.dict(os.environ, {'EMAIL_TEST_ONLY': 'false'}):
            self.assertEqual(self.run_worker()['created'], 2)


if __name__ == '__main__': unittest.main()

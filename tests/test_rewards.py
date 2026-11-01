import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from reward_transactions import define_rewards, issue_credit, consume_credit

class RewardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + self.tmp.name.replace('\\', '/') + '/test.db'
        self.db = SQLAlchemy(self.app)
        self.models = define_rewards(self.db)
        with self.app.app_context():
            self.db.create_all()
            B, _, M, _ = self.models
            self.db.session.add_all([B(id=1, identity_digest='a'*64, verified=True), B(id=2, identity_digest='b'*64, verified=True), B(id=3, identity_digest='c'*64, verified=False)])
            self.db.session.add(M(business_id=1, month='2026-10', used=0))
            self.db.session.commit()
    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.engine.dispose()
        self.tmp.cleanup()
    def credit(self, source, kind='purchase'):
        credit = issue_credit(self.db, self.models, 1, source, kind)
        self.db.session.commit()
        return credit.id
    def test_replay_and_identity(self):
        with self.app.app_context():
            self.credit('payment-1')
            with self.assertRaises(IntegrityError):
                self.credit('payment-1', 'free')
            self.db.session.rollback()
            B = self.models[0]
            self.db.session.add(B(identity_digest='a'*64, verified=True))
            with self.assertRaises(IntegrityError): self.db.session.commit()
            self.db.session.rollback()
            with self.assertRaises(ValueError): issue_credit(self.db, self.models, 3, 'unverified', 'free')
    def test_transfer_rollback_and_reuse(self):
        now = datetime(2026, 10, 15, tzinfo=timezone.utc)
        with self.app.app_context():
            credit = self.credit('entry', 'free')
            with self.assertRaises(ValueError): consume_credit(self.db, self.models, 2, credit, now)
            self.db.session.rollback()
            consume_credit(self.db, self.models, 1, credit, now)
            self.db.session.commit()
            with self.assertRaises(ValueError): consume_credit(self.db, self.models, 1, credit, now)
            self.db.session.rollback()
            self.assertEqual(self.db.session.get(self.models[2], (1, '2026-10')).used, 1)
    def test_combined_limit_and_next_month(self):
        with self.app.app_context():
            ids = [self.credit(str(i), 'free' if i % 2 else 'purchase') for i in range(11)]
            for credit in ids[:10]:
                consume_credit(self.db, self.models, 1, credit, datetime(2026,10,31,tzinfo=timezone.utc))
                self.db.session.commit()
            with self.assertRaises(ValueError): consume_credit(self.db, self.models, 1, ids[10], datetime(2026,10,31,tzinfo=timezone.utc))
            self.db.session.rollback()
            consume_credit(self.db, self.models, 1, ids[10], datetime(2026,11,1,tzinfo=timezone.utc))
            self.db.session.commit()
    def test_concurrent_double_spend(self):
        with self.app.app_context(): credit = self.credit('shared')
        def attempt(_):
            with self.app.app_context():
                try:
                    consume_credit(self.db, self.models, 1, credit, datetime(2026,10,15,tzinfo=timezone.utc))
                    self.db.session.commit()
                    return True
                except ValueError:
                    self.db.session.rollback()
                    return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

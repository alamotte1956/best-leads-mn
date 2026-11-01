import os
import unittest
from unittest.mock import patch
from ci import postgres_concurrency


class CISafetyTests(unittest.TestCase):
    def test_hosted_or_non_test_target_is_rejected_before_any_connection(self):
        for target in ('postgresql://user:dummy@production.example/test_rcusa',
                       'postgresql://user:dummy@127.0.0.1/production',
                       'sqlite:///production.db',
                       'postgresql://user:dummy@127.0.0.1/test_rcusa?host=production.example',
                       'postgresql://user:dummy@127.0.0.1/test_rcusa?dbname=production'):
            with patch.dict(os.environ,{'POSTGRES_TEST_URL':target}),patch('ci.postgres_concurrency.create_engine') as connect:
                with self.assertRaises(ValueError):postgres_concurrency.setUpModule()
                connect.assert_not_called()

    def test_missing_test_database_skips_without_creating_any_connection(self):
        with patch.dict(os.environ,{'POSTGRES_TEST_URL':''}),patch('ci.postgres_concurrency.create_engine') as connect:
            with self.assertRaises(unittest.SkipTest):postgres_concurrency.setUpModule()
            connect.assert_not_called()

import os
import tempfile
import unittest
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
from app import app, db
from national_markets import STATES, enabled, city_slug

class NationalTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
    def test_existing_routes(self):
        for path in ('/', '/health', '/contractor/login', '/services/water-damage'):
            self.assertEqual(self.client.get(path).status_code, 200, path)
    def test_new_markets_disabled(self):
        for slug, info in STATES.items():
            expected = 200 if enabled(slug) else 404
            self.assertEqual(self.client.get('/usa/' + slug).status_code, expected)
            for city in info[2]:
                self.assertEqual(self.client.get('/usa/' + slug + '/' + city_slug(city)).status_code, expected)
    def test_security_boundaries(self):
        self.assertEqual(self.client.get('/admin/national').status_code, 302)
        self.assertEqual(self.client.post('/contractor/rewards/spin', json={'prize': 7}).status_code, 503)
        self.assertEqual(self.client.get('/usa/minnesota/unknown').status_code, 404)
    def test_national_brand(self):
        response = self.client.get('/usa')
        self.assertIn(b'RestorationContractorsMN.com', response.data)
        self.assertIn(b'Restoration Contractors USA', response.data)

if __name__ == '__main__':
    unittest.main()

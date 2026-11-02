import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import time
import unittest
from unittest.mock import patch
from app import app,db
from national_markets import STATES,enabled,city_slug
from state_notices import NOTICES,notice_for
from admin_session_security import current_password_fingerprint


class StateNoticeTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-state-notice-admin'})
        self.env.start();self.ctx=app.app_context();self.ctx.push();db.drop_all();db.create_all()
        self.client=app.test_client()

    def tearDown(self):db.session.remove();self.ctx.pop();self.env.stop()

    def admin(self):
        with self.client.session_transaction() as state:
            state.update(admin_authenticated=True,admin_login_at=time.time()-1,
                admin_password_fingerprint=current_password_fingerprint())

    def test_indiana_is_a_seventh_catalog_state_and_remains_closed(self):
        self.assertEqual(len(STATES),7);self.assertEqual(STATES['indiana'][0],'IN');self.assertFalse(enabled('indiana'))
        self.assertIn('Indiana',self.client.get('/usa').text)
        for path in ['/usa/indiana','/usa/indiana/request','/usa/indiana/contractors/apply',
                     '/usa/indiana/indianapolis','/usa/indiana/services/roof-repair']:
            self.assertEqual(self.client.get(path).status_code,404,path)
        self.assertNotIn('/usa/indiana',self.client.get('/usa/sitemap.xml').text)

    def test_every_state_has_a_distinct_notice_and_public_official_references(self):
        self.assertEqual(set(STATES),set(NOTICES))
        copy=set()
        for slug,market in STATES.items():
            response=self.client.get('/state-notices/'+slug)
            self.assertEqual(response.status_code,200,slug)
            self.assertIn(market[1],response.text)
            self.assertIn('Official resources',response.text)
            self.assertIn('non-waivable legal protections',response.text)
            self.assertEqual(notice_for(market[0])['slug'],slug)
            for _,link in NOTICES[slug]['sources']:self.assertIn(link,response.text)
            if slug!='minnesota': self.assertIn('Future market.',response.text)
            copy.add(NOTICES[slug]['points'])
        self.assertEqual(len(copy),7)
        self.assertEqual(self.client.get('/state-notices/unknown').status_code,404)

    def test_indiana_private_city_and_service_previews_include_its_own_notice(self):
        self.assertEqual(self.client.get('/admin/national/preview/indiana').status_code,403)
        self.admin()
        paths=['/admin/national/preview/indiana']
        paths += ['/admin/national/preview/indiana/'+city_slug(city) for city in STATES['indiana'][2]]
        paths += ['/admin/national/preview/indiana/services/'+service for service in (
            'water-damage','fire-smoke-damage','mold-remediation','storm-hail-damage','roof-repair')]
        for path in paths:
            page=self.client.get(path)
            self.assertEqual(page.status_code,200,path)
            self.assertIn('Indiana: before you hire',page.text)
            self.assertIn('Indiana general-contractor requirements are largely local.',page.text)
            self.assertIn('Requests are closed in Indiana',page.text)
            self.assertIn('no-store',page.headers['Cache-Control'])

    def test_all_state_service_pages_use_their_specific_disclosure(self):
        self.admin()
        for slug,market in STATES.items():
            for service in ('water-damage','fire-smoke-damage','mold-remediation','storm-hail-damage','roof-repair'):
                path='/admin/national/preview/'+slug+'/services/'+service
                self.assertIn(market[1]+': before you hire',self.client.get(path).text,path)

    def test_minnesota_intake_and_privacy_match_the_one_or_three_contractor_choice(self):
        for path in ('/','/signup','/services/roof-repair','/services/water-damage'):
            self.assertIn('Minnesota: before you hire',self.client.get(path).text,path)
        privacy=self.client.get('/privacy').text
        self.assertNotIn('We do not claim to sell',privacy)
        self.assertIn('one or up to three participating contractors',privacy)
        self.assertIn('Contractors may pay us for lead access',privacy)
        self.assertIn('/state-notices',self.client.get('/terms').text)

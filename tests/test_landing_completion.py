"""Public SEO contracts and closed-state service preview boundaries."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import json
from html import unescape
import time
import unittest
from html.parser import HTMLParser
from unittest.mock import patch
from xml.etree import ElementTree
from app import app, db, Lead
from national import STATE_SERVICE_SLUGS
from national_markets import STATES
from restoration_landing_pages import LANDING_PAGES


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.elements=[]; self.json=[]; self.in_json=False; self.feed(html)
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs); self.elements.append((tag,attrs))
        if tag=='script' and attrs.get('type')=='application/ld+json': self.in_json=True
    def handle_endtag(self, tag):
        if tag=='script': self.in_json=False
    def handle_data(self, data):
        if self.in_json: self.json.append(json.loads(data))


class LandingCompletionTests(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()

    def test_ten_minnesota_pages_have_safe_canonicals_metadata_and_geography(self):
        for slug, page in LANDING_PAGES.items():
            with self.subTest(slug=slug):
                response=self.client.get('/services/'+slug,base_url='https://untrusted.example')
                self.assertEqual(response.status_code,200)
                doc=Document(response.text)
                canonical='https://RestorationContractorsMN.com/services/'+slug
                self.assertIn(('link',{'rel':'canonical','href':canonical}),doc.elements)
                self.assertIn(('meta',{'property':'og:url','content':canonical}),doc.elements)
                self.assertEqual(doc.json[0]['url'],canonical)
                self.assertEqual(doc.json[0]['@type'],'WebPage')
                self.assertIn('Minneapolis',response.text);self.assertIn('Saint Paul',response.text)
                self.assertIn(page['overview'],unescape(response.text))
                self.assertEqual(sum(tag=='h1' for tag,_ in doc.elements),1)
                for item in page['scope']:self.assertIn(item,response.text)
        self.assertEqual(self.client.get('/services/not-a-service').status_code,404)

    def test_each_native_service_form_saves_its_catalog_service_and_receipt(self):
        with patch.dict(os.environ,{'EMAIL_SENDING_ENABLED':'false','SMS_SENDING_ENABLED':'false'}),app.app_context():
            db.drop_all();db.create_all()
            try:
                for slug,page in LANDING_PAGES.items():
                    doc=Document(self.client.get('/services/'+slug).text)
                    fields={attrs['name']:attrs.get('value','') for tag,attrs in doc.elements if tag=='input' and attrs.get('type')=='hidden'}
                    self.assertEqual(fields['service_needed'],page['service'])
                    self.assertEqual(fields['state'],'MN')
                    fields.update(name='Synthetic Homeowner',phone='6125550199',zip_code='55401',description='Synthetic route test')
                    response=self.client.post('/api/leads',data=fields)
                    self.assertEqual(response.status_code,302)
                    self.assertTrue(response.headers['Location'].endswith('/request-received'))
                    self.assertEqual(Lead.query.order_by(Lead.id.desc()).first().service_needed,page['service'])
                self.assertEqual(Lead.query.count(),10)
            finally:db.session.remove();db.drop_all()

    def test_all_five_future_states_and_unknown_service_urls_remain_closed(self):
        for state in STATES:
            for slug in STATE_SERVICE_SLUGS:
                response=self.client.get('/usa/'+state+'/services/'+slug)
                self.assertEqual(response.status_code,200 if state=='minnesota' else 404)
        for path in ('/usa/unknown/services/roof-repair','/usa/minnesota/services/unknown'):
            self.assertEqual(self.client.get(path).status_code,404)

    def test_all_thirty_admin_previews_require_auth_and_closed_states_have_no_form(self):
        for state in STATES:
            for slug in STATE_SERVICE_SLUGS:
                self.assertEqual(self.client.get('/admin/national/preview/'+state+'/services/'+slug).status_code,403)
        with patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':'synthetic-test-only'}):
            from admin_session_security import current_password_fingerprint
            with self.client.session_transaction() as state:
                state.update(admin_authenticated=True,admin_login_at=time.time(),admin_password_fingerprint=current_password_fingerprint())
            for state in STATES:
                for slug in STATE_SERVICE_SLUGS:
                    response=self.client.get('/admin/national/preview/'+state+'/services/'+slug)
                    self.assertEqual(response.status_code,200)
                    self.assertIn('no-store',response.headers['Cache-Control'])
                    doc=Document(response.text)
                    self.assertIn(('meta',{'name':'robots','content':'noindex,nofollow'}),doc.elements)
                    self.assertFalse(any(tag=='link' and attrs.get('rel')=='canonical' for tag,attrs in doc.elements))
                    self.assertFalse(doc.json)
                    if state!='minnesota':
                        self.assertIn('Requests are closed',response.text)
                        self.assertFalse(any(tag=='form' for tag,_ in doc.elements))
                        self.assertFalse(any(tag=='a' and (attrs.get('href','').endswith('/request') or '#request' in attrs.get('href','')) for tag,attrs in doc.elements))
                    hero=next(a for t,a in doc.elements if t=='img' and a.get('src','').startswith('/static/images/services/'))
                    with self.client.get(hero['src']) as image:self.assertEqual(image.status_code,200)

    def test_both_sitemaps_exclude_private_and_disabled_states_and_ignore_host_injection(self):
        ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
        response=self.client.get('/sitemap.xml',base_url='https://untrusted.example')
        self.assertEqual(response.mimetype,'application/xml')
        urls=[row.text for row in ElementTree.fromstring(response.data).findall('s:url/s:loc',ns)]
        self.assertEqual(set(urls),{'https://RestorationContractorsMN.com/'}|{'https://RestorationContractorsMN.com/services/'+s for s in LANDING_PAGES})
        response=self.client.get('/sitemap.xml',base_url='https://RestorationContractorsUSA.com')
        self.assertEqual(response.status_code,301);self.assertEqual(response.headers['Location'],'/usa/sitemap.xml')
        response=self.client.get('/usa/sitemap.xml')
        urls=[row.text for row in ElementTree.fromstring(response.data).findall('s:url/s:loc',ns)]
        for slug in STATE_SERVICE_SLUGS:self.assertIn('https://RestorationContractorsUSA.com/usa/minnesota/services/'+slug,urls)
        for state in STATES:
            if state!='minnesota':self.assertFalse(any('/usa/'+state in url for url in urls))
        self.assertFalse(any('/admin/' in url for url in urls))

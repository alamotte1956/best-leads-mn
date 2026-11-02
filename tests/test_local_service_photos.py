import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import unittest
from html.parser import HTMLParser
from app import app
from restoration_landing_pages import LANDING_PAGES


class Images(HTMLParser):
    def __init__(self,html):
        super().__init__();self.images=[];self.sources=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='img':self.images.append(values)
        if tag=='source':self.sources.append(values)


class LocalServicePhotoTests(unittest.TestCase):
    def setUp(self):self.client=app.test_client()

    def test_all_ten_service_pages_use_available_local_illustrations(self):
        for slug in LANDING_PAGES:
            with self.subTest(slug=slug):
                response=self.client.get('/services/'+slug)
                self.assertEqual(response.status_code,200)
                parsed=Images(response.text)
                hero=next(img for img in parsed.images if img.get('class')=='hero-photo')
                self.assertTrue(hero['src'].startswith('/static/images/services/'))
                self.assertIn('AI-generated illustrative image.',response.text)
                self.assertNotIn('images.unsplash.com',response.text)
                with self.client.get(hero['src']) as image:
                    self.assertEqual(image.status_code,200)
                    self.assertEqual(image.mimetype,'image/webp')
                    self.assertEqual(image.data[:4],b'RIFF')
                    self.assertLess(len(image.data),300000)

    def test_approved_brand_logos_keep_png_fallbacks_and_supply_webp(self):
        for origin,brand in (('https://RestorationContractorsMN.com','rcmn'),('https://RestorationContractorsUSA.com','rcusa')):
            with self.subTest(brand=brand):
                response=self.client.get('/',base_url=origin)
                self.assertEqual(response.status_code,200)
                parsed=Images(response.text)
                self.assertTrue(any(img['src'].endswith(brand+'-logo-tm.png') for img in parsed.images))
                self.assertTrue(any(source.get('type')=='image/webp' and source.get('srcset','').endswith(brand+'-logo-tm.webp') for source in parsed.sources))
                with self.client.get('/static/images/'+brand+'-logo-tm.webp') as image:
                    self.assertEqual(image.status_code,200)
                    self.assertEqual(image.mimetype,'image/webp')

    def test_national_hero_has_local_optimized_image_and_original_fallback(self):
        response=self.client.get('/usa');parsed=Images(response.text)
        self.assertIn('/static/images/restoration-professional-hero.png', [i['src'] for i in parsed.images])
        self.assertIn('/static/images/restoration-professional-hero.webp', [i.get('srcset') for i in parsed.sources])
        with self.client.get('/static/images/restoration-professional-hero.webp') as image:
            self.assertEqual(image.status_code,200)
            self.assertLess(len(image.data),150000)


    def test_webp_registration_overrides_incorrect_platform_mime_mapping(self):
        import subprocess
        import sys
        from pathlib import Path
        code = """
import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import mimetypes
mimetypes.add_type('application/octet-stream','.webp')
from app import app
with app.test_client().get('/static/images/rcmn-logo-tm.webp') as response:
    assert response.status_code == 200
    assert response.mimetype == 'image/webp', response.mimetype
print('correct WebP MIME type')
"""
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1],
            capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)

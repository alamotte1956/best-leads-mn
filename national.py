"""Additive national preview; no writes to existing tables or live integrations."""
import time
from functools import wraps
from flask import Blueprint, abort, render_template, session, Response, url_for
from admin_session_security import session_password_valid
from national_markets import STATES, city_slug, enabled

national = Blueprint('national', __name__)


@national.after_request
def private_admin_pages(response):
    from flask import request
    if request.path.startswith('/admin/'):
        from consumer_requests import PRIVATE_HEADERS
        response.headers.update(PRIVATE_HEADERS)
    return response

def administrator(fn):
    @wraps(fn)
    def guarded(*args, **kwargs):
        from admin_session_security import admin_session_valid
        if not admin_session_valid(session):
            abort(403)
        return fn(*args, **kwargs)
    return guarded

@national.get('/usa')
def home():
    return render_national()


def render_national(state=None, city=None, preview=False):
    from market_content import landing_content, SERVICE_GROUPS
    from restoration_landing_pages import LANDING_PAGES
    market = STATES.get(state)
    label = next((c for c in market[2] if city_slug(c) == city), market[1]) if market else None
    path = '/usa' + ('/' + state if state else '') + ('/' + city if city else '')
    return render_template('national.html', states=STATES, enabled=enabled,
        market=market, label=label, state=state, city=city, city_slug=city_slug,
        preview=preview, canonical='https://RestorationContractorsUSA.com' + path,
        request_url='https://RestorationContractorsMN.com/#request' if not market or market[0]=='MN' else url_for('national_intake.request_form',state=state),
        content=landing_content(state, label, bool(city)) if market else None,
        service_groups=SERVICE_GROUPS, service_pages=LANDING_PAGES, state_services=STATE_SERVICE_SLUGS)

@national.get('/usa/<state>')
@national.get('/usa/<state>/<city>')
def landing(state, city=None):
    market = STATES.get(state)
    if not market or (city and city not in {city_slug(c) for c in market[2]}):
        abort(404)
    if not enabled(state):
        abort(404)
    return render_national(state, city)


@national.get('/admin/national/preview/<state>')
@national.get('/admin/national/preview/<state>/<city>')
@administrator
def preview(state, city=None):
    market = STATES.get(state)
    if not market or (city and city not in {city_slug(c) for c in market[2]}):
        abort(404)
    from consumer_requests import PRIVATE_HEADERS
    return render_national(state, city, preview=True), 200, PRIVATE_HEADERS


# Stable service slugs are shared with the existing Minnesota landing pages.
STATE_SERVICE_SLUGS = ('water-damage', 'fire-smoke-damage', 'mold-remediation',
                       'storm-hail-damage', 'roof-repair')


def render_state_service(state, service, preview=False):
    from app import LANDING_PHOTOS
    from restoration_landing_pages import LANDING_PAGES
    from market_content import landing_content
    market = STATES.get(state)
    if not market or service not in STATE_SERVICE_SLUGS:
        abort(404)
    page = LANDING_PAGES[service]
    canonical = 'https://RestorationContractorsUSA.com/usa/' + state + '/services/' + service
    return render_template('national_service.html', market=market, state=state,
        service=service, page=page, preview=preview, is_open=enabled(state),
        canonical=canonical, services=STATE_SERVICE_SLUGS, pages=LANDING_PAGES,
        content=landing_content(state, market[1], False),
        photo=url_for('static', filename='images/services/' + LANDING_PHOTOS[service] + '.webp'),
        request_url='https://RestorationContractorsMN.com/services/' + service + '#request'
                    if market[0] == 'MN' else url_for('national_intake.request_form', state=state))


@national.get('/usa/<state>/services/<service>')
def state_service(state, service):
    if not enabled(state):
        abort(404)
    return render_state_service(state, service)


@national.get('/admin/national/preview/<state>/services/<service>')
@administrator
def preview_service(state, service):
    return render_state_service(state, service, preview=True)


@national.get('/usa/sitemap.xml')
def sitemap():
    from xml.sax.saxutils import escape
    paths = ['/usa']
    for state, market in STATES.items():
        if enabled(state):
            paths.append('/usa/' + state)
            paths.extend('/usa/' + state + '/services/' + service for service in STATE_SERVICE_SLUGS)
            paths.extend('/usa/' + state + '/' + city_slug(city) for city in market[2])
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    xml += ''.join('<url><loc>' + escape('https://RestorationContractorsUSA.com' + path) + '</loc></url>' for path in paths)
    return Response(xml + '</urlset>', mimetype='application/xml')

@national.get('/admin/national')
@administrator
def dashboard():
    from national_coverage import national_report
    return render_template('national_admin.html', states=STATES, enabled=enabled,
        reports=national_report())

@national.get('/leadiq-demo')
def leadiq_demo():
    return render_template('leadiq_demo.html')


@national.post('/contractor/rewards/spin')
def spin():
    # No real prize selection or redemption before official rules and legal approval.
    return {'error': 'Rewards are unavailable pending official rules and legal approval.'}, 503

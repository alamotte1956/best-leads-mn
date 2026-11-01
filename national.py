"""Additive national preview; no writes to existing tables or live integrations."""
import time
from functools import wraps
from flask import Blueprint, abort, render_template, session
from admin_session_security import session_password_valid
from national_markets import STATES, city_slug, enabled

national = Blueprint('national', __name__)

def administrator(fn):
    @wraps(fn)
    def guarded(*args, **kwargs):
        at = session.get('admin_login_at')
        if (not session.get('admin_authenticated') or isinstance(at, bool)
                or not isinstance(at, (int, float)) or not 0 <= time.time() - at <= 3600
                or not session_password_valid(session.get('admin_password_fingerprint'))):
            abort(403)
        return fn(*args, **kwargs)
    return guarded

@national.get('/usa')
def home():
    return render_template('national.html', states=STATES, enabled=enabled)

@national.get('/usa/<state>')
@national.get('/usa/<state>/<city>')
def landing(state, city=None):
    market = STATES.get(state)
    if not market or (city and city not in {city_slug(c) for c in market[2]}):
        abort(404)
    if not enabled(state):
        abort(404)
    label = next((c for c in market[2] if city_slug(c) == city), market[1])
    return render_template('national.html', states=STATES, enabled=enabled,
                           market=market, label=label, state=state, city_slug=city_slug)

@national.get('/admin/national')
@administrator
def dashboard():
    from app import Contractor, Lead
    return render_template('national_admin.html', states=STATES, enabled=enabled,
        contractor_count=Contractor.query.count(), lead_count=Lead.query.count())

@national.post('/contractor/rewards/spin')
def spin():
    # No real prize selection or redemption before official rules and legal approval.
    return {'error': 'Rewards are unavailable pending official rules and legal approval.'}, 503

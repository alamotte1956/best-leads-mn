"""Shared CSRF guard and retirement of administrator-issued password links."""
import secrets
from flask import Blueprint, abort, request, session, render_template

onboarding = Blueprint('onboarding', __name__)


def require_csrf():
    token = request.form.get('_csrf', '')
    if not token or not secrets.compare_digest(token, session.get('_csrf', '')):
        abort(400)


@onboarding.route('/contractor/password-setup/<token>', methods=['GET', 'POST'])
def retired_setup(token):
    # Never look up or consume an old administrator-issued token. Contractors
    # must prove control of their own email through the self-service flow.
    from consumer_requests import PRIVATE_HEADERS
    return render_template('contractor_password_setup.html'), 410, PRIVATE_HEADERS

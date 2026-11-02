"""Administrator-issued, single-use contractor password setup."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, abort, request, session, render_template, redirect, url_for, flash
from sqlalchemy import update
from national import administrator
from contractor_password_security import hash_contractor_password

onboarding = Blueprint('onboarding', __name__)

def require_csrf():
    token = request.form.get('_csrf', '')
    if not token or not secrets.compare_digest(token, session.get('_csrf', '')):
        abort(400)

@onboarding.post('/admin/contractors/<int:contractor_id>/password-setup')
@administrator
def issue_setup(contractor_id):
    from app import db, Contractor, ContractorPasswordSetupToken as Token
    require_csrf()
    contractor = db.session.get(Contractor, contractor_id)
    if not contractor:
        abort(404)
    if not contractor.active or not contractor.verified or contractor.is_test or not contractor.credential_review_current:
        abort(409, 'Approve and verify the contractor before issuing access.')
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    try:
        # A contractor row lock serializes concurrent administrators.
        db.session.query(Contractor).filter_by(id=contractor_id).with_for_update().one()
        db.session.execute(update(Token).where(Token.contractor_id == contractor_id, Token.used_at.is_(None)).values(used_at=now))
        db.session.add(Token(contractor_id=contractor_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=now+timedelta(hours=1)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    response = render_template('contractor_password_setup.html', setup_path=url_for('onboarding.setup_password', token=token))
    return response, 200, {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}

@onboarding.route('/contractor/password-setup/<token>', methods=['GET', 'POST'])
def setup_password(token):
    from app import db, Contractor, ContractorPasswordSetupToken as Token
    if len(token) > 100:
        abort(404)
    error = None
    if request.method == 'POST':
        require_csrf()
        try:
            password = request.form.get('password', '')
            if password != request.form.get('confirm_password', ''):
                raise ValueError('Passwords must match.')
            password_hash = hash_contractor_password(password)
        except ValueError as exc:
            error = str(exc)
        if error is None:
            now = datetime.now(timezone.utc)
            try:
                digest = hashlib.sha256(token.encode()).hexdigest()
                # Lock contractor before token consumption, so reissuing a link and
                # consuming one always acquire locks in the same order.
                row = Token.query.filter_by(token_hash=digest).first()
                if row is None:
                    abort(400, 'This link is invalid or expired.')
                contractor = Contractor.query.filter_by(id=row.contractor_id).with_for_update().one()
                if not contractor.active or not contractor.verified or contractor.is_test or not contractor.credential_review_current:
                    abort(400, 'Account is unavailable.')
                result = db.session.execute(update(Token).where(Token.id == row.id,
                    Token.used_at.is_(None), Token.expires_at > now).values(used_at=now).execution_options(synchronize_session=False))
                if result.rowcount != 1:
                    abort(400, 'This link is invalid or expired.')
                contractor.password_hash = password_hash
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            session.pop('contractor_id', None)
            session.pop('contractor_login_at', None)
            flash('Password saved. You can now sign in.', 'success')
            return redirect(url_for('contractor_login'))
    return render_template('contractor_password_setup.html', error=error), 200, {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}

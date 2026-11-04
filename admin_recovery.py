"""Owner-email recovery; no public response reveals whether a link was issued."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import update
from account_recovery import ACK, ORIGIN, _rate_allowed
from contractor_onboarding import require_csrf

admin_recovery = Blueprint('admin_recovery', __name__)


def define_admin_recovery(db):
    class AdminCredential(db.Model):
        __tablename__ = 'admin_credentials'
        id = db.Column(db.Integer, primary_key=True)
        configuration_binding = db.Column(db.String(64), nullable=False)
        password_hash = db.Column(db.Text, nullable=False)
        __table_args__ = (db.CheckConstraint('id = 1', name='single_admin_credential'),)

    class AdminRecoveryToken(db.Model):
        __tablename__ = 'admin_recovery_tokens'
        id = db.Column(db.Integer, primary_key=True)
        token_hash = db.Column(db.String(64), unique=True, nullable=False)
        subject_binding = db.Column(db.String(64), nullable=False)
        recipient = db.Column(db.String(254), nullable=False)
        delivery_id = db.Column(db.Integer, db.ForeignKey('provider_deliveries.id'), unique=True)
        expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
        used_at = db.Column(db.DateTime(timezone=True))
    return AdminCredential, AdminRecoveryToken


def configuration_binding():
    import os
    from admin_auth import owner_email
    value = owner_email() + ':' + os.environ.get('ADMIN_PASSWORD_HASH', '').strip()
    return hmac.new(str(current_app.config['SECRET_KEY']).encode(), value.encode(), hashlib.sha256).hexdigest()


def effective_password_hash():
    import os
    from flask import has_app_context
    configured = os.environ.get('ADMIN_PASSWORD_HASH', '').strip()
    if not configured or not has_app_context():
        return configured
    from app import db, AdminCredential
    row = db.session.get(AdminCredential, 1, populate_existing=True)
    if row and hmac.compare_digest(row.configuration_binding, configuration_binding()):
        return row.password_hash
    return configured


def subject_binding():
    return hashlib.sha256((configuration_binding() + ':' + effective_password_hash()).encode()).hexdigest()


def current_token(token):
    from admin_auth import owner_email, admin_auth_configured
    if not token or token.used_at or not admin_auth_configured() or not owner_email():
        return False
    expiry = token.expires_at
    if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
    return (expiry > datetime.now(timezone.utc) and token.recipient == owner_email()
            and hmac.compare_digest(token.subject_binding, subject_binding()))


def issue(email):
    from app import db, AdminCredential, AdminRecoveryToken as Token, Delivery
    from admin_auth import owner_email, admin_auth_configured
    from communications import email_recipient_allowed
    if not _rate_allowed('admin', email): return
    if (not admin_auth_configured() or not owner_email() or not hmac.compare_digest(email.encode(), owner_email().encode())
            or not email_recipient_allowed(email)): return
    # The email rate-limit lock serializes owner issuance, including first creation.
    row = db.session.get(AdminCredential, 1)
    if not row:
        row = AdminCredential(id=1, configuration_binding=configuration_binding(), password_hash=effective_password_hash())
        db.session.add(row); db.session.flush()
    db.session.query(AdminCredential).filter_by(id=1).populate_existing().with_for_update().one()
    now = datetime.now(timezone.utc)
    db.session.execute(update(Token).where(Token.used_at.is_(None)).values(used_at=now))
    raw = secrets.token_urlsafe(32)
    token = Token(token_hash=hashlib.sha256(raw.encode()).hexdigest(), subject_binding=subject_binding(),
                  recipient=owner_email(), expires_at=now + timedelta(minutes=20))
    db.session.add(token); db.session.flush()
    link = ORIGIN + url_for('admin_recovery.reset', token=raw)
    delivery = Delivery(event_key=f'admin-recovery:{token.id}', channel='email', recipient=owner_email(),
        subject='Reset your administrator password',
        body='Use this private link to choose a new administrator password:\n\n' + link +
             '\n\nThis link expires in 20 minutes and works once. If you did not request it, ignore this email.')
    db.session.add(delivery); db.session.flush(); token.delivery_id = delivery.id


@admin_recovery.route('/admin/forgot-password', methods=['GET', 'POST'])
def forgot():
    from app import db, valid_email
    if request.method == 'POST':
        require_csrf()
        email = request.form.get('email', '').strip().lower()
        if len(email) > 254 or not valid_email(email):
            return render_template('recovery_request.html', purpose='admin', error='Enter a valid email address.'), 400
        try:
            issue(email); db.session.commit()
        except Exception as error:
            db.session.rollback()
            current_app.logger.error('Administrator recovery request failed (%s)', type(error).__name__)
        flash(ACK, 'success')
        return redirect(url_for('admin_recovery.forgot'), code=303)
    return render_template('recovery_request.html', purpose='admin')


@admin_recovery.route('/admin/reset-password/<token>', methods=['GET', 'POST'])
def reset(token):
    from app import db, AdminCredential, AdminRecoveryToken as Token
    from contractor_password_security import hash_contractor_password
    row = None
    if re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        if request.method == 'POST':
            require_csrf()
            db.session.query(AdminCredential).filter_by(id=1).populate_existing().with_for_update().first()
        row = Token.query.filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).populate_existing().first()
    if not current_token(row):
        db.session.rollback()
        return render_template('recovery_complete.html', purpose='admin', invalid=True), 400
    if request.method == 'POST':
        try:
            password = request.form.get('password', '')
            if password != request.form.get('confirm_password', ''): raise ValueError('Passwords must match.')
            password_hash = hash_contractor_password(password)
        except ValueError as error:
            db.session.rollback()
            return render_template('recovery_complete.html', purpose='admin', error=str(error)), 400
        try:
            now = datetime.now(timezone.utc)
            changed = db.session.execute(update(Token).where(Token.id==row.id, Token.used_at.is_(None), Token.expires_at>now)
                .values(used_at=now).execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                db.session.rollback()
                return render_template('recovery_complete.html', purpose='admin', invalid=True), 400
            credential = db.session.get(AdminCredential, 1)
            credential.configuration_binding = configuration_binding()
            credential.password_hash = password_hash
            db.session.execute(update(Token).where(Token.used_at.is_(None)).values(used_at=now))
            from communications import queue_email
            queue_email(f'admin-recovery-confirmation:{row.id}', row.recipient, 'Your administrator password was changed',
                'Your administrator password was changed. Existing administrator sessions have ended. '
                'If you did not make this change, secure your email account and contact the website operator. Sign in at ' + ORIGIN + '/admin/login')
            db.session.commit()
        except Exception:
            db.session.rollback(); raise
        session.clear()
        return redirect(url_for('admin_login'), code=303)
    return render_template('recovery_complete.html', purpose='admin')


def admin_recovery_notice_current(delivery):
    if not delivery.event_key.startswith('admin-recovery:'): return True
    from app import db, AdminRecoveryToken as Token
    identifier = delivery.event_key.partition(':')[2]
    if not identifier.isdigit(): return False
    token = db.session.get(Token, int(identifier), populate_existing=True)
    return bool(current_token(token) and token.delivery_id == delivery.id and token.recipient == delivery.recipient.strip().lower())

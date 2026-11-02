"""Email possession restores access; public responses never identify an account."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, text, update
from consumer_requests import PRIVATE_HEADERS
from contractor_onboarding import require_csrf

recovery = Blueprint('recovery', __name__)
ORIGIN = 'https://www.restorationcontractorsmn.com'
ACK = 'If an eligible account or request matches that email, a private link will be emailed. Please allow a few minutes and check your spam folder.'


def define_recovery(db):
    class AccessRecoveryToken(db.Model):
        __tablename__ = 'access_recovery_tokens'
        id = db.Column(db.Integer, primary_key=True)
        purpose = db.Column(db.String(16), nullable=False)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id', ondelete='CASCADE'), index=True)
        lead_id = db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'), db.ForeignKey('leads.id', ondelete='CASCADE'), index=True)
        token_hash = db.Column(db.String(64), unique=True, nullable=False)
        subject_binding = db.Column(db.String(64), nullable=False)
        delivery_id = db.Column(db.Integer, db.ForeignKey('provider_deliveries.id', ondelete='CASCADE'), unique=True)
        expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
        used_at = db.Column(db.DateTime(timezone=True))
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        __table_args__ = (db.CheckConstraint("(purpose='contractor' AND contractor_id IS NOT NULL AND lead_id IS NULL) OR (purpose='consumer' AND lead_id IS NOT NULL AND contractor_id IS NULL)",name='recovery_subject_kind'),)
    class AccessRecoveryAttempt(db.Model):
        __tablename__ = 'access_recovery_attempts'
        id = db.Column(db.Integer, primary_key=True)
        identifier_hash = db.Column(db.String(64), nullable=False, index=True)
        attempted_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    return AccessRecoveryToken, AccessRecoveryAttempt


def _digest(value):
    return hmac.new(str(current_app.config['SECRET_KEY']).encode(), value.encode(), hashlib.sha256).hexdigest()


def subject_binding(purpose, subject):
    email = (subject.email or '').strip().lower()
    password = (subject.password_hash or '') if purpose == 'contractor' else ''
    return _digest(f'{purpose}:{subject.id}:{email}:{password}')


def _eligible(purpose, subject):
    return subject is not None and (purpose == 'consumer' or (
        subject.active and subject.verified and not subject.is_test and subject.credential_review_current))


def _subject(token, lock=False):
    from app import Contractor, Lead
    model = Contractor if token.purpose == 'contractor' else Lead
    identifier = token.contractor_id if token.purpose == 'contractor' else token.lead_id
    query = model.query.filter_by(id=identifier).populate_existing()
    return (query.with_for_update() if lock else query).first()


def _current(token, subject):
    if not token or token.used_at or not _eligible(token.purpose, subject): return False
    expiry = token.expires_at
    if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry > datetime.now(timezone.utc) and hmac.compare_digest(token.subject_binding, subject_binding(token.purpose, subject))


def _rate_allowed(purpose, email):
    from app import db, AccessRecoveryAttempt as Attempt
    now = datetime.now(timezone.utc)
    keys = [(_digest(f'recovery-email:{purpose}:{email}'),3),
            (_digest('recovery-client:'+(request.remote_addr or 'unknown')),20)]
    if db.session.get_bind().dialect.name == 'sqlite':
        db.session.execute(text('BEGIN IMMEDIATE'))
    else:
        from contractor_login_transaction_lock import lock_contractor_login_account
        for key, _ in sorted(keys): lock_contractor_login_account(db.session,key)
    for key, limit in keys:
        if Attempt.query.filter(Attempt.identifier_hash==key,Attempt.attempted_at>=now-timedelta(minutes=15)).count() >= limit:
            return False
    for key, _ in keys: db.session.add(Attempt(identifier_hash=key,attempted_at=now))
    Attempt.query.filter(Attempt.attempted_at<now-timedelta(days=1)).delete(synchronize_session=False)
    return True


def _issue(purpose, email):
    from app import db, Contractor, Lead, Delivery, AccessRecoveryToken as Token
    from communications import email_recipient_allowed
    if not _rate_allowed(purpose,email): return
    if not email_recipient_allowed(email): return
    if purpose == 'contractor':
        matches = Contractor.query.filter(func.lower(func.trim(Contractor.email))==email).limit(2).all()
        subject = matches[0] if len(matches)==1 else None
    else:
        subject = Lead.query.filter(func.lower(func.trim(Lead.email))==email).order_by(Lead.submitted_at.desc().nullslast(),Lead.id.desc()).first()
    if not _eligible(purpose,subject): return
    # Issuance and consumption use the same subject-row lock order.
    subject = type(subject).query.filter_by(id=subject.id).populate_existing().with_for_update().one()
    if not _eligible(purpose,subject) or (subject.email or '').strip().lower()!=email: return
    now = datetime.now(timezone.utc)
    field = Token.contractor_id if purpose=='contractor' else Token.lead_id
    db.session.execute(update(Token).where(Token.purpose==purpose,field==subject.id,Token.used_at.is_(None)).values(used_at=now))
    raw = secrets.token_urlsafe(32)
    row = Token(purpose=purpose,token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        subject_binding=subject_binding(purpose,subject),expires_at=now+timedelta(minutes=20),
        **({'contractor_id':subject.id} if purpose=='contractor' else {'lead_id':subject.id}))
    db.session.add(row); db.session.flush()
    endpoint = 'recovery.reset_password' if purpose=='contractor' else 'recovery.open_request'
    link = ORIGIN + url_for(endpoint,token=raw)
    title = 'Reset your contractor password' if purpose=='contractor' else 'Access your restoration request status'
    body = ('Use the private link below to reset your contractor password.' if purpose=='contractor' else
            'Use the private link below to reopen the status of your most recent restoration request matching this email.')
    notice = Delivery(event_key=f'recovery:{row.id}',channel='email',recipient=subject.email,
        subject=title,body=body+'\n\n'+link+'\n\nThis link expires in 20 minutes and can be used once. If you did not request this email, you can ignore it.')
    db.session.add(notice); db.session.flush(); row.delivery_id=notice.id


@recovery.after_request
def private_response(response):
    response.headers.update(PRIVATE_HEADERS)
    return response


def _request_link(purpose):
    from app import db, valid_email
    if request.method=='POST':
        require_csrf()
        email=request.form.get('email','').strip().lower()
        if not valid_email(email) or len(email)>254:
            return render_template('recovery_request.html',purpose=purpose,error='Enter a valid email address.'),400
        try:
            _issue(purpose,email); db.session.commit()
        except Exception as error:
            db.session.rollback()
            current_app.logger.error('Access recovery request failed (%s)',type(error).__name__)
        flash(ACK,'success')
        return redirect(url_for('recovery.forgot_password' if purpose=='contractor' else 'recovery.request_access'),code=303)
    return render_template('recovery_request.html',purpose=purpose)


@recovery.route('/contractor/forgot-password',methods=['GET','POST'])
def forgot_password(): return _request_link('contractor')


@recovery.route('/request-access',methods=['GET','POST'])
def request_access(): return _request_link('consumer')


def _find(raw,purpose):
    from app import AccessRecoveryToken as Token
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',raw): return None
    return Token.query.filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest(),purpose=purpose).first()


def _use_link(raw,purpose):
    from app import db, AccessRecoveryToken as Token, ContractorPasswordSetupToken
    token=_find(raw,purpose)
    subject=_subject(token,lock=request.method=='POST') if token else None
    if not _current(token,subject):
        db.session.rollback()
        return render_template('recovery_complete.html',purpose=purpose,invalid=True),400
    if request.method=='POST':
        require_csrf()
        password_hash=None
        if purpose=='contractor':
            from contractor_password_security import hash_contractor_password
            try:
                password=request.form.get('password','')
                if password!=request.form.get('confirm_password',''): raise ValueError('Passwords must match.')
                password_hash=hash_contractor_password(password)
            except ValueError as error:
                db.session.rollback()
                return render_template('recovery_complete.html',purpose=purpose,error=str(error)),400
        now=datetime.now(timezone.utc)
        try:
            changed=db.session.execute(update(Token).where(Token.id==token.id,Token.used_at.is_(None),Token.expires_at>now).values(used_at=now).execution_options(synchronize_session=False)).rowcount
            if changed!=1: abort(400,'This link is invalid or expired.')
            if purpose=='contractor':
                subject.password_hash=password_hash
                db.session.execute(update(ContractorPasswordSetupToken).where(ContractorPasswordSetupToken.contractor_id==subject.id,ContractorPasswordSetupToken.used_at.is_(None)).values(used_at=now))
                from communications import queue_email
                queue_email(f'recovery-confirmation:{token.id}',subject.email,'Your contractor password was changed',
                    'Your contractor password was changed. If you did not make this change, contact the website administrator. Sign in at '+ORIGIN+'/contractor/login')
            db.session.commit()
        except Exception:
            db.session.rollback(); raise
        if purpose=='consumer':
            from consumer_requests import remember_request
            remember_request(subject.id)
            session['request_access_binding']=subject_binding('consumer',subject)
            return redirect(url_for('consumer_requests.status'),code=303)
        for key in ('contractor_id','contractor_login_at','contractor_password_fingerprint'): session.pop(key,None)
        flash('Password saved. Sign in with your new password.','success')
        return redirect(url_for('contractor_login'),code=303)
    return render_template('recovery_complete.html',purpose=purpose)


@recovery.route('/contractor/reset-password/<token>',methods=['GET','POST'])
def reset_password(token): return _use_link(token,'contractor')


@recovery.route('/request-access/<token>',methods=['GET','POST'])
def open_request(token): return _use_link(token,'consumer')


def recovery_notice_current(delivery):
    if not delivery.event_key.startswith('recovery:'): return True
    from app import db, AccessRecoveryToken as Token
    identifier=delivery.event_key.partition(':')[2]
    if not identifier.isdigit(): return False
    token=db.session.get(Token,int(identifier))
    subject=_subject(token) if token else None
    return bool(token and token.delivery_id==delivery.id and _current(token,subject)
                and (subject.email or '').strip().lower()==(delivery.recipient or '').strip().lower())

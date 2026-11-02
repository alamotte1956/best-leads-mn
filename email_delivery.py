"""Signed Resend delivery events and durable recipient suppression.

Signature format follows https://docs.svix.com/receiving/verifying-payloads/how-manual.
No email bodies or raw webhook payloads are retained here.
"""
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone

from flask import Blueprint, abort, request
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

email_delivery = Blueprint('email_delivery', __name__)
EVENT_STATUSES = {
    'email.sent': 'sent', 'email.delivery_delayed': 'delivery_delayed',
    'email.delivered': 'delivered', 'email.failed': 'failed',
    'email.bounced': 'bounced', 'email.suppressed': 'suppressed',
    'email.complained': 'complained',
}
STATUS_RANK = {value: rank for rank, value in enumerate(
    ('sent', 'delivery_delayed', 'delivered', 'failed', 'bounced', 'suppressed', 'complained'), 1)}


def define_email_tracking(db):
    class ResendEvent(db.Model):
        __tablename__ = 'resend_delivery_events'
        id = db.Column(db.String(150), primary_key=True)
        delivery_id = db.Column(db.Integer, db.ForeignKey('provider_deliveries.id'), nullable=False)
        provider_id = db.Column(db.String(150), nullable=False)
        event_type = db.Column(db.String(40), nullable=False)
        occurred_at = db.Column(db.DateTime(timezone=True), nullable=False)
        received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())

    class EmailSuppression(db.Model):
        __tablename__ = 'email_suppressions'
        email = db.Column(db.String(255), primary_key=True)
        reason = db.Column(db.String(30), nullable=False)
        source_event_id = db.Column(db.String(150), db.ForeignKey('resend_delivery_events.id'), nullable=False)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    return ResendEvent, EmailSuppression


def canonical_email(value):
    return value.strip().lower() if isinstance(value, str) else ''


def email_suppressed(email):
    from app import EmailSuppression
    normalized = canonical_email(email)
    return not normalized or EmailSuppression.query.filter_by(email=normalized).first() is not None


def verify_signature(payload, headers, secret, now=None):
    """Verify raw bytes, signed attempt timestamp and every supported v1 signature."""
    try:
        if not secret.startswith('whsec_'):
            raise ValueError()
        key = base64.b64decode(secret[6:], validate=True)
        if len(key) < 16:
            raise ValueError()
    except (ValueError, binascii.Error):
        raise RuntimeError('Configure a valid Resend webhook signing secret.') from None
    identifier = headers.get('svix-id', '')
    timestamp = headers.get('svix-timestamp', '')
    signatures = headers.get('svix-signature', '')
    if (not re.fullmatch(r'[A-Za-z0-9_-]{1,150}', identifier)
            or not re.fullmatch(r'[0-9]{1,12}', timestamp)
            or abs((time.time() if now is None else now) - int(timestamp)) > 300
            or len(signatures) > 4096):
        return False
    expected = hmac.new(key, f'{identifier}.{timestamp}.'.encode() + payload, hashlib.sha256).digest()
    for item in signatures.split():
        version, separator, signature = item.partition(',')
        if version == 'v1' and separator:
            try:
                if hmac.compare_digest(expected, base64.b64decode(signature, validate=True)):
                    return True
            except (ValueError, binascii.Error):
                pass
    return False


@email_delivery.post('/webhooks/resend')
def resend_status():
    from app import db, Delivery, ResendEvent, EmailSuppression
    secret = os.environ.get('RESEND_WEBHOOK_SECRET', '')
    if not secret:
        abort(503, 'Resend delivery tracking is not configured.')
    payload = request.stream.read(262145)
    if len(payload) > 262144:
        abort(413)
    try:
        valid = verify_signature(payload, request.headers, secret)
    except RuntimeError:
        abort(503, 'Resend delivery tracking is not configured.')
    if not valid:
        abort(400, 'Invalid Resend webhook signature.')
    try:
        event = json.loads(payload)
        if not isinstance(event, dict):
            raise ValueError()
        kind = event.get('type')
        if not isinstance(kind, str):
            raise ValueError()
        if kind not in EVENT_STATUSES:
            return '', 204
        data = event['data']
        provider_id = data['email_id']
        recipients = data['to']
        occurred_at = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
        if (not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 150
                or not isinstance(recipients, list) or len(recipients) != 1
                or not canonical_email(recipients[0]) or occurred_at.tzinfo is None):
            raise ValueError()
        tags = data.get('tags') or {}
        if not isinstance(tags, dict):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        abort(400, 'Invalid Resend delivery event.')
    identifier = request.headers['svix-id']
    if db.session.get(ResendEvent, identifier):
        return '', 204
    try:
        delivery = Delivery.query.filter_by(channel='email', provider_id=provider_id).with_for_update().first()
        reference = tags.get('delivery_id')
        if not delivery and isinstance(reference, str) and reference.isascii() and reference.isdigit() and len(reference) < 12:
            delivery = Delivery.query.filter_by(id=int(reference), channel='email').with_for_update().first()
            if delivery and (delivery.provider_id is not None or delivery.status not in ('sending', 'uncertain')):
                abort(409, 'The delivery is not awaiting provider confirmation.')
        if not delivery:
            # Other applications can share a Resend account; never mutate unrelated mail.
            return '', 204
        if ((reference is not None and reference != str(delivery.id))
                or canonical_email(recipients[0]) != canonical_email(delivery.recipient)):
            abort(400, 'Resend delivery details do not match the queued email.')
        db.session.add(ResendEvent(id=identifier, delivery_id=delivery.id, provider_id=provider_id,
            event_type=kind, occurred_at=occurred_at.astimezone(timezone.utc)))
        db.session.flush()
        status = EVENT_STATUSES[kind]
        permanent_bounce = False
        if kind == 'email.bounced':
            bounce = data.get('bounce') or {}
            if not isinstance(bounce, dict):
                abort(400)
            permanent_bounce = bounce.get('type') == 'Permanent'
            if bounce.get('type') == 'Temporary':
                status = 'delivery_delayed'
        # Conditional updates also protect SQLite, where FOR UPDATE is unavailable.
        lower_statuses = [name for name, rank in STATUS_RANK.items() if rank < STATUS_RANK[status]]
        lower_statuses += ['sending', 'uncertain']
        db.session.execute(update(Delivery).where(Delivery.id == delivery.id,
            Delivery.status.in_(lower_statuses)).values(status=status))
        db.session.execute(update(Delivery).where(Delivery.id == delivery.id,
            Delivery.provider_id.is_(None)).values(provider_id=provider_id))
        if permanent_bounce or kind in ('email.complained', 'email.suppressed'):
            dialect = db.session.get_bind().dialect.name
            if dialect == 'postgresql':
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
            db.session.execute(insert(EmailSuppression).values(
                email=canonical_email(delivery.recipient), reason=status, source_event_id=identifier
            ).on_conflict_do_nothing(index_elements=['email']))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if db.session.get(ResendEvent, identifier):
            return '', 204
        raise
    except Exception:
        db.session.rollback()
        raise
    return '', 204

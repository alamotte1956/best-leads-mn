"""SMS opt-out processing. Does not send messages."""

from datetime import datetime, timezone

STOP_KEYWORDS = frozenset({
    "STOP",
    "STOPALL",
    "UNSUBSCRIBE",
    "CANCEL",
    "END",
    "QUIT",
})


def is_stop_request(message):
    """Recognize standard SMS opt-out commands."""
    return (message or "").strip().upper() in STOP_KEYWORDS


def revoke_sms_consent(contractor, received_at=None):
    """Revoke consent for a contractor without changing approval status."""
    contractor.sms_consent = False
    contractor.sms_opted_out_at = received_at or datetime.now(timezone.utc)
    return contractor

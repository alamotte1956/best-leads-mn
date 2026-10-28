"""Safety configuration for outbound SMS.

SMS sending is disabled unless explicitly enabled.
"""

import os


def sms_sending_enabled():
    """Return True only for an explicit enable setting."""
    value = os.environ.get(
        "SMS_SENDING_ENABLED", ""
    ).strip().lower()

    return value == "true"


def require_sms_sending_enabled():
    """Raise an error when outbound SMS is disabled."""
    if not sms_sending_enabled():
        raise RuntimeError(
            "Outbound SMS sending is disabled."
        )

    return True

"""Security helpers for incoming Twilio webhooks."""

import os
from twilio.request_validator import RequestValidator


def validate_twilio_request(url, form_data, signature):
    """Verify a Twilio webhook signature; fail closed."""
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()

    if not token or not signature or not url:
        return False

    validator = RequestValidator(token)

    return validator.validate(
        url,
        form_data,
        signature
    )

"""Guarded SMS dispatch. No Twilio integration is included."""

from sms_config import require_sms_sending_enabled
from sms_delivery_guard import authorize_sms_delivery


def dispatch_contractor_sms(
    contractor_id,
    zip_code,
    service_needed,
    message,
    load_contractor,
    sms_eligible,
    send_message,
):
    """Authorize a contractor notification before dispatch.

    This function does not create a Twilio client.
    The caller supplies the message delivery function.
    """
    require_sms_sending_enabled()

    if not callable(send_message):
        raise TypeError("send_message must be callable")

    if not isinstance(message, str) or not message.strip():
        raise ValueError("SMS message must not be empty")

    contractor = authorize_sms_delivery(
        contractor_id,
        zip_code,
        service_needed,
        load_contractor,
        sms_eligible,
    )

    if contractor is None:
        return {
            "status": "blocked",
            "reason": "contractor_not_eligible",
        }

    return send_message(contractor.phone, message)

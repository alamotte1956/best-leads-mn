"""Final authorization checks for contractor SMS delivery.

This module does not send messages.
"""

from matching import contractor_matches


def authorize_sms_delivery(
    contractor_id,
    zip_code,
    service_needed,
    load_contractor,
    sms_eligible,
):
    """Return the eligible contractor or None.

    The caller must supply a fresh database lookup and the
    application's authoritative SMS eligibility function.

    This check must run immediately before any future SMS
    provider request. It does not eliminate concurrent
    opt-out races or replace provider-side suppression.
    """
    if not callable(load_contractor):
        raise TypeError("load_contractor must be callable")

    if not callable(sms_eligible):
        raise TypeError("sms_eligible must be callable")

    if contractor_id is None:
        return None

    contractor = load_contractor(contractor_id)

    if contractor is None:
        return None

    if not contractor_matches(
        contractor,
        zip_code,
        service_needed,
    ):
        return None

    if not sms_eligible(contractor):
        return None

    return contractor

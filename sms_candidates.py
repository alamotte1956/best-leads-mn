"""Select eligible SMS candidates without sending messages."""

from matching import contractor_matches


def find_sms_candidates(
    contractors,
    zip_code,
    service_needed,
    sms_eligible,
):
    """Return matching contractors who also pass SMS eligibility.

    sms_eligible must be the application's authoritative
    contractor_sms_eligible function.
    """
    if not callable(sms_eligible):
        raise TypeError("sms_eligible must be callable")

    return [
        contractor
        for contractor in contractors
        if contractor_matches(
            contractor,
            zip_code,
            service_needed,
        )
        and sms_eligible(contractor)
    ]

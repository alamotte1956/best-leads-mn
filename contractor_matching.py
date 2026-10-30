"""Preview-only contractor matching.

No database writes, SMS messages, assignments, or payments.
"""


def normalize_service(value):
    return " ".join(str(value or "").strip().casefold().split())


def normalize_zip(value):
    return str(value or "").strip()


def contractor_matches(contractor, lead, additional_services=None):
    """Return True when an approved contractor matches a lead."""

    if contractor.active is not True:
        return False

    if contractor.verified is not True:
        return False

    if contractor.is_test is not False:
        return False

    requested_service = normalize_service(lead.service_needed)

    services = {normalize_service(contractor.service_type)}

    for service in additional_services or []:
        services.add(normalize_service(service))

    if not requested_service or requested_service not in services:
        return False

    homeowner_zip = normalize_zip(lead.zip_code)

    contractor_zips = {
        normalize_zip(value)
        for value in (contractor.zip_codes or "").split(",")
    }

    if not homeowner_zip or homeowner_zip not in contractor_zips:
        return False

    return True

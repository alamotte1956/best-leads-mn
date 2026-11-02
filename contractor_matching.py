"""Preview-only contractor matching.

No database writes, SMS messages, assignments, or payments.
"""


def normalize_service(value):
    return " ".join(str(value or "").strip().casefold().split())


def normalize_zip(value):
    return str(value or "").strip()


def contractor_matches(contractor, lead, additional_services=None):
    """Return True when an approved contractor matches a lead."""
    status=getattr(lead,'status','New')
    # SQLAlchemy applies the New default only when an unsaved preview is flushed.
    if status is None and getattr(lead,'id',None) is None:
        status='New'
    if status!='New':
        return False

    if contractor.active is not True:
        return False

    if contractor.verified is not True:
        return False

    if contractor.is_test is not False:
        return False

    if not getattr(contractor, 'credential_review_current', True):
        return False

    from national_coverage import lead_state, market_eligible, minnesota_origin
    if not market_eligible(contractor, lead):
        return False
    # Each additional state has its own reviewed services and exact ZIP coverage.
    # Legacy Minnesota coverage and service fields retain their existing behavior.
    if lead_state(lead) != 'MN' or not minnesota_origin(contractor):
        return True

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

"""Contractor matching rules. No messages are sent from this module."""

def normalize_service(value):
    return " ".join((value or "").strip().lower().split())


def contractor_matches(contractor, zip_code, service_needed):
    if getattr(contractor, "is_test", True):
        return False

    if not contractor.active or not contractor.verified:
        return False

    covered_zips = {
        value.strip()
        for value in (contractor.zip_codes or "").split(",")
        if value.strip()
    }

    if zip_code not in covered_zips:
        return False

    return normalize_service(contractor.service_type) == normalize_service(service_needed)


def find_matching_contractors(contractors, zip_code, service_needed):
    return [
        contractor
        for contractor in contractors
        if contractor_matches(contractor, zip_code, service_needed)
    ]

from contractor_password_security import verify_contractor_password


def normalize_contractor_email(email):
    if not isinstance(email, str):
        return None

    normalized = email.strip().lower()

    if not normalized or len(normalized) > 254:
        return None

    if "@" not in normalized:
        return None

    return normalized


def contractor_login_allowed(contractor, password):
    if contractor is None:
        return False

    if not isinstance(password, str) or not password:
        return False

    if not contractor.active:
        return False

    if not contractor.verified:
        return False

    if getattr(contractor, "is_test", False):
        return False

    password_hash = getattr(contractor, "password_hash", None)

    if not password_hash:
        return False

    return verify_contractor_password(password_hash, password)

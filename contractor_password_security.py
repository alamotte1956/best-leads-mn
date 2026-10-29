from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


def hash_contractor_password(password):
    if not isinstance(password, str):
        raise ValueError("Password must be text.")

    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")

    if len(password) > 1024:
        raise ValueError("Password is too long.")

    return generate_password_hash(
        password,
        method="scrypt",
    )


def verify_contractor_password(password_hash, password):
    if not password_hash or not isinstance(password, str):
        return False

    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False

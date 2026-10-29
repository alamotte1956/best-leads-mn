from sqlalchemy import select, func

from contractor_login_security import (
    normalize_contractor_email,
    contractor_login_allowed,
)
from contractor_login_db_limit import (
    account_key,
    check_login_allowed,
    record_login_failure,
    record_login_success,
)
from contractor_login_transaction_lock import (
    lock_contractor_login_account,
)


def authenticate_contractor(
    session,
    contractor_model,
    email,
    password,
    lock_secret,
):
    """
    Authenticate a contractor inside one database transaction.

    The caller must commit on completion or roll back on error.
    Do not grant a Flask login session before the commit succeeds.

    Returns contractor on success, otherwise None.
    """

    if not isinstance(lock_secret, str) or len(lock_secret) < 32:
        raise ValueError("A stable server-side lock secret is required")

    try:
        normalized_email = normalize_contractor_email(email)
    except (ValueError, TypeError):
        return None

    if not isinstance(password, str) or not password:
        return None

    key = account_key(normalized_email, lock_secret)

    # Serialize authentication attempts for this email.
    # This also works when no login-attempt row exists.
    lock_contractor_login_account(session, key)

    if not check_login_allowed(session, key):
        return None

    contractor = session.execute(
        select(contractor_model).where(
            func.lower(contractor_model.email) == normalized_email
        )
    ).scalar_one_or_none()

    if contractor_login_allowed(contractor, password):
        record_login_success(session, key)
        return contractor

    record_login_failure(session, key)
    return None

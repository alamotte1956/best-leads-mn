from sqlalchemy import text


def lock_contractor_login_account(session, account_key_hash):
    """
    Acquire a PostgreSQL transaction-scoped advisory lock.

    The caller must acquire this lock before checking the
    account lockout, verifying credentials, or recording
    a login result.

    The lock is released automatically when the database
    transaction commits or rolls back.
    """

    if (
        not isinstance(account_key_hash, str)
        or len(account_key_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in account_key_hash
        )
    ):
        raise ValueError("Valid SHA-256 account key required")

    session.execute(
        text("""
            SELECT pg_advisory_xact_lock(
                hashtextextended(:account_key_hash, 0)
            )
        """),
        {"account_key_hash": account_key_hash}
    )

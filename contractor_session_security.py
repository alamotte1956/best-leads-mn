from datetime import datetime, timedelta, timezone


CONTRACTOR_SESSION_MINUTES = 60


def create_contractor_session_data(contractor_id, now=None):
    if isinstance(contractor_id, bool) or not isinstance(contractor_id, int):
        raise ValueError("Invalid contractor ID.")

    if contractor_id <= 0:
        raise ValueError("Invalid contractor ID.")

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("Session time must be timezone-aware.")

    now = now.astimezone(timezone.utc)

    return {
        "contractor_id": contractor_id,
        "contractor_login_at": now.isoformat()
    }


def contractor_session_valid(session_data, contractor, now=None):
    if not isinstance(session_data, dict):
        return False

    if contractor is None:
        return False

    contractor_id = session_data.get("contractor_id")

    if isinstance(contractor_id, bool) or not isinstance(contractor_id, int):
        return False

    if contractor_id <= 0 or contractor_id != contractor.id:
        return False

    if not getattr(contractor, "active", False):
        return False

    if not getattr(contractor, "verified", False):
        return False

    if getattr(contractor, "is_test", False):
        return False

    if not getattr(contractor, "password_hash", None):
        return False

    try:
        login_at = datetime.fromisoformat(
            session_data["contractor_login_at"]
        )
    except (KeyError, TypeError, ValueError):
        return False

    if login_at.tzinfo is None:
        return False

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        return False

    now = now.astimezone(timezone.utc)
    login_at = login_at.astimezone(timezone.utc)

    if login_at > now:
        return False

    if now >= login_at + timedelta(
        minutes=CONTRACTOR_SESSION_MINUTES
    ):
        return False

    return True

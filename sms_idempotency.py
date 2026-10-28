"""Identifiers for deduplicating contractor SMS notifications.

Actual duplicate prevention requires durable database storage
with a unique constraint on the notification identifier.
"""


def notification_key(lead_id, contractor_id):
    """Return a stable identifier for one lead/contractor pair."""
    if type(lead_id) is not int or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer")

    if type(contractor_id) is not int or contractor_id <= 0:
        raise ValueError("contractor_id must be a positive integer")

    return f"lead:{lead_id}:contractor:{contractor_id}:sms:v1"

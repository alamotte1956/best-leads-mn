"""Temporary administrator login-attempt protection."""

import time
from collections import defaultdict
from threading import Lock

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 900

_attempts = defaultdict(list)
_lock = Lock()


def is_locked(identifier):
    now = time.monotonic()

    with _lock:
        attempts = [
            t for t in _attempts.get(identifier, [])
            if now - t < LOCKOUT_SECONDS
        ]

        if attempts:
            _attempts[identifier] = attempts
        else:
            _attempts.pop(identifier, None)

        return len(attempts) >= MAX_ATTEMPTS


def record_failure(identifier):
    now = time.monotonic()

    with _lock:
        attempts = [
            t for t in _attempts.get(identifier, [])
            if now - t < LOCKOUT_SECONDS
        ]

        attempts.append(now)
        _attempts[identifier] = attempts

        return len(attempts) >= MAX_ATTEMPTS


def clear_failures(identifier):
    with _lock:
        _attempts.pop(identifier, None)

"""Persistent administrator login-attempt records."""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy


def define_admin_login_attempt(db: SQLAlchemy):
    class AdminLoginAttempt(db.Model):
        __tablename__ = "admin_login_attempts"

        id = db.Column(db.Integer, primary_key=True)

        client_identifier = db.Column(
            db.String(128),
            nullable=False,
            index=True,
        )

        attempted_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )

    return AdminLoginAttempt

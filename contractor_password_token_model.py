def define_contractor_password_setup_token(db):
    class ContractorPasswordSetupToken(db.Model):
        __tablename__ = "contractor_password_setup_tokens"

        id = db.Column(db.BigInteger, primary_key=True)

        contractor_id = db.Column(
            db.Integer,
            db.ForeignKey("contractors.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )

        token_hash = db.Column(
            db.String(64),
            nullable=False,
            unique=True
        )

        expires_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False,
            index=True
        )

        used_at = db.Column(
            db.DateTime(timezone=True),
            nullable=True
        )

        created_at = db.Column(
            db.DateTime(timezone=True),
            nullable=False,
            server_default=db.func.current_timestamp()
        )

    return ContractorPasswordSetupToken

"""Additive encrypted QuickBooks credentials, OAuth attempts and export audit."""
def define_quickbooks(db):
    class QuickBooksConnection(db.Model):
        __tablename__='quickbooks_connections'
        id=db.Column(db.Integer,primary_key=True)
        environment=db.Column(db.String(12),unique=True,nullable=False)
        realm_id=db.Column(db.String(30),nullable=False)
        company_name=db.Column(db.String(255),nullable=False)
        client_binding=db.Column(db.String(64),nullable=False)
        encrypted_tokens=db.Column(db.Text)
        status=db.Column(db.String(20),nullable=False,default='connected')
        confirmed_at=db.Column(db.DateTime(timezone=True))
        created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        __table_args__=(db.CheckConstraint("environment in ('sandbox','production')",name='qbo_connection_environment'),)
    class QuickBooksOAuthAttempt(db.Model):
        __tablename__='quickbooks_oauth_attempts'
        id=db.Column(db.Integer,primary_key=True)
        state_hash=db.Column(db.String(64),unique=True,nullable=False)
        browser_hash=db.Column(db.String(64),nullable=False)
        admin_fingerprint=db.Column(db.String(64),nullable=False)
        client_binding=db.Column(db.String(64),nullable=False)
        environment=db.Column(db.String(12),nullable=False)
        expires_at=db.Column(db.DateTime(timezone=True),nullable=False)
        consumed_at=db.Column(db.DateTime(timezone=True))
    class QuickBooksExport(db.Model):
        __tablename__='quickbooks_exports'
        id=db.Column(db.Integer,primary_key=True)
        environment=db.Column(db.String(12),nullable=False)
        realm_id=db.Column(db.String(30),nullable=False)
        finance_entry_id=db.Column(db.Integer,db.ForeignKey('owner_finance_entries.id'),nullable=False)
        request_id=db.Column(db.String(50),unique=True,nullable=False)
        payload_json=db.Column(db.Text,nullable=False)
        source_hash=db.Column(db.String(64),nullable=False)
        status=db.Column(db.String(20),nullable=False)
        external_id=db.Column(db.String(30))
        created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        completed_at=db.Column(db.DateTime(timezone=True))
        __table_args__=(db.UniqueConstraint('environment','finance_entry_id',name='qbo_expense_once_per_environment'),
            db.CheckConstraint("status in ('sending','sent','uncertain')",name='qbo_export_status'),)
    return QuickBooksConnection,QuickBooksOAuthAttempt,QuickBooksExport

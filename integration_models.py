"""Additive provider integration tables; hosted schema migration is explicit."""
def define_integrations(db):
    class Delivery(db.Model):
        __tablename__ = 'provider_deliveries'
        id = db.Column(db.Integer, primary_key=True)
        event_key = db.Column(db.String(180), unique=True, nullable=False)
        channel = db.Column(db.String(10), nullable=False)
        recipient = db.Column(db.String(255), nullable=False)
        subject = db.Column(db.String(150), nullable=False)
        body = db.Column(db.Text, nullable=False)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'))
        offer_id = db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'), db.ForeignKey('lead_offers.id'))
        status = db.Column(db.String(30), nullable=False, default='pending')
        provider_id = db.Column(db.String(150), unique=True)
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    class Payment(db.Model):
        __tablename__ = 'lead_payments'
        id = db.Column(db.Integer, primary_key=True)
        offer_id = db.Column(db.BigInteger().with_variant(db.Integer,'sqlite'), db.ForeignKey('lead_offers.id'), unique=True, nullable=False)
        contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False)
        amount_cents = db.Column(db.Integer, nullable=False)
        currency = db.Column(db.String(3), nullable=False)
        price_id = db.Column(db.String(150), nullable=False)
        session_id = db.Column(db.String(150), unique=True)
        payment_intent = db.Column(db.String(150), unique=True)
        status = db.Column(db.String(30), nullable=False, default='creating')
        paid_at = db.Column(db.DateTime(timezone=True))
        refunded_cents = db.Column(db.Integer, nullable=False, default=0)
        __table_args__ = (db.CheckConstraint('amount_cents > 0 AND refunded_cents >= 0 AND refunded_cents <= amount_cents'),)
    class ProviderEvent(db.Model):
        __tablename__ = 'provider_events'
        id = db.Column(db.String(150), primary_key=True)
        received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
    class LeadPrice(db.Model):
        __tablename__ = 'lead_price_catalog'
        id = db.Column(db.Integer, primary_key=True)
        state_code = db.Column(db.String(2), nullable=False)
        service_name = db.Column(db.String(100), nullable=False)
        mode = db.Column(db.String(10), nullable=False)
        stripe_price_id = db.Column(db.String(150), nullable=False)
        __table_args__ = (db.UniqueConstraint('state_code','service_name','mode',name='lead_price_state_service_mode'),)
    return Delivery, Payment, ProviderEvent, LeadPrice

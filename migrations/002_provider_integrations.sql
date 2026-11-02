-- Additive PostgreSQL provider integration schema. Staging review required.
BEGIN;
CREATE TABLE IF NOT EXISTS provider_deliveries (
 id SERIAL PRIMARY KEY, event_key VARCHAR(180) NOT NULL UNIQUE,
 channel VARCHAR(10) NOT NULL, recipient VARCHAR(255) NOT NULL,
 subject VARCHAR(150) NOT NULL, body TEXT NOT NULL,
 contractor_id INTEGER REFERENCES contractors(id), offer_id BIGINT REFERENCES lead_offers(id),
 status VARCHAR(30) NOT NULL, provider_id VARCHAR(150) UNIQUE,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS lead_payments (
 id SERIAL PRIMARY KEY, offer_id BIGINT NOT NULL UNIQUE REFERENCES lead_offers(id),
 contractor_id INTEGER NOT NULL REFERENCES contractors(id), amount_cents INTEGER NOT NULL,
 currency VARCHAR(3) NOT NULL, price_id VARCHAR(150) NOT NULL,
 session_id VARCHAR(150) UNIQUE, payment_intent VARCHAR(150) UNIQUE,
 status VARCHAR(30) NOT NULL, paid_at TIMESTAMP WITH TIME ZONE,
 refunded_cents INTEGER NOT NULL DEFAULT 0,
 CHECK (amount_cents > 0 AND refunded_cents >= 0 AND refunded_cents <= amount_cents)
);
CREATE TABLE IF NOT EXISTS provider_events (
 id VARCHAR(150) PRIMARY KEY, received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;

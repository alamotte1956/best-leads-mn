-- Additive homeowner status notices; no existing lead columns are changed.
BEGIN;
CREATE TABLE IF NOT EXISTS consumer_request_updates (
 id SERIAL PRIMARY KEY, lead_id BIGINT NOT NULL REFERENCES leads(id),
 offer_id BIGINT REFERENCES lead_offers(id),
 delivery_id INTEGER NOT NULL UNIQUE REFERENCES provider_deliveries(id),
 status VARCHAR(20) NOT NULL CHECK(status IN ('accepted','closed','cancelled')),
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT consumer_update_lead_status UNIQUE(lead_id,status)
);
CREATE INDEX IF NOT EXISTS ix_consumer_request_updates_lead_id ON consumer_request_updates(lead_id);
COMMIT;

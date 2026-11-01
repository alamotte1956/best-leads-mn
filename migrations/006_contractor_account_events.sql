-- Additive account decision/outbox linkage. Apply only in isolated staging first.
BEGIN;
CREATE TABLE IF NOT EXISTS contractor_account_events (
 id SERIAL PRIMARY KEY,
 contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 delivery_id INTEGER NOT NULL UNIQUE REFERENCES provider_deliveries(id),
 review_id INTEGER REFERENCES contractor_credential_reviews(id),
 status VARCHAR(30) NOT NULL CHECK(status IN ('approved','deactivated','review_rejected')),
 actor VARCHAR(30) NOT NULL DEFAULT 'administrator',
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_contractor_account_events_contractor_id ON contractor_account_events(contractor_id);
COMMIT;

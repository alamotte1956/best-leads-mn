-- Additive audit and suppression tables. Review in isolated PostgreSQL staging first.
BEGIN;
CREATE TABLE IF NOT EXISTS resend_delivery_events (
 id VARCHAR(150) PRIMARY KEY,
 delivery_id INTEGER NOT NULL REFERENCES provider_deliveries(id),
 provider_id VARCHAR(150) NOT NULL, event_type VARCHAR(40) NOT NULL,
 occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
 received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS email_suppressions (
 email VARCHAR(255) PRIMARY KEY, reason VARCHAR(30) NOT NULL,
 source_event_id VARCHAR(150) NOT NULL REFERENCES resend_delivery_events(id),
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;

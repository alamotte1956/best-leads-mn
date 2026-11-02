-- Default behavior is retained when a contractor has not set preferences.
BEGIN;
CREATE TABLE IF NOT EXISTS contractor_notification_preferences (
 contractor_id INTEGER PRIMARY KEY REFERENCES contractors(id),
 lead_email BOOLEAN NOT NULL, lead_sms BOOLEAN NOT NULL,
 version INTEGER NOT NULL CHECK(version > 0),
 updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS contractor_notification_events (
 id SERIAL PRIMARY KEY, contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 previous_email BOOLEAN NOT NULL, previous_sms BOOLEAN NOT NULL,
 lead_email BOOLEAN NOT NULL, lead_sms BOOLEAN NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_contractor_notification_events_contractor_id ON contractor_notification_events(contractor_id);
COMMIT;

-- Additive audit for administrator and same-browser consumer matching termination.
BEGIN;
CREATE TABLE IF NOT EXISTS lead_status_events (
 id SERIAL PRIMARY KEY, lead_id BIGINT NOT NULL REFERENCES leads(id),
 previous_status VARCHAR(50) NOT NULL,
 new_status VARCHAR(50) NOT NULL CHECK(new_status IN ('Closed','Cancelled')),
 actor VARCHAR(20) NOT NULL CHECK(actor IN ('administrator','consumer')),
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_lead_status_events_lead_id ON lead_status_events(lead_id);
COMMIT;

-- Self-reported follow-up only; no existing lead/offer/payment status is changed.
BEGIN;
CREATE TABLE IF NOT EXISTS contractor_lead_progress (
 offer_id BIGINT PRIMARY KEY REFERENCES lead_offers(id),
 contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 stage VARCHAR(30) NOT NULL CHECK(stage IN ('new','contact_attempted','contacted','estimate_sent','work_scheduled','completed','not_proceeding')),
 next_follow_up DATE, note TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL CHECK(version > 0),
 updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_contractor_lead_progress_contractor_id ON contractor_lead_progress(contractor_id);
CREATE TABLE IF NOT EXISTS contractor_lead_progress_events (
 id SERIAL PRIMARY KEY, offer_id BIGINT NOT NULL REFERENCES lead_offers(id),
 contractor_id INTEGER NOT NULL REFERENCES contractors(id), previous_stage VARCHAR(30) NOT NULL,
 stage VARCHAR(30) NOT NULL CHECK(stage IN ('new','contact_attempted','contacted','estimate_sent','work_scheduled','completed','not_proceeding')),
 next_follow_up DATE, note TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT lead_progress_event_version UNIQUE(offer_id,version)
);
CREATE INDEX IF NOT EXISTS ix_contractor_lead_progress_events_offer_id ON contractor_lead_progress_events(offer_id);
COMMIT;

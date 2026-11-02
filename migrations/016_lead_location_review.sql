BEGIN;
CREATE TABLE IF NOT EXISTS lead_location_reviews (
 id SERIAL PRIMARY KEY, lead_id INTEGER NOT NULL UNIQUE REFERENCES leads(id), zip_code VARCHAR(5) NOT NULL,
 state_code VARCHAR(2) NOT NULL CHECK(state_code IN ('MN','TX','FL','NC','GA','WI')),
 decision VARCHAR(20) NOT NULL CHECK(decision IN ('approved','unavailable')),
 evidence_reference VARCHAR(255) NOT NULL, private_notes TEXT NOT NULL,
 reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;

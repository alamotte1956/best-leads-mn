-- Additive state scope. Existing leads without sidecars remain Minnesota.
BEGIN;
CREATE TABLE IF NOT EXISTS lead_markets (
 lead_id INTEGER PRIMARY KEY REFERENCES leads(id),
 state_code VARCHAR(2) NOT NULL CHECK(state_code IN ('MN','TX','FL','NC','GA','WI'))
);
CREATE INDEX IF NOT EXISTS ix_lead_markets_state_code ON lead_markets(state_code);
CREATE TABLE IF NOT EXISTS contractor_market_applications (
 id SERIAL PRIMARY KEY, contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 state_code VARCHAR(2) NOT NULL CHECK(state_code IN ('TX','FL','NC','GA','WI')),
 zip_codes VARCHAR(500) NOT NULL, services_json TEXT NOT NULL, license_number VARCHAR(100) NOT NULL,
 applicant_notes TEXT NOT NULL, status VARCHAR(20) NOT NULL CHECK(status IN ('pending','approved','rejected')),
 pending_key VARCHAR(50) UNIQUE, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_contractor_market_applications_contractor_id ON contractor_market_applications(contractor_id);
CREATE INDEX IF NOT EXISTS ix_contractor_market_applications_state_code ON contractor_market_applications(state_code);
CREATE TABLE IF NOT EXISTS contractor_market_reviews (
 id SERIAL PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE REFERENCES contractor_market_applications(id),
 decision VARCHAR(20) NOT NULL CHECK(decision IN ('approved','rejected')),
 license_reference VARCHAR(255) NOT NULL, insurance_reference VARCHAR(255) NOT NULL, scope_reference VARCHAR(255) NOT NULL,
 license_expires DATE, insurance_expires DATE, private_notes TEXT NOT NULL, response_message VARCHAR(1000) NOT NULL,
 reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;

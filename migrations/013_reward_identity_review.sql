-- Preparation only. No entries, credit issuance, spins or redemption enabled.
BEGIN;
CREATE TABLE IF NOT EXISTS reward_businesses (
 id SERIAL PRIMARY KEY, identity_digest VARCHAR(64) NOT NULL UNIQUE, verified BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS reward_credits (
 id SERIAL PRIMARY KEY, business_id INTEGER NOT NULL REFERENCES reward_businesses(id),
 source VARCHAR(200) NOT NULL UNIQUE, kind VARCHAR(20) NOT NULL CHECK(kind IN ('purchase','free')),
 consumed BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS reward_months (
 business_id INTEGER NOT NULL REFERENCES reward_businesses(id), month VARCHAR(7) NOT NULL,
 used INTEGER NOT NULL DEFAULT 0 CHECK(used>=0 AND used<=10), PRIMARY KEY(business_id,month)
);
CREATE TABLE IF NOT EXISTS reward_spins (
 id SERIAL PRIMARY KEY, business_id INTEGER NOT NULL REFERENCES reward_businesses(id),
 credit_id INTEGER NOT NULL UNIQUE REFERENCES reward_credits(id), prize_index INTEGER NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE TABLE IF NOT EXISTS reward_identity_applications (
 id SERIAL PRIMARY KEY, contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 legal_name VARCHAR(200) NOT NULL, jurisdiction VARCHAR(5) NOT NULL, registration_id VARCHAR(100) NOT NULL,
 notes TEXT NOT NULL, status VARCHAR(20) NOT NULL CHECK(status IN ('pending','approved','rejected')),
 pending_key INTEGER UNIQUE, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_reward_identity_applications_contractor_id ON reward_identity_applications(contractor_id);
CREATE TABLE IF NOT EXISTS reward_business_accounts (
 contractor_id INTEGER PRIMARY KEY REFERENCES contractors(id), business_id INTEGER NOT NULL UNIQUE REFERENCES reward_businesses(id),
 application_id INTEGER NOT NULL UNIQUE REFERENCES reward_identity_applications(id), verified_until DATE NOT NULL
);
CREATE TABLE IF NOT EXISTS reward_identity_reviews (
 id SERIAL PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE REFERENCES reward_identity_applications(id),
 decision VARCHAR(20) NOT NULL CHECK(decision IN ('approved','rejected')),
 evidence_reference VARCHAR(255) NOT NULL, canonical_jurisdiction VARCHAR(5) NOT NULL,
 canonical_registration_id VARCHAR(100) NOT NULL, private_notes TEXT NOT NULL, response_message VARCHAR(1000) NOT NULL,
 reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMIT;

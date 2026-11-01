-- Additive PostgreSQL migration. Review and back up staging/production first.
-- Do not run against production without explicit authorization.
BEGIN;
CREATE TABLE IF NOT EXISTS contractor_credential_reviews (
    id SERIAL PRIMARY KEY,
    contractor_id INTEGER NOT NULL REFERENCES contractors(id),
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('approved', 'rejected')),
    license_number VARCHAR(50) NOT NULL,
    license_expires DATE,
    insurance_expires DATE,
    license_reference VARCHAR(255) NOT NULL,
    insurance_reference VARCHAR(255) NOT NULL,
    notes TEXT NOT NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_contractor_credential_reviews_contractor_id
    ON contractor_credential_reviews (contractor_id);
COMMIT;

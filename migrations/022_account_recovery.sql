BEGIN;
CREATE TABLE IF NOT EXISTS access_recovery_tokens (
 id SERIAL PRIMARY KEY,
 purpose VARCHAR(16) NOT NULL,
 contractor_id INTEGER REFERENCES contractors(id) ON DELETE CASCADE,
 lead_id BIGINT REFERENCES leads(id) ON DELETE CASCADE,
 token_hash VARCHAR(64) NOT NULL UNIQUE,
 subject_binding VARCHAR(64) NOT NULL,
 delivery_id INTEGER UNIQUE REFERENCES provider_deliveries(id) ON DELETE CASCADE,
 expires_at TIMESTAMPTZ NOT NULL,
 used_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT recovery_subject_kind CHECK(
  (purpose='contractor' AND contractor_id IS NOT NULL AND lead_id IS NULL) OR
  (purpose='consumer' AND lead_id IS NOT NULL AND contractor_id IS NULL))
);
CREATE INDEX IF NOT EXISTS ix_access_recovery_tokens_contractor_id ON access_recovery_tokens(contractor_id);
CREATE INDEX IF NOT EXISTS ix_access_recovery_tokens_lead_id ON access_recovery_tokens(lead_id);
CREATE TABLE IF NOT EXISTS access_recovery_attempts (
 id SERIAL PRIMARY KEY,
 identifier_hash VARCHAR(64) NOT NULL,
 attempted_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_access_recovery_attempts_identifier_hash ON access_recovery_attempts(identifier_hash);
CREATE INDEX IF NOT EXISTS ix_access_recovery_attempts_attempted_at ON access_recovery_attempts(attempted_at);
COMMIT;

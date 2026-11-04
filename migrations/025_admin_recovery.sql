BEGIN;
CREATE TABLE IF NOT EXISTS admin_credentials (
 id INTEGER PRIMARY KEY CHECK (id = 1),
 configuration_binding VARCHAR(64) NOT NULL,
 password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_recovery_tokens (
 id SERIAL PRIMARY KEY,
 token_hash VARCHAR(64) NOT NULL UNIQUE,
 subject_binding VARCHAR(64) NOT NULL,
 recipient VARCHAR(254) NOT NULL,
 delivery_id INTEGER UNIQUE REFERENCES provider_deliveries(id),
 expires_at TIMESTAMPTZ NOT NULL,
 used_at TIMESTAMPTZ
);
COMMIT;

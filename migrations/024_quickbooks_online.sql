-- Additive only. No existing financial/customer rows are changed.
BEGIN;
CREATE TABLE IF NOT EXISTS quickbooks_connections (
 id SERIAL PRIMARY KEY, environment VARCHAR(12) NOT NULL UNIQUE CHECK (environment IN ('sandbox','production')),
 realm_id VARCHAR(30) NOT NULL, company_name VARCHAR(255) NOT NULL, client_binding VARCHAR(64) NOT NULL,
 encrypted_tokens TEXT, status VARCHAR(20) NOT NULL DEFAULT 'connected', confirmed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS quickbooks_oauth_attempts (
 id SERIAL PRIMARY KEY, state_hash VARCHAR(64) NOT NULL UNIQUE, browser_hash VARCHAR(64) NOT NULL,
 admin_fingerprint VARCHAR(64) NOT NULL, client_binding VARCHAR(64) NOT NULL,
 environment VARCHAR(12) NOT NULL, expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS quickbooks_exports (
 id SERIAL PRIMARY KEY, environment VARCHAR(12) NOT NULL, realm_id VARCHAR(30) NOT NULL,
 finance_entry_id INTEGER NOT NULL REFERENCES owner_finance_entries(id), request_id VARCHAR(50) NOT NULL UNIQUE,
 payload_json TEXT NOT NULL, source_hash VARCHAR(64) NOT NULL,
 status VARCHAR(20) NOT NULL CHECK (status IN ('sending','sent','uncertain')),
 external_id VARCHAR(30), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
 UNIQUE(environment,finance_entry_id)
);
COMMIT;

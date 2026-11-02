BEGIN;
-- Existing orders remain revision 1 and retain their original idempotency key.
ALTER TABLE lead_payments ADD COLUMN IF NOT EXISTS quote_version INTEGER NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS checkout_quote_history (
 id SERIAL PRIMARY KEY,
 payment_id INTEGER NOT NULL REFERENCES lead_payments(id),
 contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 quote_version INTEGER NOT NULL,
 amount_cents INTEGER NOT NULL,
 currency VARCHAR(3) NOT NULL,
 mode VARCHAR(10) NOT NULL,
 market_benchmark_id INTEGER REFERENCES market_lead_benchmarks(id),
 quote_expires_at TIMESTAMPTZ NOT NULL,
 session_id VARCHAR(150) UNIQUE,
 status VARCHAR(30) NOT NULL,
 archived_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT checkout_history_payment_version UNIQUE(payment_id,quote_version),
 CONSTRAINT checkout_history_terminal_state CHECK(status IN ('unused','expired')),
 CONSTRAINT checkout_history_amount_version CHECK(quote_version > 0 AND amount_cents > 0)
);
CREATE INDEX IF NOT EXISTS ix_checkout_quote_history_payment_id ON checkout_quote_history(payment_id);
COMMIT;

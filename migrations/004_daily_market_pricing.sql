-- Additive evidence and quote fields. Static price rows/history are retained.
BEGIN;
CREATE TABLE IF NOT EXISTS market_lead_benchmarks (
 id SERIAL PRIMARY KEY, state_code VARCHAR(2) NOT NULL,
 service_name VARCHAR(100) NOT NULL, zip_code VARCHAR(5) NOT NULL,
 observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
 angi_cents INTEGER NOT NULL CHECK(angi_cents > 0),
 thumbtack_cents INTEGER NOT NULL CHECK(thumbtack_cents > 0),
 angi_reference VARCHAR(255) NOT NULL, thumbtack_reference VARCHAR(255) NOT NULL,
 comparison_basis VARCHAR(100) NOT NULL, import_key VARCHAR(150) NOT NULL UNIQUE
);
ALTER TABLE lead_payments ADD COLUMN IF NOT EXISTS market_benchmark_id INTEGER REFERENCES market_lead_benchmarks(id);
ALTER TABLE lead_payments ADD COLUMN IF NOT EXISTS quote_expires_at TIMESTAMP WITH TIME ZONE;
COMMIT;

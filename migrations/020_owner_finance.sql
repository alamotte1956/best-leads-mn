-- Owner-entered financial records are independent of customer-data reset roots.
BEGIN;
CREATE TABLE IF NOT EXISTS owner_finance_entries (
 id SERIAL PRIMARY KEY, entry_key VARCHAR(64) NOT NULL UNIQUE,
 occurred_on DATE NOT NULL, kind VARCHAR(20) NOT NULL, category VARCHAR(40) NOT NULL,
 description VARCHAR(255) NOT NULL, amount_cents INTEGER NOT NULL,
 mode VARCHAR(10) NOT NULL, state_code VARCHAR(2), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 voided_at TIMESTAMPTZ, void_reason VARCHAR(255),
 CONSTRAINT finance_positive_amount CHECK(amount_cents > 0 AND amount_cents <= 100000000),
 CONSTRAINT finance_entry_kind CHECK(kind IN ('expense','other_income')),
 CONSTRAINT finance_entry_mode CHECK(mode IN ('live','test'))
);
CREATE INDEX IF NOT EXISTS ix_owner_finance_entries_occurred_on ON owner_finance_entries(occurred_on);
CREATE TABLE IF NOT EXISTS owner_finance_reviews (
 id SERIAL PRIMARY KEY, starts_on DATE NOT NULL, ends_on DATE NOT NULL,
 mode VARCHAR(10) NOT NULL, state_code VARCHAR(3) NOT NULL DEFAULT 'ALL',
 confirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT finance_review_period UNIQUE(starts_on,ends_on,mode,state_code)
);
COMMIT;

BEGIN;
CREATE TABLE IF NOT EXISTS lead_match_preferences (
 lead_id INTEGER PRIMARY KEY REFERENCES leads(id), contractor_limit INTEGER NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT lead_choice_one_or_three CHECK(contractor_limit IN (1,3))
);
CREATE TABLE IF NOT EXISTS benchmark_match_types (
 benchmark_id INTEGER PRIMARY KEY REFERENCES market_lead_benchmarks(id),
 contractor_limit INTEGER NOT NULL,
 CONSTRAINT benchmark_choice_one_or_three CHECK(contractor_limit IN (1,3))
);
-- Legacy requests and untyped benchmark evidence retain single-contractor behavior.
COMMIT;

BEGIN;
CREATE TABLE IF NOT EXISTS contractor_origins (
 contractor_id INTEGER PRIMARY KEY REFERENCES contractors(id),
 state_code VARCHAR(2) NOT NULL CHECK(state_code IN ('MN','TX','FL','NC','GA','WI'))
);
-- A contractor originating outside MN requires separately reviewed MN coverage.
-- No existing accounts or leads are reclassified or updated.
DO $$ DECLARE item RECORD; BEGIN
 FOR item IN SELECT conname FROM pg_constraint WHERE conrelid='contractor_market_applications'::regclass
   AND contype='c' AND pg_get_constraintdef(oid) LIKE '%state_code%'
 LOOP EXECUTE format('ALTER TABLE contractor_market_applications DROP CONSTRAINT %I',item.conname); END LOOP;
 ALTER TABLE contractor_market_applications ADD CONSTRAINT market_application_state CHECK(state_code IN ('MN','TX','FL','NC','GA','WI'));
END $$;
COMMIT;

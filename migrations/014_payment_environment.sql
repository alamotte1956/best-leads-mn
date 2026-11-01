BEGIN;
-- Historical unclassified payments remain test-only; never unlock live contacts.
ALTER TABLE lead_payments ADD COLUMN IF NOT EXISTS mode VARCHAR(10) NOT NULL DEFAULT 'test';
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='lead_payment_mode' AND conrelid='lead_payments'::regclass) THEN
  ALTER TABLE lead_payments ADD CONSTRAINT lead_payment_mode CHECK(mode IN ('test','live'));
 END IF;
END $$;
COMMIT;

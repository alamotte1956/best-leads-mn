BEGIN;
-- Original Minnesota records keep their original browser/site tracking origin.
ALTER TABLE lead_markets ADD COLUMN IF NOT EXISTS intake_brand VARCHAR(3) NOT NULL DEFAULT 'MN';
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='lead_market_intake_brand' AND conrelid='lead_markets'::regclass) THEN
  ALTER TABLE lead_markets ADD CONSTRAINT lead_market_intake_brand CHECK(intake_brand IN ('MN','USA'));
 END IF;
END $$;
COMMIT;

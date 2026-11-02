BEGIN;
-- Preserve future corrections; leave any older review's unknown source unknown.
ALTER TABLE lead_location_reviews ADD COLUMN IF NOT EXISTS previous_state_code VARCHAR(2);
COMMIT;

-- Adds catalog/coverage storage support only. Indiana remains closed in code.
BEGIN;
DO $migration$
DECLARE target TEXT; prior RECORD;
BEGIN
 FOREACH target IN ARRAY ARRAY['contractor_origins','lead_markets','contractor_market_applications','lead_location_reviews'] LOOP
  FOR prior IN SELECT conname FROM pg_constraint
    WHERE conrelid=format('%I.%I',current_schema(),target)::regclass
      AND contype='c' AND pg_get_constraintdef(oid) LIKE '%state_code%'
  LOOP
   EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I',target,prior.conname);
  END LOOP;
  EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I CHECK (state_code IN (''MN'',''TX'',''FL'',''NC'',''GA'',''WI'',''IN''))',target,target||'_state_allowed');
 END LOOP;
END;
$migration$;
COMMIT;

-- Separate sandbox/live price mappings; does not enable expansion states.
BEGIN;
CREATE TABLE IF NOT EXISTS lead_price_catalog (
 id SERIAL PRIMARY KEY, state_code VARCHAR(2) NOT NULL,
 service_name VARCHAR(100) NOT NULL, mode VARCHAR(10) NOT NULL,
 stripe_price_id VARCHAR(150) NOT NULL,
 CONSTRAINT lead_price_state_service_mode UNIQUE(state_code,service_name,mode)
);
COMMIT;

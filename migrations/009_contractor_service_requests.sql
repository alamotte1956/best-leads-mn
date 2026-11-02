-- Reviewed additions only. No existing contractor or service rows are removed.
BEGIN;
CREATE TABLE IF NOT EXISTS contractor_service_requests (
 id SERIAL PRIMARY KEY, contractor_id INTEGER NOT NULL REFERENCES contractors(id),
 service_name VARCHAR(100) NOT NULL, contractor_notes TEXT NOT NULL DEFAULT '',
 status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','withdrawn')),
 pending_key VARCHAR(150) UNIQUE, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
 resolved_at TIMESTAMP WITH TIME ZONE, resolved_by VARCHAR(20),
 coverage_reference VARCHAR(255), private_review_notes TEXT, response_message TEXT,
 CONSTRAINT service_request_resolution CHECK (
  (status = 'pending' AND pending_key IS NOT NULL AND resolved_at IS NULL AND resolved_by IS NULL)
  OR (status != 'pending' AND pending_key IS NULL AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL AND
   ((status = 'withdrawn' AND resolved_by = 'contractor') OR
    (status IN ('approved','rejected') AND resolved_by = 'administrator')))),
 CONSTRAINT service_request_coverage CHECK(status != 'approved' OR
  (coverage_reference IS NOT NULL AND length(trim(coverage_reference)) > 0))
);
CREATE INDEX IF NOT EXISTS ix_contractor_service_requests_contractor_id ON contractor_service_requests(contractor_id);
COMMIT;

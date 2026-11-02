## Problem and resulting behavior

The Minnesota marketplace needed secure approval, working customer/contractor workflows, email/payment foundations and a controlled national expansion. This branch preserves Minnesota routes and records, applies the supplied MN/USA logos, and adds the operating workflows below. The five expansion states and real rewards remain closed. This is a draft for review, not a production release.

## Completed work

- Rebuilt responsive Minnesota homeowner/application experiences, service pages, receipts, same-browser tracking/cancellation and clear errors/native form fallbacks.
- Added administrator credential evidence, approval/revocation, password setup, protected sessions, exact ZIP coverage, reviewed additional services, multistate applications and gated future-state initial registration/intake.
- Added state-aware service/ZIP matching, protected offer lifecycle, request closure/cancellation audit, private accepted-lead follow-up and national state reporting.
- Prepared state/city SEO pages, illustrative local imagery with provenance, hostname-specific USA home/shared logos, enabled-only sitemap and private previews for all requested markets.
- Integrated durable Resend notifications and signed delivery/suppression tracking for both audiences. Added alert preferences and prevented disabled SMS backlogs from blocking email. SMS stays off.
- Added default-off hosted-checkout expiration/reconciliation, versioned fresh quotes with preserved old sessions, stale-form protection, and retired-session callback isolation. No live provider actions were performed.
- Added daily evidence-based pricing at 85% of the lower comparable Angi/Thumbtack lead fee, Stripe Checkout/idempotent signed accounting, test/live separation and verified-payment contact access for newly billable leads.
- Added postal-facility plausibility holds, documented property-location review and original-site tracking provenance. Postal facility state never proves property jurisdiction.
- Added disabled rewards readiness/business identity review, canonical business/account uniqueness and renewal safeguards; strengthened combined monthly-cap and first-month concurrency primitives. No real entries, credits, prizes or redemption are enabled.
- Added an explicit local customer-row reset with a verified backup, rollback and program/schema preservation. Disabled the legacy schema-dropping reset entry point.
- Prepared isolated PostgreSQL and seven-browser/project CI checks. All provider switches remain default-off; no production resources were changed.

## Validation

Local Python/JavaScript results and browser evidence are summarized in RELEASE_CHECKS.md. The current local Python suite passed 232 tests, including 29 new checkout expiration, quote-history, retry and callback-race tests. After the final previous-state audit addition, all ten location-review tests passed again. GitHub Actions passed all 56 browser scenarios across seven projects and the application checks. Five PostgreSQL concurrency checks passed; repeat migration execution found a test-runner bug caused by literal percent signs being interpreted as driver parameters. The runner now executes migration bodies directly without parameters; its corrected parent run subsequently passed all six PostgreSQL checks (run 41334510324). The new checkout migration and two additional PostgreSQL scenarios have not executed in CI yet. Existing Chromium evidence includes national 24-page/width checks and earlier Minnesota checks. No live emails, texts or charges were sent.

## Remaining requirements

Ongoing private publishing-session authentication; authorized daily market observations; verified Resend sender/runtime keys/webhook and end-to-end delivery; real Stripe sandbox validation of the new hosted-session expiry/requote implementation; the corrected PostgreSQL migration check; physical-device checks; rewards legal rules/qualification/prizes/equal free-entry/fulfillment; state verification policies and launch approvals. Business identity and credentials are documented manual reviews, not external registry integrations.

The owner requested removal of contractor/consumer data only. No local saved database was found. Railway's connected access reveals names, not database credentials or query access; no hosted customer records have been deleted. Keep program files and operational schema intact.

## Deployment steps

1. Run the checks on this draft PR and review requirements/risks in IMPLEMENTATION_STATUS.md.
2. With explicit staging authorization, restore an isolated database, apply additive migrations 001–019 and verify preservation/rollback. Test real providers in test mode with protected secrets and suppressed real recipients.
3. Configure owner-selected Resend sender info@restorationcontractorsmn.com after domain verification. Run the outbox worker; keep SMS and live Stripe off.
4. Obtain the required pricing, legal, state-launch and production approvals. Reconcile outstanding hosted checkouts and customer-data removal against an approved backup.
5. Merge/deploy only after specific authorization, with restore-tested backups, domain checks, monitoring and rollback. The existing Railway services track main, so merging can trigger production deployment. Do not merge this draft as a way to run tests.

First CI results: https://github.com/alamotte1956/best-leads-mn/actions/runs/41333049842. Direct Python dependencies are pinned to the versions installed in the successful application/browser jobs.

# Restoration Contractors USA — current implementation status

This feature branch contains substantial implemented and locally tested work. The entire platform is **not yet complete or approved for production**. External credentials, authorized pricing data, real provider/database/browser validation, rewards rules and release authorization remain required. No Railway deployment, production migration or customer-record deletion has been performed by this work.

## Implemented

- Approved Minnesota and USA logos, preserved Minnesota routes and service catalog, responsive navy/orange/white pages, accessible native forms and JavaScript fallbacks. The exact USA host serves the national home; Minnesota retains its homepage.
- State/city landing content for all six states and requested initial metros, local professional-style illustrative imagery with provenance, fixed SEO canonicals, enabled-only sitemap, private administrator previews. All five new states remain disabled.
- Inactive-first registration, manual license/insurance evidence and approval, secure login/session revocation, single-use password setup, contractor ZIP settings, separately reviewed additional services and state coverage. Gated initial registration/intake for future launched states. Out-of-state origins cannot implicitly gain Minnesota scope.
- Matching by explicit state, service, exact ZIP and current approved coverage; protected offer acceptance/decline/expiration; request cancellation/closure and audit history; accepted-lead follow-up, notes and date filters. Private same-browser consumer status and cancellation; private/no-store account and administration pages.
- National reporting of state activity, applications/current approval and payment/refund records. New state approvals do not change launch controls.
- Resend outbox for consumer and contractor transactional email, signed delivery webhooks, replay protection, bounce/complaint suppression, account/service/state/identity decision notices and lead-alert choices. Disabled SMS cannot starve enabled email batches. SMS remains off for the owner's email-only launch.
- Stripe market-based quotes, inline Checkout amounts, idempotency, signed successful/asynchronous payment and refund accounting, and test/live order separation. Newly billable homeowner contacts remain locked until verified payment; historical acceptance access is preserved.
- Postal-reference plausibility safeguards and documented location review. Unknown/mismatched associations are held before matching; facilities do not establish actual property jurisdiction. Original website tracking links survive state corrections.
- Disabled LeadIQ Rewards preparation and business identity review. Canonical legal-entity/account uniqueness, renewal without identity switching, private evidence, and combined ten-spin monthly transaction primitives with replay/double-spend/concurrency tests. Real entries, credits, spins and redemption remain disconnected and unavailable.
- Local SQLite customer-data reset with verified backup, dependency-safe row deletion and rollback. Legacy schema-dropping reset is disabled. No program files are removed by the record-reset utility.
- Pull-request checks prepared for Python/JavaScript, six isolated PostgreSQL concurrency/migration scenarios, and 56 browser scenarios across Chromium, Chrome, Edge, Firefox, WebKit and Android/iPhone emulation. The browser matrix has now passed in GitHub Actions. Five PostgreSQL checks passed; the migration-runner correction awaits another CI run.

## Verified locally

The complete Python suite passed 203 tests. After adding explicit previous-state audit storage, all ten location-review tests passed again. Three JavaScript fallback checks passed. National pages passed 24 screenshot-backed phone/tablet/desktop checks with no horizontal overflow or broken local images. Earlier Minnesota compatibility checks and their limits remain in BROWSER_COMPATIBILITY.md. GitHub Actions independently passed 203 application tests, three JavaScript checks and all 56 browser scenarios. Five PostgreSQL concurrency checks passed. The migration repeatability check exposed a raw-SQL parameter-handling issue in the test runner; that runner has been corrected and awaits re-execution. Direct dependencies are pinned to the versions installed by the successful CI application/browser jobs.

## External connections and owner choices

- Owner-selected sender: **info@restorationcontractorsmn.com**. Its Resend domain verification and actual delivery are not yet confirmed.
- Railway read-only inventory confirms the repository's live web/cron/Postgres services. A Resend key is present by name; sender, enable switch and webhook secret are not listed. Connected access redacts database credentials and provides no data-query operation. The browser dashboard requires separate sign-in. No variables, services, domains or data were changed.
- The Albert LaMotte Stripe test account was read successfully. Runtime keys/webhook configuration and actual test Checkout/refund/replay execution remain necessary. No charge or live Stripe configuration was created.
- The owner published feature/restoration-usa and draft PR #1 using the private masked token helper. Main remains unchanged. Connected repository reads and CI inspection work; connected write calls still reject access, and the build account does not retain the owner's temporary token. Subsequent updates can use the private project-session publisher.
- No customer database file exists in this local checkout/work directory. Hosted customer-record removal remains pending exact data access, backup/reconciliation and a reviewable target-specific operation. Program files remain intact.

## Required to finish and release

1. Publish the migration-runner fix to existing draft PR #1 and rerun PostgreSQL checks. The browser matrix and application checks have passed; physical-device validation remains outstanding.
2. In an explicitly authorized isolated environment, apply migrations 001–018, test preservation/rollback against a restored copy and execute concurrent matching, acceptance, provider and rewards tests. Do not apply migrations to production automatically.
3. Verify the Resend sender domain, configure protected runtime values and signed webhooks, test delivery/bounce/complaint/idempotency for both audiences, and schedule the outbox worker. SMS remains disabled.
4. Connect an authorized source of comparable daily Angi/Thumbtack contractor lead fees. Missing or stale evidence blocks quotes. No static prices, invented marketplace values or gated-page scraping is used.
5. Complete real Stripe sandbox Checkout, asynchronous success/failure, refunds and replay tests. Finish expiry/re-quote and open hosted-session reconciliation before live payments; closing website matching cannot by itself revoke a Stripe-hosted URL. Confirm purchase/refund policy and activation dates.
6. Complete state credential/insurance policies, actual property-jurisdiction verification and launch review before opening any new state. The current postal snapshot is advisory, not authoritative address verification.
7. Supply lawyer-reviewed rewards rules, qualification criteria, time zone, prizes/odds/inventory, equal no-purchase process and fulfillment. Only then connect trusted issuers and approved prize selection/redemption. The eight-outcome internal primitive is simulation only.
8. Resolve any additional local wheel files not present in this checkout if they become available. The existing embedded dashboard wheel is retained and disabled; no separate missing wheel source was found in the inspected project/work files.
9. Obtain specific production authorization for backups/migrations, record removal, release/merge and Railway deployment. Confirm both brand domains, monitoring and rollback before launch.

Supporting details: PROVIDER_SETUP.md, NATIONAL_EXPANSION.md, REWARDS_READINESS.md, LOCATION_REFERENCE.md, DATA_RESET.md, MARKET_PRICING.md, MINNESOTA_LOOKUP_PLAN.md, BROWSER_COMPATIBILITY.md and RELEASE_CHECKS.md.

GitHub evidence: [draft PR #1](https://github.com/alamotte1956/best-leads-mn/pull/1), [first check run](https://github.com/alamotte1956/best-leads-mn/actions/runs/41333049842).

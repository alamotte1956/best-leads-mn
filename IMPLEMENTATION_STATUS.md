# Restoration Contractors USA — implementation status

This branch is a preparatory increment, not the complete platform and not approved for production. Current pricing uses daily competitor evidence as described in MARKET_PRICING.md; historical milestone notes below record earlier work.

## Implemented

- Additive `/usa` national entry point with navy, orange and white styling.
- Catalog of all six states and requested initial markets.
- Minnesota state and Twin Cities routes. Every new state and city returns 404.
- `/admin/national` overview protected by the existing administrator session, password fingerprint and one-hour expiry.
- Existing Minnesota routes and schema retained.
- Rewards spin endpoint returns 503 unconditionally. No real redemption exists.
- Isolated SQLAlchemy reward models and internal transaction functions: globally unique verified identity digest, unique credit source, credit ownership, atomic consumption and a combined 10-spin UTC calendar-month cap.
- Identical server-side placeholder selection for purchase and free credits. This is simulation code, not approved prize odds.
- Eight passing automated tests covering legacy pages, disabled states, access controls, monthly rollover, combined purchase/free limits, replay, duplicate identity, transfer rejection and concurrent double spending.

## Reconciliation

GitHub main inspected at 068f011549ed501d3d49c6258ee9467532d68cb0. The demo wheel is embedded in templates/contractor_offers.html; the initial filename search missed it. It now retains the design with spinning disabled and no browser prize selection. Accessible Codex folders were searched; no matching uncommitted wheel files were located. Some local paths were inaccessible. The location of the user's existing work has been requested. Do not replace that work without reconciling it. Both approved Minnesota and USA logos supplied by the owner are now included, with trademark artwork preserved.

## Remaining implementation

- Connect the preserved dashboard wheel to the transaction service after identity, legal, and entry-verification work is complete.
- Final official rules, legal review, prize inventory, eligibility, odds, promotion timezone, and approved no-purchase entry procedure. UTC in the prototype must be confirmed before release.
- Trusted business verification and shared business-to-account identity mapping. A unique digest alone cannot establish business identity or prevent aliases.
- Verified payment webhook and approved free-entry issuer. `issue_credit` is internal only and has no public HTTP route. No client may authorize a credit.
- PostgreSQL integration/concurrency testing, including first-month insert retry behavior. Callers must roll back the whole transaction on failures; no caller integration is currently enabled.
- National registration, state-specific license and insurance evidence review, coverage management, approval workflows and contractor dashboard integration.
- State/ZIP/service matching integration, national lead tracking, payment integration, notifications, and state reporting backed by real national data.
- New-state landing content and licensed professional restoration photos. Current catalog is preparatory and new-state routes are disabled.
- Hostname routing and domain/DNS configuration. The approved national logo is now installed.

## Local verification

Use an isolated Python environment, install requirements.txt, and run:

    DATABASE_URL=sqlite:///:memory: python -m unittest discover -s tests -v

Tests force an in-memory legacy application database and a temporary SQLite reward database. Eight tests passed locally. Python compile checks also passed. No PostgreSQL, payment provider, SMS provider, browser visual QA or production checks were run. These tests do not certify the complete platform.

## Deployment steps (approval required)

1. Finish the remaining implementation and reconcile missing local work.
2. Review changes and dependency versions; run full regression and PostgreSQL concurrency tests in an isolated staging database.
3. Prepare additive, versioned migrations and backups. Reward models are intentionally NOT registered with the live application or its existing import-time create_all call.
4. Confirm legal rules, identity verification, payment/free-entry controls and approved imagery before enabling rewards.
5. Obtain explicit authorization for production database changes and Railway deployment.
6. Deploy to staging first, verify existing Minnesota routes and records, and retain a rollback artifact.
7. Keep five new states disabled until separately approved. Production activation requires a reviewed change; there is no public or admin switch that silently enables them.

No Railway deployment or production database connection was performed. GitHub content writes were rejected by the integration (403); the local GitHub sign-in is invalid. A PR cannot be opened with branch content until write access is restored.


## Minnesota repair pass

18 automated tests now pass. Added administrator-issued, one-hour, single-use password links with hashed tokens, CSRF protection, expiry/reissue checks and no automatic messages. Approved contractors can establish credentials and sign in. Password changes revoke existing contractor sessions. Existing contractors will need to sign in again after this update.

Fixed SQLite login and offer-action failures while preserving PostgreSQL production locking. SQLite integer primary-key variants fix local autoincrement; PostgreSQL types remain BigInteger. Fixed naive/aware offer date rendering. Accepted offers show homeowner contact details only to the assigned contractor; pending offers hide them. Added an acceptance guard against multiple accepted offers on one lead and against cancelled leads. Owner reporting now checks the current administrator password fingerprint. Hosted startup no longer creates tables automatically.

Tests include registration/approval/duplicate email, password setup/reuse/expiry/reissue, login/lockout/session revocation, accepted-contact privacy, accept/decline, duplicate acceptance, homeowner submission validation, template compilation and administrator pages. PostgreSQL execution, external SMS delivery, payment processing and production configuration remain unverified. Live matching remains behind its existing activation controls; this update does not enable it. The source contains no functioning payment checkout, so payment operation cannot be claimed complete. Rewards remain unavailable pending the original legal and verification requirements.

Run locally with SECRET_KEY, ADMIN_PASSWORD_HASH and CONTRACTOR_LOGIN_LOCK_SECRET (at least 32 characters) configured. In a fresh isolated environment, install requirements.txt then run Flask using app:app. Local SQLite tables are created automatically; hosted databases require an explicitly reviewed schema step. Do not run reset_db.py or seed scripts against production. Create a contractor application, review its evidence manually, approve it in /admin, then use Create password setup link and share it privately with the verified contractor.


## Usability redesign

20 automated tests pass. Rebuilt the Minnesota homepage and contractor application with local CSS, mobile layouts, visible focus states, associated labels, readable form sections, common-service shortcuts and accurate expectations. Preserved the full existing service catalog, application aliases, SMS consent language, and Minnesota logo.

The homeowner form progressively enhances into two steps, with an editable summary, client validation, inline failure messages, busy-state protection and a no-JavaScript fallback. Server-side form errors retain entries. Email is optional. Request receipts show a session-scoped reference and next steps; these references are not public tracking URLs. Contractor offers can be filtered by status. Administration can search the latest displayed 200 leads and 200 contractors, shows full lead totals, surfaces action messages and expands request details.

Browser checks: completed a synthetic homeowner request against an isolated in-memory preview and verified its receipt; inspected desktop homepage and mobile homepage/application layouts at a 390px viewport with no horizontal overflow. JavaScript syntax checks passed. This is not a formal accessibility audit or proof of superiority to another marketplace. The comparison point was Angi's official how-it-works page (https://www.angi.com/landing/how-it-works); the implementation focuses on restoration-specific clarity and transparent status. Remaining live integrations, PostgreSQL staging verification, identity verification and legal requirements remain as documented above.


## Browser compatibility pass

Shared safeguards now cover every HTML page family, including policies and errors. 22 automated Python tests and three browser-feature fallback checks pass. Chromium preview completed 99 geometry checks across 33 routes at phone, tablet and desktop widths with no page-level horizontal overflow; mobile request submission succeeded. Safari, Firefox and physical-device execution remain outstanding. See BROWSER_COMPATIBILITY.md for the precise matrix and release checks. Production remains untouched.


## Contractor coverage and administrative lead controls

Approved, authenticated contractors can manage their own comma-separated ZIP coverage at /contractor/settings. Invalid input retains the form without changing records. Account identifiers supplied in the request are ignored; the authenticated account determines ownership. Service/credential changes remain subject to review.

Administrators can review an individual request and its offer history, see a side-effect-free service/ZIP matching preview, and move open requests to Closed or Cancelled. The status change cancels pending offers in the same transaction, retains accepted/history records, and stops matching. PostgreSQL status updates take the same lead advisory lock as matching/acceptance; this path still needs PostgreSQL staging execution. Terminal requests cannot be reopened through this control.

27 Python automated tests and three JavaScript fallback checks pass. Browser execution verified coverage saving and request closure against synthetic in-memory data. The two new pages passed six phone/tablet/desktop overflow checks. No new database schema or production changes were required. GitHub branch creation was rechecked and rejected with 403 Resource not accessible by integration; an account connection with repository write access remains necessary to publish the branch and PR.


## Manual license and insurance review workflow

Added append-only contractor credential-review records, administrator review forms with evidence references and expiration dates, and a current-review requirement for new account activation. Rejection deactivates the contractor and cancels pending offers while preserving review/offer history. Once a review exists, expired, rejected or changed-license credentials block login, existing sessions, matching, SMS eligibility and password-setup access. Administration flags current review problems and excludes them from the verified-contractor count. Historical approved records with no review preserve their existing behavior until reviewed; audit and review them before production rollout.

This is documented manual review, not an external registry/insurance-provider check, and not verified legal business identity for rewards. Administrators must independently inspect evidence. This does not authorize activation of the five expansion states or real rewards.

33 Python tests and three browser fallback checks pass. New regressions cover required reviews before activation, registration-to-review-to-activation, expired evidence, expired review session/matching protection, license changes, rejected history and administrator/CSRF boundaries. Chromium preview checked the review page at 320/768/1440 requested widths without horizontal overflow.

New PostgreSQL schema is supplied in migrations/001_credential_reviews.sql. Apply it first in isolated staging, review existing tables/backups and PostgreSQL concurrency behavior, and obtain production authorization before any hosted migration. Local SQLite creation only was exercised; no production migration was performed. The application must not be deployed without the new table. For an application rollback, retain the review table/history rather than dropping records.


## Resend, Twilio and Stripe integration build

Implemented transactional Resend receipts for homeowner requests, contractor applications and confirmed payments, plus email/SMS lead-offer notifications queued by the matching worker. Delivery workers use conditional claims, disabled-by-default channel switches, send-time consent/suppression and credential checks, stable email idempotency keys and no blind retry after uncertain provider results. Signed Twilio terminal callbacks preserve delivery status, including early-callback correlation. Sent email means provider acceptance; email delivery/bounce webhooks remain pending.

Stripe hosted Checkout is authenticated and explicit, prices come from an administrator-managed service/state/mode catalog, and client amounts are ignored. Existing orders retain their saved prices; missing mappings have no fallback fee. Only accepted offers after an explicit activation date can be billed. Signed Stripe callbacks validate mode, linked order, owner metadata, amount, currency and paid status. Unique event records, conditional session persistence, callback-race tests, and monotonic refunds protect accounting. No rewards credits or prizes are issued. Historical Minnesota access/offer behavior remains in place.

The Albert LaMotte Stripe sandbox was selected by the owner, connected through the Stripe plugin and read successfully. It has no active one-time USD prices. The later daily-market policy supersedes fixed-price setup. Application runtime API keys/webhook secrets, Resend domain verification and Twilio sender/campaign configuration are not installed or verified. No real emails, texts, checkout sessions, payments or refunds were created during development.

48 automated Python tests and three browser fallback checks pass. Tests cover real local Stripe/Twilio signature validation with synthetic events, replay/mismatch/refund cases, early callbacks, server-owned variable pricing, live-mode gates, missing configuration, consent suppression, Resend request shape, delivery deduplication and uncertainty. Sending and checkout creation were mocked. The three new screens passed nine Chromium viewport checks without horizontal overflow.

Review PROVIDER_SETUP.md and provider-settings.example. Apply additive PostgreSQL migrations 001, 002 and 003 in staging before deployment; none were applied to production. Real provider sandbox tests, PostgreSQL concurrency, Resend bounce/suppression automation, closed-session reconciliation, disputes and refund initiation remain required before release. Five expansion states, live delivery, live charges and real rewards remain disabled by default.


## Future Minnesota electronic lookup integration

The owner requested future Minnesota state lookup support. MINNESOTA_LOOKUP_PLAN.md records the confirmed DLI licensing/iMS and nightly-export options, Secretary of State business-record options and workers' compensation lookup as separate evidence sources. It defines an additive adapter/evidence architecture, exact-identity matching, freshness/error handling, an observation-only rollout, access/usage prerequisites and release tests. No public real-time API or general liability insurance feed was assumed or activated.

The manual credential-review screen now includes three official lookup-resource links with scope notes. Its authenticated render was checked locally. No automated external lookup, bulk import, paid subscription, external contact, approval change or database migration was performed for this planning update.

## Daily marketplace pricing — current policy

Replaced assigned pricing for new checkout with 85% of the lower comparable Angi/Thumbtack lead fee, rounded down to cents. Observations must match service, state and ZIP and be current for the America/Chicago market day. Administrators can review evidence but cannot assign a platform fee. Historical mappings and payments remain stored.

Contractors receive a durable, expiring quote before explicit Stripe payment. No fresh evidence means no quote or guessed fallback. Quotes last at most one hour and never cross market midnight; Stripe minimum validity imposes a cutoff near day end. Expired or older orders require reconciliation before replacement. Delayed payment methods are confirmed only by a signed successful payment event. No rewards are issued.

The trusted refresh command and source-adapter interface are implemented, but NO authorized Angi/Thumbtack daily collector is connected and no real competitor prices were collected. Source access and meaningful comparison validation remain dependencies, as documented in MARKET_PRICING.md. Apply additive migration 004 after 001–003 in staging; production remains untouched.

Validation of daily pricing: 53 automated Python tests and three JavaScript fallback checks pass. Added checks cover 15% rounding, stale evidence, ignored assigned/client prices, expired quotes and delayed payment confirmation. Synthetic observations and mocked Stripe creation are used. Real daily data collection, provider transactions, PostgreSQL execution and browser execution of the new quote screen remain unverified.

Resend audience confirmation: Resend is the selected transactional email provider for consumers and contractors. An additional end-to-end receipt test passes: consumer intake and contractor signup both queue email, then reach the Resend adapter with their respective recipients. Provider network responses are mocked; no real email was sent. Verified sender-domain/runtime-key setup and two-way reply handling remain outstanding.

Approval-before-purchase policy: contractor billing, quote and checkout routes already require an active, verified approved account through the server-side session guard. The application now states this clearly. Two new regression tests verify pending/partially approved accounts and administrator deactivation cannot bypass the guard with existing sessions, accepted offers or saved quotes. Four focused tests passed, including the approved checkout path and both Resend audiences. No approval records, production data or payment enablement changed.

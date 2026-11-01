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

## Resend delivery tracking and recipient protection

Added signed /webhooks/resend ingestion for sent, delayed, delivered, failed, bounced, complained and suppressed email events. Verification uses the documented Svix raw-body HMAC format, constant-time comparison, a five-minute signed attempt window and durable event-ID deduplication. Valid events must match the queued email recipient and server-owned correlation tag. Audit events retain event type/time and linked message identifiers, without raw email/webhook bodies.

Callbacks, message status and suppression records commit together. Conditional status updates prevent late events or provider send completion/timeouts from clearing a terminal outcome. Permanent bounces, spam complaints and provider suppression block future consumer and contractor messages; explicit temporary bounces do not permanently block an address. The worker checks local blocks before claiming and again before sending. Provider suppression must remain enabled for already-in-flight sends. No automatic unblock, blind resend, inbound reply or marketing flow was added.

Administration shows blocked-address totals and the latest 50 records. The new signing-secret readiness check reveals names only, not values. Migration 005 is additive and unexecuted on production. Existing records and approval requirements remain unchanged. Provider setup now documents the seven event subscriptions, legacy early-callback reconciliation, clock synchronization, pre-existing suppression reconciliation and staging checks.

70 automated Python tests and three JavaScript fallback checks passed. Fourteen new email tests cover the official Svix signature vector, tampering, stale/future attempts, replay, malformed/oversized input, recipient mismatch, early delivery/complaint callbacks, provider timeouts, suppression, temporary delays, administrator access, and concurrent SQLite duplicate/out-of-order events. No provider network calls or real emails occurred. The updated administration screen passed three Chromium widths (320/768/1440), including a long synthetic address, without horizontal overflow. PostgreSQL concurrency, real provider delivery, Safari/Firefox and physical devices remain unverified.

## Contractor account decisions and Resend notices

Added transactional approval, deactivation and rejected-review emails with append-only account activity linked to the delivery record. A credential review alone still cannot activate an account. Repeated unchanged decisions do not create duplicate notices. Later decisions cancel older pending notices, and the worker rechecks the latest decision, current credentials and original recipient before sending. Private review notes and evidence references remain internal.

Only a recorded administrator decision permits a deactivation/rejection notice to reach an inactive contractor; ordinary lead notifications retain all approval restrictions. Account changes, pending-offer cancellation, activity history and email queue entries roll back together on failure. Deactivation now cancels pending offers while retaining accepted offers and payment history. Existing contractor approvals are not backfilled or emailed. An email already in flight cannot be recalled. Approval emails do not issue passwords or authorize payments; password setup remains private and administrator-issued.

The protected credential-review screen shows the latest 20 account decisions and email statuses. Additive migration 006 creates the activity table and was not run against production. No production approvals, payments or live emails were changed. A working website support contact and real Resend setup/testing remain release requirements.

77 Python tests and three JavaScript fallback checks passed. Seven new tests cover final approval versus credential review, unchanged-decision deduplication, superseded notices, inactive-account rejection notices, non-bypassable lead restrictions, transactional rollback and expiry cancellation. The updated activity screen passed three Chromium widths (320/768/1440), including a long synthetic contact address, with no horizontal overflow. PostgreSQL execution, real delivery and other browser engines remain unverified.

## Private consumer request tracking and Resend updates

Added /request-status, linked from the homepage, submission receipt and consumer receipt email. New submissions establish a server-signed same-browser ownership claim with a fixed seven-day expiry. Only the most recently submitted request is shown; URL parameters, request IDs, phone numbers and emails do not grant access. Private/no-store, no-referrer and noindex headers protect tracking and receipt pages. Older browser claims without the new timestamp cannot display private status details.

The page distinguishes pending matching, eligible acceptance, a match needing review, closed/cancelled matching and unknown states. Eligible accepted businesses have call/email actions. Inactive, unverified, test or expired-credential accounts and ambiguous multiple accepted offers expose no business contact details. Homeowner names, phone/email addresses, project descriptions and internal lead fees are omitted. Closure is explicitly not proof of completed work. No new consumer login, cross-device recovery, consumer cancellation control or public ID lookup was added.

Acceptance and administrative closure/cancellation now queue generic consumer Resend updates when an email was provided. Mutation, pending-offer cancellation, update history and email reservation share a transaction. Repeated terminal/accept actions cannot issue duplicate notices. New statuses cancel older pending updates; sending rechecks state, match and original recipient. Initial receipt emails no longer make an outdated matching-pending claim. Already-in-flight messages cannot be recalled. The administrator request view shows consumer update history.

Additive migration 007 creates the new status-update/outbox linkage table and preserves existing records. It was not run against production. 90 Python tests and three JavaScript fallback checks passed. Thirteen new tests cover ownership/privacy, expiry/future/malformed/deleted claims, JSON/HTML intake, contact eligibility, terminal/ambiguous states, notice deduplication/supersession, recipient changes, no-email operation and rollback of both acceptance and closure. Chromium preview passed 27 page-state/viewport checks at 320/768/1440 with no horizontal overflow or incorrect contact visibility. Real provider sends, PostgreSQL execution and additional browser engines remain unverified.

## Consumer control to stop matching

Consumers can open a confirmation page from their private status view and stop matching for their own latest request within the seven-day browser access window. CSRF, an explicit checkbox and a request reference bound to current browser ownership are required. A stale confirmation after submitting a newer request cannot cancel the newer record. GET does not mutate state; repeat and concurrent confirmations are idempotent. Closed requests cannot be reopened or changed through this control.

Shared lifecycle code now handles administrator and consumer termination with the existing PostgreSQL lead lock and conditional state transition. Pending offers are cancelled; accepted offers, payment history and request records are retained. Status audit, email update and changes commit or roll back together. The administrator sees the latest 20 transitions with consumer/administrator actor roles, including requests without an email address. Existing changes are not backfilled. Migration 008 is additive and unexecuted on production.

Fixed a related checkout gap: closed/cancelled requests no longer appear as billable offers or permit new website quotes/checkout. Existing payment accounting and callbacks continue. Previously created Stripe-hosted sessions are not automatically expired; reconciliation/expiration remains required before live payment activation. No refund or contract cancellation is performed by stopping matching.

99 Python tests and three JavaScript fallback checks passed. Nine new checks cover ownership, confirmation/CSRF, stale forms, terminal/expired access, preserved history and replay, transaction rollback, trusted actor roles, concurrent cancellation and closed-request billing restrictions. Eight simultaneous SQLite cancellation attempts produced one audit and one email. Browser execution verified Keep matching and confirmed cancellation on synthetic data; nine responsive checks across confirmation, result and administrative history at 320/768/1440 passed without overflow. Real PostgreSQL concurrency, provider sending and other browser engines remain unverified. No production changes or deployment occurred.

## Reviewed additional contractor services

Contractors can now request another catalog service from service settings and withdraw an unresolved request belonging to their account. Current registered services remain unchanged while a request is pending. Existing and pending services are excluded from the selection list; server validation independently rejects duplicates, unsupported services and oversized notes. A unique pending reservation prevents two pending requests for the same contractor/service. Resubmission after withdrawal/rejection preserves the earlier record.

Administrators have a protected status-filtered review queue and detailed decision page. Approval requires an active approved non-test account, an actual current license/insurance review, two explicit service-scope checks and an evidence reference. It adds one additional service while retaining every existing service row and the primary service. Rejection requires a contractor-visible response, separate from private internal notes. Existing matching consumes the additional service only after approval; service requests never approve accounts or enable payments.

Request and decision emails use the Resend outbox and generic historical wording. Private notes/references stay out of contractor pages and email bodies. State changes, service additions and email reservations commit or roll back together; repeated decisions cannot add duplicate services or notices. Service settings now consistently include the primary service even when legacy records also contain additional service rows. Private/no-store headers cover the settings and operating pages.

Additive migration 009 creates the request/history table; no existing schema columns or rows are removed. It was not run against production. 109 Python tests and three JavaScript fallback checks passed. Ten new tests cover ownership and administrative/CSRF gates, pending-service exclusion from matching, credential/scope requirements, inactive accounts, duplicate/invalid requests, withdrawal/resubmission, preserved records, private/public messages, decision replay and transactional rollback. Browser execution verified a synthetic contractor submission and administrator approval. Phone/tablet/desktop views were checked across seven page states; two inconsistent initial settings viewport measurements were rechecked with screenshots and no overflow was reproduced at 320/768/1440. Internal notes stayed hidden in contractor views. PostgreSQL execution, real sends and additional browser engines remain unverified. Service removal and primary-service changes remain future work.

## Contractor lead-alert choices

Added owner-scoped controls to pause email and SMS lead-offer alerts independently, with a read-only administrator support view and append-only change history. Defaults preserve existing behavior when no preference is saved. Matching, account approval, services and existing offers are unchanged. Account/application/service-review/payment emails keep their own delivery controls. SMS choices cannot provide consent or remove STOP, and email choices cannot clear delivery blocks.

Preference updates, revision checks, audit and pending-alert suppression commit together. Identical retries do not create extra audit records; stale forms cannot overwrite newer choices. Queueing and pre-send checks enforce current preferences, including an interleaving after the worker claims a message. Resuming affects future offers and never revives suppressed outbox messages. In-flight sends cannot be recalled. The authoritative SMS guard also protects the legacy injected dispatch path; the read-only consent-inspection bypass is not for senders.

Additive migration 010 creates preference/history tables without changing existing contractor records. No production migration or real provider send occurred. Dashboard, service settings and administrator navigation link to the new controls. Checkbox styling uses the existing navy brand color with native fallback behavior.

121 Python tests and three JavaScript fallback checks passed. Twelve new tests cover defaults, channel independence, retained offers and critical email, pause/resume, stale/replayed forms, ownership/approval/CSRF, consent and suppression invariants, rollback, read-only administrator access, legacy SMS authorization and a pause after claim before provider dispatch. The twelve notification tests were rerun after final template copy updates. Browser execution verified pausing both channels and resuming SMS independently; 21 screenshot-backed viewport checks at 320/768/1440 passed without horizontal overflow. Real PostgreSQL races, provider delivery and other browser engines remain unverified.

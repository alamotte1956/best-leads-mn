# Restoration Contractors USA — implementation status

This branch is a preparatory increment, not the complete platform and not approved for production.

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

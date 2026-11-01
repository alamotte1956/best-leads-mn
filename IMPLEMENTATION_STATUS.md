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

GitHub main inspected at 068f011549ed501d3d49c6258ee9467532d68cb0. No rewards files exist there. Accessible Codex folders were searched; no matching uncommitted wheel files were located. Some local paths were inaccessible. The location of the user's existing work has been requested. Do not replace that work without reconciling it. Only the approved Minnesota logo exists in this checkout; no national logo has been fabricated.

## Remaining implementation

- Reconcile the original wheel and connect its UI to the new transaction service.
- Final official rules, legal review, prize inventory, eligibility, odds, promotion timezone, and approved no-purchase entry procedure. UTC in the prototype must be confirmed before release.
- Trusted business verification and shared business-to-account identity mapping. A unique digest alone cannot establish business identity or prevent aliases.
- Verified payment webhook and approved free-entry issuer. `issue_credit` is internal only and has no public HTTP route. No client may authorize a credit.
- PostgreSQL integration/concurrency testing, including first-month insert retry behavior. Callers must roll back the whole transaction on failures; no caller integration is currently enabled.
- National registration, state-specific license and insurance evidence review, coverage management, approval workflows and contractor dashboard integration.
- State/ZIP/service matching integration, national lead tracking, payment integration, notifications, and state reporting backed by real national data.
- New-state landing content and licensed professional restoration photos. Current catalog is preparatory and new-state routes are disabled.
- Approved national logo, hostname routing and domain/DNS configuration.

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

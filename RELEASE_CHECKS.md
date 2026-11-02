# Release checks

## Executed locally

- Current local Python suite: 232 tests passed, including 29 checkout expiration/requote/history tests. After the final previous-state audit addition, ten location-review tests passed again. All runs used isolated SQLite databases and mocked external sending/charging.
- Three JavaScript feature-fallback checks passed.
- Twenty-four national route/width combinations passed screenshot-backed Chromium geometry/local-image checks at 320, 768 and 1440 pixels. See national-layout-checks.json in the output package. Earlier Minnesota and workflow results are detailed in BROWSER_COMPATIBILITY.md.
- GitHub Actions executed and passed all 56 browser scenarios across seven projects: Chromium, branded Chrome/Edge, Firefox, WebKit and Android/iPhone emulation. The same run passed the full application and JavaScript jobs. This does not establish physical-device compatibility.
- PostgreSQL safety guards reject hosted/non-test URLs and connection-override query strings before any connection. The GitHub PostgreSQL 18 job passed five concurrency checks; the repeat-migration check failed in the test runner because raw SQL percent literals were interpreted as driver parameters. The corrected parent commit passed all six checks in CI run 41334510324.

## CI coverage and remaining verification

`.github/workflows/platform-checks.yml` runs the normal suite, JavaScript fallbacks, six PostgreSQL 18 scenarios and a browser matrix after a draft PR is published. Browser projects cover Chromium, branded Chrome and Edge, Firefox, WebKit and Android/iPhone emulation. They cover public/private routes at three widths, disabled markets/rewards and native form submission without JavaScript. Emulation does not replace physical-device testing or a formal accessibility audit.

`ci/postgres_concurrency.py` accepts only loopback test_* PostgreSQL databases with no connection-override query parameters. It uses a unique generated test schema and verifies schema isolation before creating/dropping its test tables. It exercises sequential matching, simultaneous acceptance, cancellation/acceptance races, mixed free/purchase monthly cap, source replay and repeat execution of migrations. It must run separately from tests/, which deliberately forces SQLite.

`ci/browser_fixture.py` requires explicit CI/test flags and unconditionally forces in-memory SQLite and disabled email/SMS/payments/matching. It binds loopback and is never imported by the production app. Fixture routes must not be added to app.py or production startup commands.

## Production gates

No live provider end-to-end tests, physical devices, production migrations or deploys have been verified. The corrected parent PostgreSQL migration run passed; new migration 019 and the new checkout-concurrency scenario remain unexecuted on PostgreSQL. The first actual browser matrix and five PostgreSQL concurrency checks passed. All five new states and real rewards remain disabled. Missing daily authorized market data blocks quotes. The hosted-checkout expiry/requote implementation requires real sandbox validation and approved purchase/refund terms before payment launch.

First CI run: https://github.com/alamotte1956/best-leads-mn/actions/runs/41333049842. Pinned Python package versions match that run's successful installations.

Current local continuation: CHECKOUT_RECONCILIATION.md. The current Python/JavaScript results apply locally; earlier 56-browser and six-PostgreSQL CI results apply to parent commit 250f5e9 only. No current-branch CI run or rendered browser validation is claimed.

## PR #2 follow-up

Run 41366990413 passed the application job and all eight PostgreSQL checks, including migration 019 and its preservation/race scenarios. Browser results: 54 passed, two WebKit timeouts. Trace analysis identified a local fixture server request waiting about 86 seconds. BROWSER_FIX_CHECKPOINT.md documents the correction and limits. The new local suite includes the idle-socket/concurrent-write regression and local photo tests; browser rerun is required after publishing the correction.

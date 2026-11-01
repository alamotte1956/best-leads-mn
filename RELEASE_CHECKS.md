# Release checks

## Executed locally

- Complete Python suite: 203 tests passed. After the final previous-state audit addition, ten location-review tests passed again. All runs used isolated SQLite databases and mocked external sending/charging.
- Three JavaScript feature-fallback checks passed.
- Twenty-four national route/width combinations passed screenshot-backed Chromium geometry/local-image checks at 320, 768 and 1440 pixels. See national-layout-checks.json in the output package. Earlier Minnesota and workflow results are detailed in BROWSER_COMPATIBILITY.md.
- Playwright configuration and pinned dependencies installed successfully; `--list` enumerated 56 browser scenarios across seven projects. Enumeration is not execution.
- PostgreSQL safety guard tests reject hosted/non-test URLs and connection-override query strings before making any connection. Actual PostgreSQL checks reported a skip because POSTGRES_TEST_URL was absent.

## Prepared but not executed

`.github/workflows/platform-checks.yml` runs the normal suite, JavaScript fallbacks, six PostgreSQL 18 scenarios and a browser matrix after a draft PR is published. Browser projects cover Chromium, branded Chrome and Edge, Firefox, WebKit and Android/iPhone emulation. They cover public/private routes at three widths, disabled markets/rewards and native form submission without JavaScript. Emulation does not replace physical-device testing or a formal accessibility audit.

`ci/postgres_concurrency.py` accepts only loopback test_* PostgreSQL databases with no connection-override query parameters. It uses a unique generated test schema and verifies schema isolation before creating/dropping its test tables. It exercises sequential matching, simultaneous acceptance, cancellation/acceptance races, mixed free/purchase monthly cap, source replay and repeat execution of migrations. It must run separately from tests/, which deliberately forces SQLite.

`ci/browser_fixture.py` requires explicit CI/test flags and unconditionally forces in-memory SQLite and disabled email/SMS/payments/matching. It binds loopback and is never imported by the production app. Fixture routes must not be added to app.py or production startup commands.

## Production gates

No live provider end-to-end tests, PostgreSQL execution, other browser engines, physical devices, production migrations or deploys have been verified. All five new states and real rewards remain disabled. Missing daily authorized market data blocks quotes. Real payment launch also requires hosted-checkout expiry/re-quote reconciliation and approved purchase/refund terms.

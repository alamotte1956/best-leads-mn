# Browser reliability checkpoint

## Published checkout update

Draft PR #2: https://github.com/alamotte1956/best-leads-mn/pull/2

Commit `0f16bff1c62f1ed852fac5ad45ba6a5b3f3f288f` was published from the owner's authenticated Windows checkout. The complete Python suite passed 232 tests there and the three JavaScript fallback checks passed. GitHub Actions run 41366990413 independently passed the application job and all eight PostgreSQL scenarios, including migration 019 preservation/repeatability and reconciliation/payment concurrency.

The browser matrix passed 54 scenarios and failed two WebKit scenarios. The trace showed an approximately 86-second wait for a **local** `/services/roof-repair` HTML response, while other WebKit navigation stalled. This was not a quote-history database or paid-contact validation failure.

## Correction prepared after that CI run

The CI-only Flask server was single-threaded. An idle/preconnected browser socket could monopolize it and block the second worker. The fixture now handles concurrent requests against its own newly generated temporary SQLite file, with separate database connections. It still refuses to start without both explicit CI flags, always overrides DATABASE_URL, binds loopback and forces all sending/payment/matching/reconciliation switches off. No production startup path imports this fixture.

A regression test leaves a socket idle, verifies another request completes, then submits four concurrent synthetic requests and verifies distinct saved IDs. It also starts with a deliberately invalid hosted database URL to verify the fixture ignores external database configuration. It passes with the corrected fixture.

Public pages also no longer depend on Unsplash hotlinks. Ten service routes use five previously generated/reviewed, local WebP illustrations; related water/roof/storm categories share the appropriate scene. Captions identify them as illustrative. Approved PNG logos and the national hero are retained unchanged as fallbacks, with smaller WebP variants for modern browsers. Original logo artwork and styling were not redesigned.

The browser test assertions, timeout and scenario coverage are unchanged. Passing a local fixture regression does not establish that the full 56-scenario browser matrix has passed after this correction; that CI rerun remains required after publication.

## Stripe sandbox observation

Using the previously selected Albert LaMotte **test** account, a synthetic $1 Checkout session was created and retrieved successfully: `cs_test_a1wdDuxdO4LCge332md0AlWqp3scvg2n5QR9TRcUom7m7CQ7wBeEdrJkfH`. It contained no customer email or application order and remained unpaid. Its provider response passed the application's session-identity validator against a synthetic expected object. This confirms compatible session creation/retrieval fields only; it is not application-runtime authentication, a successful payment or verified webhook delivery.

The connected Stripe operation catalog did not expose session expiration. The probe was configured to expire automatically after approximately 31 minutes; expiry has not been independently retrieved yet. No successful payment, real charge, refund, provider configuration change or application record was created. Full sandbox payment/expiration/webhook/refund/replay testing remains required.

## Publishing limitation

The connected GitHub integration still rejects writes. The correction must be published through the owner's authenticated local session to the same PR #2 branch, followed by the complete CI rerun. It does not target main or deploy Railway. Provider switches, rewards and new states remain closed.

Local correction verification: all 236 Python tests and three JavaScript fallback checks passed. The WebKit executable downloaded, but local browser execution remains unavailable because required shared libraries cannot be installed in this restricted runtime. No corrected full-browser pass is claimed. The publisher reruns checks in GitHub Actions and only integrates PR #2 into the development branch after its exact commit passes.

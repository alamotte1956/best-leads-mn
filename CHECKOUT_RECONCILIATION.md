# Checkout expiration and fresh quotes

This change continues `feature/restoration-usa` at commit `250f5e9b4bea9e6f846fee4174f598eeb809f599`. It is implemented locally; GitHub's connected integration still rejects write operations. No provider request, hosted schema change, production configuration change or deployment was performed.

## Contractor behavior

- The payment history provides **Check checkout status** when the separate reconciliation switch is enabled. It requires a current approved contractor session, ownership and CSRF protection, and works for a closed homeowner request without allowing a new purchase.
- A verified open hosted session is expired when its quote expires, its request closes, coverage becomes unavailable or purchases are shut down. A provider timeout does not establish cancellation. If payment wins the expiration race, the order waits for a signed payment notification.
- Existing paid/refunded history is preserved. Provider retrieval and browser redirects never unlock homeowner contact details; verified successful payment callbacks remain authoritative.
- A quote proven never attempted can refresh after expiry using current authorized market evidence. A previously hosted quote can refresh only after Stripe reports that the exact session is expired and unpaid. An unlinked or ambiguous create attempt cannot be replaced automatically.
- Previous quotes are retained in `checkout_quote_history`. A replacement increments `quote_version`, requires the newly displayed version on the payment form and uses a separate Stripe idempotency key. Late callbacks for a retired session cannot attach to the new quote, even when its price is identical.
- Paid, refunded or asynchronously pending orders cannot be replaced. An unexpected successful callback for a session previously confirmed expired fails closed for provider investigation rather than unlocking a different quote.

## Operator workflow

`CHECKOUT_RECONCILIATION_ENABLED=false` by default. Set it only in the environment being tested, using a matching Stripe test/live key. This flag authorizes inspection/expiration of **existing** sessions; it does not enable purchases. Cleanup can run while `PAYMENTS_ENABLED=false` to close existing hosted links.

`flask --app app reconcile-checkouts --limit 100 --after-id 0` processes a bounded batch in the configured Stripe mode. Advance the returned `next_after_id` until it is null, then restart from zero for the next scheduled sweep. One provider error is reported for that order without stopping later orders. The command creates no replacement checkout, confirms no payment and prints no customer contact or provider secrets. It must be scheduled after deployment; merely closing matching does not immediately revoke an external hosted URL.

Register `checkout.session.expired` alongside the existing successful, asynchronous-failure and refund webhook types. Signatures, mode, session, quote revision, contractor, amount, currency and benchmark are checked. Duplicate expiry events preserve the order state. Already-settled or processing orders are not downgraded.

## Schema and release

Apply additive migration **019** after migrations 001–018, first against an isolated restored database. It adds `lead_payments.quote_version` (existing records stay at version 1) and the quote-history table. Do not deploy the new application against an unmigrated hosted database. The local database-reset utility discovers this customer-data dependency automatically; no production reset was run.

Older version-1 orders retain their existing `lead-payment:<id>:v1` idempotency key. A timeout with no stored session ID requires matching the original Stripe record before a new quote is issued; never clear the old row or invent another key to get around uncertainty.

Local validation: 29 new checkout tests plus the existing suite, 232 Python tests total, and three JavaScript fallback checks passed. PostgreSQL scenarios were added for the reconciliation/payment race and migration of a legacy order with preservation and repeat execution. Those two scenarios and migration 019 have not run on PostgreSQL here. Baseline CI run 41334510324 passed all six previous PostgreSQL scenarios and all 56 browser scenarios on the parent commit. Those results do not validate the new migration or new browser rendering. Actual Stripe sandbox expiration, delayed completion, timeout/replay and requote tests remain necessary before launch.

Official references consulted: [expire a Checkout Session](https://docs.stripe.com/api/checkout/sessions/expire), [retrieve a Checkout Session](https://docs.stripe.com/api/checkout/sessions/retrieve). Stripe permits expiration of open sessions; an already-complete/expired session can reject the expiration request. The implementation retrieves again after that race and never treats an error as proof of cancellation.

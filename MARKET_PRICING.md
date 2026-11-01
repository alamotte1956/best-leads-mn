# Daily competitor-based lead pricing

The owner requested daily market pricing, 15% below Angi and Thumbtack. This means contractor lead fees, not homeowner restoration project estimates. There is no assigned service/state price catalog for new checkouts.

## Implemented rule

For two comparable USD observations, calculate `floor(min(angi_cents, thumbtack_cents) * 85 / 100)`. For example, observed fees of $100 and $80 produce a $68 quote. Rounding down keeps the quote at least 15% below both observations. This is a comparison against recorded observations, not a guarantee about every competitor transaction.

Both observations must cover the same restoration service, state and ZIP and must be observed on the current America/Chicago calendar day. Future, stale, missing or invalid observations block new quotes. Minnesota is the only enabled billing market; client state/amount parameters cannot override it. Old assigned-price rows remain in the database for history but are not used for new checkout.

The authenticated contractor sees a server-owned quote before continuing to Stripe. Quotes last at most one hour and end no later than market-day midnight. New quotes stop during the final 31 minutes of the day because Stripe requires a minimum 30-minute Checkout session. Starting Checkout also requires sufficient remaining validity. Existing valid quotes retain their amount. An expired order cannot create another charge; reconciliation must verify any earlier Stripe session before a replacement is permitted. Browser redirects never confirm payment. No rewards are issued.

## Daily data connection still required

No actual Angi or Thumbtack fees were collected and no authorized data feed or collector is connected. Public homeowner cost estimates are not suitable evidence. There is no implemented automatic public-page price check, and no fabricated fallback.

Before connecting a source, obtain authorized professional-account exports, a permitted provider feed or other documented access for both marketplaces. Establish comparability of service, geography, lead quality, shared/exclusive status, billing unit, promotions, subscriptions, taxes and extra fees. Retain source references and observation time. An importer must reject incompatible or non-USD data before producing records; the application cannot independently prove the meaning of a supplied observation.

A server-owned callable in `app.config['MARKET_BENCHMARK_COLLECTOR']` supplies records to `flask --app app refresh-market-benchmarks`. It must return dictionaries with state_code, service_name, zip_code, observed_at (UTC datetime), angi_cents, thumbtack_cents, angi_reference, thumbtack_reference, comparison_basis='comparable_contractor_lead_fee', and a stable import_key. Positive integer amounts, current date and supported scope are validated. Import keys prevent re-importing observations; a failed batch rolls back. No public price-write endpoint exists. Schedule this command only after the real adapter and source-access checks are implemented. A missing collector fails explicitly.

`/admin/pricing` displays evidence and collector readiness without setting a price. Source references should identify access-controlled evidence, never contain credentials or sensitive homeowner data. Data collection failure must alert operations and leave checkout unavailable after evidence expires.

## Release checks

Apply additive migrations 001 through 004 to isolated PostgreSQL staging first. Confirm actual SDK session creation, expiry, delayed payment completion, refunds, webhook retries and PostgreSQL concurrency there. Tests currently mock Stripe creation and use synthetic observations. Reconcile old pending fixed-price orders before enabling this policy. Runtime provider configuration, real daily data collection and production authorization remain outstanding. No production migration or deployment was performed.

Official context: [Angi billing FAQ](https://intercom.help/angi/en/articles/11024858-billing-frequently-asked-questions) describes variable lead costs; [Thumbtack for professionals](https://www.thumbtack.com/pro) describes professional lead pricing controls. Neither is an implemented daily data feed for this project.

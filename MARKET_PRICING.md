# Authorized daily contractor lead-fee evidence

## Current release

The pricing engine and an administrator CSV intake are implemented. **No live competitor feed or real pricing observations have been supplied or connected.** A callable collector hook alone is not a data connection. The administrator screen reports automatic collector readiness separately from imported evidence. Payment activation, matching and future-state launch controls remain independent.

Verified source context on November 2, 2026:
- Angi's own billing FAQ says lead fees vary by task, homeowner location and demand, and explains access to professional billing statements: https://intercom.help/angi/en/articles/11024858-billing-frequently-asked-questions
- Thumbtack's own administrator explanation describes professional-set exact lead prices and possible promotions: https://community.thumbtack.com/discussion/2234/how-to-set-the-right-lead-budget-as-a-new-pro

These pages explain pricing; they are not an authorized daily fee feed. Generic articles, homeowner restoration estimates and unrelated account averages do not establish the exact comparable contractor lead fee. No arbitrary fallback price or unsupported blanket discount claim is introduced.

## Owner workflow

1. Sign in at `/admin/login`, then open `/admin/pricing`.
2. Download `/admin/pricing/template.csv`. It contains headers only, with no invented example prices.
3. Obtain records you are permitted to reuse from both professional accounts or a permitted provider feed. Retain source documents and source-access/usage permission in secure records. This workflow cannot independently authenticate a document or grant reuse rights.
4. Normalize each comparable pair into a row. Required columns: `state_code,service_name,zip_code,contractor_limit,observed_at,currency,angi_cents,thumbtack_cents,angi_reference,thumbtack_reference,comparison_basis,import_key`.
5. Use exact catalog service names (listed on the page), supported state codes, five ASCII ZIP digits and `contractor_limit` exactly `1` or `3`. The type must be supported by both sources; unknown sharing limits cannot be relabeled as comparable. Currency must be `USD`, amounts positive integer cents, and `comparison_basis` exactly `comparable_contractor_lead_fee`. Observation timestamps must have an explicit UTC offset or Z and be non-future observations from the current America/Chicago calendar day. A historical invoice retrieved today is not a current observation merely because it was downloaded today.
6. Each source reference identifies the original evidence using a private document ID or safe HTTPS URL without credentials, query strings or fragments. Never include account credentials, signed links, customer information or raw invoices in the CSV. Stable import IDs are 1–150 letters/digits/dots/colons/underscores/hyphens, beginning with a letter/digit.
7. Confirm permission and like-for-like comparability, then select **Validate and import evidence**. Review sharing type, source IDs, freshness and calculated fees on the resulting page. This attestation is a manual verification step, not an automatic certification of the underlying records.

Comparability includes the same service, geography, sharing limit, lead quality, billing unit, promotions, subscriptions, taxes and additional fees. Do not invent missing terms. Different project scopes or a lead shared with five contractors cannot silently stand in for one shared with up to three.

Imports require current administrator authentication and CSRF, are bounded to UTF-8 CSV / 256 KB / 500 rows, and are atomic. One invalid row rejects the complete file. Identical import-key retries are skipped; conflicting reuse of a key rejects the entire transaction. Evidence is never overwritten and historical payment/quote records are retained. Original permission/source documents remain in the owner's secure records rather than this application. No schema migration is required.

## Quote rule and safety

For two comparable observations, the fee is `floor(min(angi_cents, thumbtack_cents) * 85 / 100)`. For a **synthetic arithmetic example only**, 10000 and 8000 cents produce 6800 cents. This comparison applies to those recorded observations; it does not establish a guarantee against every competitor transaction.

Quotes require exact state/service/ZIP/sharing-type evidence. Missing or expired evidence blocks quoting. No market-wide substitution or one-to-three sharing substitution is allowed. Closed states remain closed even when evidence is recorded. Only Minnesota is enabled.

Quotes last at most one hour and end no later than Central midnight. New quotes stop during the final 31 minutes of the day because Stripe requires at least 30 minutes of Checkout validity. Evidence may still be imported during this final window, but it cannot bypass the Checkout cutoff and becomes stale at the day boundary. Old quote versions, hosted-session expiration/reconciliation and contact-access/payment controls remain as documented in CHECKOUT_RECONCILIATION.md.

## Server-side import and future feed adapter

Trusted operators can use the same normalized file and validation with:

```
flask --app app import-market-benchmarks /secure/normalized-evidence.csv --authorized
```

This confirms authorized source reuse and like-for-like verification. The command does not fetch websites, store the file, enable a provider or schedule itself. Validation failures return a nonzero exit status. Do not put credentials into filenames or source references.

An approved provider adapter can call the shared atomic `import_benchmark_records` function. The existing `app.config['MARKET_BENCHMARK_COLLECTOR']` hook and `flask --app app refresh-market-benchmarks` remain available for a server-owned adapter. That adapter needs a real documented source contract, access credentials, source schema, comparability rules, failure alerts and freshness monitoring before scheduling. No feed endpoint or credentials have been guessed or provisioned.

## Verification and remaining dependency

Automated tests cover authorization/CSRF/private downloads, exact fee calculation, one/three separation, stale/future/currency/scope/source rejection, rollback, conflicts, replay, malformed/oversized files, closed-state preservation and the day-end quote cutoff. Browser checks exercise synthetic uploads and retries only. They do not establish actual source permission or real marketplace prices.

**Still required to activate evidence-backed pricing:** owner-authorized, current comparable Angi and Thumbtack records, or documented permission and access to a real provider feed. Full Stripe sandbox end-to-end validation remains a separate launch gate. Do not enable payments or manufacture evidence to work around this dependency.

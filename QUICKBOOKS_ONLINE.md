# QuickBooks Online integration

## Release scope and honest connection status

`/admin/quickbooks` is the sole-owner connection and accounting page, linked from the master directory, integrations and finance report. This release implements OAuth company authorization, explicit company confirmation, read-only QuickBooks profit-and-loss reports and individually reviewed exports of local **expenses**. It does not automatically export lead-sale/refund records, initiate payments, send invoices, modify QuickBooks transactions when local entries are voided, or import QuickBooks expenses into local financial totals. These remain separate follow-up workflows, including tax and sales-account mapping review.

No real company is connected merely by deploying code. Automated tests use synthetic/mocked providers, not a real Intuit sandbox. A developer app, credentials and owner authorization are still needed for actual sandbox verification. Production accounting writes remain disabled until that verification and mapping review are completed.

## Protected setup

- `QBO_ENVIRONMENT=sandbox` initially; only `sandbox` and `production` are valid. Each connection uses its matching fixed Intuit API host. Test expenses never export into a production company; live expenses never export into a sandbox.
- `QBO_CLIENT_ID`, `QBO_CLIENT_SECRET`: credentials belonging to the matching Intuit app environment. Store directly in protected hosting variables, not source code, financial descriptions or chat.
- `QBO_TOKEN_KEY`: persistent Fernet encryption key, generated once and stored in protected hosting variables. Retain it with encrypted backups. Never regenerate it for a routine release: without it, stored credentials cannot be decrypted and the company must be reauthorized. It is separate from the site session key.
- `QBO_ENABLED=true` enables connect/read features only when required credentials, encryption and schema are present. Missing or invalid settings stop provider access.
- `QBO_LIVE_EXPORTS_ENABLED=false` initially. Production expense writes remain blocked independently of the company connection. Sandbox exports still require per-expense review and explicit confirmation.

Register this exact redirect URI in the Intuit app:

```
https://www.restorationcontractorsmn.com/admin/quickbooks/callback
```

Start the connection from the signed-in website owner page. Intuit's standard accounting scope grants read/write access; the app restricts its behavior to the reviewed operations described here. The company owner must choose and authorize the intended company. Then review its returned name, realm ID and environment, and click Confirm company. A wrong company must be disconnected before replacement. CompanyInfo.Id is an entity ID, not the OAuth realm ID; company information is fetched through the realm-scoped Intuit API and reviewed by the owner.

## Reports and reviewed exports

The profit-and-loss view accepts an explicit date range of up to 184 days and Cash or Accrual basis. It confirms the provider's returned period/basis and shows its currency and generation time. Empty provider data is not represented as established zero profit. It does not add QuickBooks totals to the local management report or infer state attribution.

For an expense export, first check whether it is already recorded or matched by a bank feed in QuickBooks. The owner selects an active expense category and bank/credit-card funding account from the actual company's chart of accounts; no category is guessed. A verified USD home currency is required. The reviewed local date, description, amount and classification are sent as a QuickBooks Purchase (an accounting record, not a payment instruction).

The request ID, exact payload, source fingerprint, environment and company are committed locally before contacting Intuit. Database uniqueness prevents repeated site export of the same local expense in an environment, including after reconnection. A provider timeout or mismatched result leaves a sending/uncertain record and is never blindly retried. Find the existing QuickBooks Purchase by the recorded reference and enter its ID to reconcile it; the app verifies its date, amount, accounts, payment type and unique private note. A confirmed export cannot be reassigned to a different provider ID. A pre-existing manual entry is not automatically detected; human review before export remains required.

Local corrections do not silently delete or void accounting records. Review corresponding corrections in QuickBooks. Do not enter a separate second local expense simply because an export completed.

## Credential and request security

Tokens are encrypted in the database and never rendered into HTML, session cookies, URLs, logs or reports. The browser cookie holds only a random OAuth binding nonce; server storage retains only its hash and the hashed state. Authorization state is single-use, expires in ten minutes, and is tied to the initiating browser, current admin password fingerprint, client and environment. Callback codes are never copied into login redirects. Callback previews without a current admin session must restart the connection. Denials consume state without exchanging a code.

The refresh helper locks the connection row on PostgreSQL and stores any rotated refresh token before subsequent API failures can roll back a transaction. Refresh failure requires reauthorization. API and OAuth hosts are fixed, TLS validation remains enabled, HTTP redirects are refused, requests and response sizes are bounded, and provider errors are sanitized. Expense calls verify the expected realm, so changing a connection cannot redirect an in-flight write to another company. All pages are owner-only/private/no-store and form writes require CSRF. Disconnect stops local access even when provider revocation cannot be confirmed; in that case the owner must also disconnect the app in QuickBooks.

## Schema and deployment

Migration `024_quickbooks_online.sql` creates only three new tables: encrypted connections, OAuth attempts and export audit. It does not rewrite or delete existing customer/financial records. `python apply_quickbooks_schema.py` is an explicit PostgreSQL pre-deploy operation with a transaction advisory lock and idempotent CREATE TABLE IF NOT EXISTS statements. All statements run in one transaction. Existing migrations and schema repetition are checked in isolated PostgreSQL CI; the pre-deploy runner is also exercised twice while preserving existing expense/export rows.

## Official sources checked November 2, 2026

- Intuit OAuth client/token and refresh/revoke behavior: https://developer.intuit.com/app/developer/qbo/docs/develop/sdks-and-samples-collections/ruby/oauth-ruby-client
- Current OAuth endpoints verified from Intuit's discovery document: https://developer.api.intuit.com/.well-known/openid_sandbox_configuration/
- Accounting scope, company authorization and report/expense capabilities: https://github.com/intuit/quickbooks-online-mcp-server
- CompanyInfo identity and realm-scoped SDK behavior: https://github.com/intuit/QuickBooks-V3-PHP-SDK/blob/master/src/DataService/DataService.php
- API error/Fault handling: https://static.developer.intuit.com/output_html/qbo/docs/develop/troubleshooting/error-codes.html

Provider approval, actual sandbox round trips, real account/currency mapping and production write authorization remain necessary before live bookkeeping exports are enabled. Do not label mocked tests as successful real-company synchronization.

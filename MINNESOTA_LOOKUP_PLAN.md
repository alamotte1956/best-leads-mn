# Future Minnesota electronic lookup integration

Status: planned; automated state connectivity is disabled. Official reference links are available in the existing administrator credential-review screen. No external account was created, data subscription purchased, state contacted, records bulk-downloaded, or production database changed for this plan.

Scope assumption: the requested Minnesota lookup is for contractor licensing, business identity and credential review. A different state program can be added through the same adapter boundary after its exact system and documentation are identified.

## Confirmed official sources

| Source | Documented capability | Intended use and limit |
| --- | --- | --- |
| [DLI license and registration lookup](https://www.dli.mn.gov/license-and-registration-lookup) | Guest iMS search by complete license/registration number; links to a nightly licensing data spreadsheet. DLI describes current active license/registration status as Issued. | Licensing evidence, license type, status and enforcement review. The nightly export is an initial integration candidate, subject to confirming automated download/reuse terms and actual file schema. |
| [Secretary of State business search](https://www.sos.mn.gov/business-liens/business-help/how-to-search-business-filings/) | Search by company name or file number and inspect the business record. | Resolve legal entity/DBA identity and filing status. This is separate from occupational licensing and insurance. |
| [Secretary of State data options](https://sos.mn.gov/business-liens/business-liens-data/business-data-available/) | Electronic business data and commercial bulk-data options with order/licensing requirements; active-business data is delivered as CSV in a ZIP file. | Evaluate an approved licensed data import if suitable. Do not subscribe, incur fees or republish records based on this plan alone. |
| [DLI workers’ compensation lookup](https://dli.mn.gov/business/workers-compensation/work-comp-online-insurance-verification-tool) | Employer workers’ compensation proof-of-coverage lookup. | Record workers’ compensation evidence as its own check. Do not treat it as general liability insurance verification. |

Sources checked November 1, 2026. No documented public real-time API was established by this review. This is not a claim that no API exists. Confirm any partner/API program directly with the responsible agency before choosing endpoints or authentication.

## Phased implementation

1. **Current manual workflow:** use the official links, compare the relevant records, and retain references/notes in the existing append-only credential reviews. No automated approval is implied.
2. **Confirm data access:** obtain official integration documentation, permitted commercial use, download/caching/redistribution rules, schema, update cadence, identifiers, authentication, rate limits and any charges. Validate whether the nightly DLI export covers each service/license type we support. Government registration, contractor registration, occupational license and insurance are separate concepts.
3. **Build an isolated adapter:** support a documented official API or an approved snapshot import behind the same internal interface. Keep network calls in a background job rather than homeowner request or contractor login paths. The existing manual review screen must continue to function during outages.
4. **Run in observation mode:** compare external results with reviewed applications without changing approvals. Review false matches, duplicate entities, license-type differences, stale snapshots and missing records before enabling any eligibility effects.
5. **Enable assisted review:** show source, identity match, status, timestamps and exceptions to administrators. Append external evidence and the human decision separately. Any automatic suspension, approval or public badge requires an explicitly reviewed policy and rollout decision. A new state integration must not enable any of the five disabled expansion states.

## Planned adapter contract

One provider interface per jurisdiction and evidence category. A request supplies the internal contractor ID, jurisdiction, complete license/registration number, claimed license type, company/DBA name and, where legitimately required, business filing identifier. Do not send homeowner data, payment details, SSNs or unrelated personal records.

Normalize results into:

- Provider, jurisdiction, evidence category and source record identifier.
- Requested and returned license number/type; legal entity/DBA identity; match method and ambiguity indicator.
- Separate license, registration, business-filing and workers’ compensation statuses. General liability remains a distinct review.
- Effective/expiration dates only when supplied by that source; do not invent an expiry for records that lack one.
- Source update time, retrieval time, snapshot version/checksum, schema version and a stable evidence reference.
- Outcome: matched, ambiguous, no record found, unavailable, stale or invalid response. No record found is not proof of fraud or automatic license revocation.

Future evidence storage should be additive and independent of contractors and existing manual review history. Preserve provenance and prior observations rather than overwriting them. Do not place a government credential, provider key or raw sensitive response in browser content or application logs.

## Matching, freshness and failure behavior

Match complete jurisdiction/license identifier and license type first, then corroborate business identity. Company-name similarity alone must not mark a business verified or merge contractor accounts. Handle DBAs, renamed companies, personal versus business licenses and multiple credentials explicitly.

Use a configurable freshness policy based on the official update schedule. Label a nightly import with its actual source date; it is not a live lookup. When data is unavailable, stale, malformed or ambiguous, report an unresolved check and route to manual review. Do not fabricate active/insured status or automatically reverse a human rejection.

Keep the existing credential-expiry protections. The first integration release should attach evidence only. Final approval, insurance adequacy and any change to legacy approved accounts remain within the reviewed administrative workflow. State business registration alone does not satisfy LeadIQ business-identity, monthly-limit or free-entry requirements.

## Release acceptance checks

Before activation, verify exact match, duplicate/ambiguous match, no record, expired/revoked status, changed license, wrong license type, stale source date, provider outage, rate limiting, malformed payload, schema changes and secret redaction. Test import idempotency, checkpoint/resume, concurrent jobs, source checksums and preservation of existing reviews. Verify that external evidence cannot approve an account, award a reward, trigger a payment or enable another state without the appropriate application policy.

Use fixtures or permitted sample records in isolated staging first. Production activation requires confirmed access terms, reviewed retention/redistribution rules, staging results, an operational rollback procedure and the owner's release authorization. This plan does not authorize scraping login-protected pages, bypassing access controls or contacting state personnel on the owner's behalf.

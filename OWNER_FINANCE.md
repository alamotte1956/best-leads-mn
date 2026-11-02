# Owner profitability reporting

The prior owner command center left payment/refund metrics disconnected, and national totals deducted refunds without expenses. Those operational figures did not establish business profit.

`/admin/finance` now reports recorded operating results from confirmed live USD lead payments plus owner-entered other income, less cumulative recorded refunds and recorded expenses. The owner can choose a Central-time date range, state and environment, enter actual advertising/hosting/domain/software/labor/insurance/payment-processing costs, void incorrect entries with a retained reason, confirm period cost review and export CSV. New or voided entries invalidate overlapping cost reviews. Repeated form submission is idempotent. Fees are part of expenses and are not deducted twice. Sandbox activity is separately selectable and excluded from live results.

Default All states is the overall result. State views show direct contribution before shared overhead, explicitly display unallocated shared costs and are not described as full state profit. A report starts with a costs-incomplete warning; owner confirmation is not an audit. Positive net receipts permit a recorded margin; zero or negative receipts do not produce a misleading percentage.

These are management reports, not a bank-reconciled accounting ledger. Current cumulative refunds are allocated to the original paid date; period results can therefore change after a later refund. Provider fees, bank settlements, disputes, taxes, unpaid bills, legacy payment_transactions/business_expenses and external income/costs are not silently imported. Unconfirmed, undated or non-USD receipts are excluded. No live financial-provider operation is performed.

Migration 020 adds independent owner finance entries/reviews. It does not alter or delete business_expenses or customer tables. Owner finance records have no customer foreign keys and survive the existing dependency-based customer reset utility. The endpoint requires current administrator authentication and CSRF for every mutation; responses and CSV downloads are private/no-store. CSV descriptions are protected against spreadsheet-formula interpretation.

The owner command center also now shows confirmed live USD payment totals for the current Central day, with a label that correctly attributes cumulative refunds to those payments. Operational acceptance counts are never treated as revenue.

No production migration or deployment is included in this change. Required before release: apply the additive migration in an isolated restored environment, verify retention/repeatability and run application, PostgreSQL and browser checks. Actual entries must come from the owner's receipts and provider statements; no costs, processing percentages or revenues are invented.

## Next requested marketplace work

Preserve the owner's additional request: homeowners choose one contractor or up to three; contractors see the request's type before acceptance and payment. Matching/acceptance capacity, disclosures, private homeowner tracking and comparable pricing must all honor the selection. This is separate from profitability reporting and must not be claimed complete until implemented and concurrency-tested.

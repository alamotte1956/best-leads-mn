# Homeowner choice: one contractor or up to three

Homeowner intake on the main, Minnesota service and future launched-state forms explicitly offers one contractor or up to three. The server accepts only 1/3 (including their form strings), stores the selection once in a dedicated preference row, and defaults old clients/legacy requests to one. No public endpoint changes that selection after submission. Expansion gates remain closed.

The contractor dashboard, offer emails/SMS, accepted-offer billing form, quote screen and hosted Checkout product description disclose single-contractor versus shared (up to three) before a decision. A single-contractor label describes this platform's accepted-recipient limit, not exclusivity across other marketplaces or a guaranteed job. No fees or comparative prices are invented.

Sequential matching continues after a shared request's first and second acceptance and stops at three. PostgreSQL acceptance, expiration, cancellation and matching share the per-lead advisory lock. SQLite acceptance uses the same limit inside its atomic update. Accepted recipients are distinct contractor IDs. A duplicate accepted contractor cannot occupy another slot. Pending offers are cancelled when capacity fills, in the same transaction. Cancellation/closure and qualification checks remain enforced. Existing paid-contact rules are unchanged; acceptance does not by itself unlock newly billable contacts.

Private homeowner status lists all eligible accepted businesses up to the chosen cap; malformed legacy over-cap/duplicate matches require review. The original-browser/seven-day access boundary is retained. An initial accepted-status email remains one-per-request and links to the current list rather than duplicating notices with each additional acceptance. Receipt and status pages repeat the chosen lead type.

Comparable pricing evidence now has a typed optional mapping. Legacy/untyped evidence applies only to single-contractor requests. Shared requests require current authorized shared-lead evidence; they cannot reuse single-lead benchmark values. Collector input can include contractor_limit; absent values preserve one. Missing shared evidence blocks quotes. This does not connect a pricing feed or enable payments.

Migration 021 adds preference and benchmark-type mapping tables only; no production schema or records are changed by this branch. Existing customer reset FK discovery includes lead preferences; independent owner financial records stay preserved.

Validation includes invalid/forged intake limits, single/legacy capacity, shared acceptance cap, sequential progression, private multi-business status, non-duplicated initial notices, contractor disclosures, closed-request rejection, typed pricing, native no-JavaScript choice submission, and a four-contractor PostgreSQL acceptance race that must yield exactly three successful acceptances. Runtime provider switches and all five future states remain closed.

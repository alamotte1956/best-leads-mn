# Master administrator access

Production owner email: alamotte1956@gmail.com. Configure `ADMIN_OWNER_EMAIL` on the web service. When configured, sign-in requires that email (case insensitive) **and** the existing hashed administrator password. The email alone never grants access or creates a contractor/admin account. No password is stored in this document. Installations without an owner email retain their existing password-only login until configured.

Open https://www.restorationcontractorsmn.com/admin/login and use the owner email and current administrator password. After sign-in, https://www.restorationcontractorsmn.com/admin/access lists every administrative section, financial CSV export, and all seven private state previews. Contractor/lead record pages are reached through their lists; no record IDs are invented. This is the existing sole administrator's full access, not an unauthenticated bypass or new subordinate-role system.

HTML GET requests to protected admin sections now direct expired/missing sessions to sign-in and return to the original existing admin GET route after successful authentication. Only local registered administrative GET destinations are accepted. External URLs, control characters, backslashes, fragments, login/logout loops, nonexistent pages and POST-only actions fall back to the admin dashboard. POST actions are never automatically replayed. Unauthenticated POST and JSON requests remain forbidden. The branded denied-action page explains sign-in and resubmission.

Sessions retain the existing one-hour lifetime and password-fingerprint revocation. Password changes end older sessions. Stay on the same HTTPS www hostname and browser; cookies are not shared between unrelated domains, private windows or devices. Contractor sign-in does not confer administrator rights. The master directory and owner email remain private/no-store, and public pages never render the owner identity.

All state previews are available to the authenticated owner. Public future-state launch, payment, matching and rewards controls remain independent. Contractor passwords remain chosen/reset by contractors using their private email links.

## Recording expenses

1. Open https://www.restorationcontractorsmn.com/admin/finance after signing in.
2. Select the date range and Live business for actual transactions, or Test / sandbox for practice. Click Update report.
3. Expand Record an expense or other income.
4. Enter Date paid or received (within the selected date range), choose Expense, Category, Description or receipt reference, Amount (USD), and Assign to a state.
5. Choose Shared / overall business for overhead benefiting the whole company, or the specific state for a directly assigned cost. Click Save financial entry.
6. Check Recorded entries and the updated expense/profit totals. Void incorrect entries with a correction reason, then add the corrected entry. Keep bank credentials and full account details out of descriptions.
7. Confirm cost review only after all applicable period costs have been entered and duplicate income checked. Confirmed lead payments already appear automatically; do not enter them again as other income.

QuickBooks Online is not connected by this release. Financial CSV downloads are management reports, not a ready-made QuickBooks transaction import. Any future connection needs authorized company access, explicit account/category mappings, duplicate protection and test/live isolation before writing to real books.

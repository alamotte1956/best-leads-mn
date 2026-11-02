# Contractor and consumer data reset

## Production reset completed — November 2, 2026

After explicit final owner confirmation, the Best Leads 2 production PostgreSQL customer reset committed through the authenticated Railway maintenance console. Removed all 8 contractor records, 12 homeowner leads and their related records across 12 customer tables. Read-back verified every selected table contained zero rows and all 14 public tables remained present. Administrator login and business-expense rows were unchanged (both tables were empty before and after). Table definitions, sequence progression, program files, branding and administrator configuration were preserved.

A Railway volume recovery snapshot was completed before reset. A separate private pg_dump archive was restored successfully into a disposable verification database, confirming 8 contractors and 12 leads; the verification copy was then removed. The reset checked archive readability, used a guarded transaction with exclusive customer-table locks, refused changed customer/payment counts, used an explicit table list with RESTRICT and CONTINUE IDENTITY, and preserved operational tables. There were zero local payment transactions. No external provider records or backups were deleted.

Post-reset live website health returned `{"status":"ok"}` at `https://www.restorationcontractorsmn.com/health`. New registrations and requests may create new records normally. This reset does not disable intake or deploy development code.

## Earlier checkpoint and local utility

The owner requested removal of contractor and consumer records, keeping all program files. No saved customer database was found in the local checkout or its work directory on November 1, 2026. Railway is now connected for configuration inventory, but its OAuth access redacts database credentials and has no data-query operation; the browser dashboard requires a separate sign-in. No existing hosted records have been deleted.

`tools/reset_customer_records.py` is an explicit **local SQLite** maintenance utility, dry-run by default. It accepts an existing database file, never a database URL. It does not import/start the app, create tables, drop tables, delete files, or alter application code. It removes contractor/consumer root rows and their foreign-key dependents, including leads, offers, reviews, preferences, customer notifications and local payments. It also removes local phone/email suppression data belonging to that reset. It preserves administrator login metadata, benchmark evidence, pricing catalog and Stripe event-id replay tombstones. No external Resend, Stripe, SMS or backup records are removed by this local utility.

1. Identify the actual local database and stop its application and workers. Keep all sending and payment switches off.
2. Review the counts: `python tools/reset_customer_records.py --database instance/contractors.db`.
3. Apply only to the intended local file: `python tools/reset_customer_records.py --database instance/contractors.db --apply --backup /absolute/private/customer-backup.db`.
4. The utility takes the SQLite write lock, creates a new full database backup, checks its integrity/references, deletes customer rows in dependency order, and checks references before committing. Any failure rolls back the deletions. A completed or partial backup may remain after failure; treat every backup as private customer data.
5. Reconcile/expire any open external checkout sessions and provider mail queues before allowing sending or payments again. Database deletion alone cannot revoke a Checkout URL or remove copies held by a provider. Retained Stripe event IDs help prevent old webhook replays.

Hosted PostgreSQL deletion requires the exact target database, an approved restore-tested backup, a reviewed deletion plan with current schema and open-payment reconciliation. This utility deliberately does not perform hosted deletion. No generic production reset button or public deletion endpoint is provided.

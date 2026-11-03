# Temporary email testing

Set `EMAIL_TEST_ONLY=true` and `EMAIL_TEST_RECIPIENTS` to a comma-separated list of exact destination addresses before enabling email. An empty or malformed list blocks all email in this mode. Matching is case insensitive. Addresses are never substituted: other recipients' messages remain pending. Enabled SMS is independent and should remain disabled during email-only tests.

The owner-designated test addresses are alamotte1956@gmail.com for consumer requests and alamotte19562@gmail.com for contractor registration. Enter the appropriate address on each form. Do not route unrelated customer records into these inboxes.

Provider setup also requires `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, a verified sender domain, and `EMAIL_SENDING_ENABLED=true`. The notification worker is `flask --app app deliver-notifications`; saving a form queues a receipt but does not itself run that worker. Test-mode provider payloads are marked `[TEST]` and include a test notice. The administrator integrations screen shows whether this restriction is active.

A provider acceptance is not inbox delivery. Configure `RESEND_WEBHOOK_SECRET` and the signed `/webhooks/resend` endpoint to track delivery events. Reconcile `uncertain` or stuck `sending` records with the provider before retrying; never automatically resend them.

Before returning to real recipients: stop the worker, review the pending backlog, deliberately cancel obsolete test messages, configure verified production delivery, and then disable `EMAIL_TEST_ONLY`. Removing the restriction makes all otherwise eligible pending email available to the worker.

Verification: all 263 application tests pass locally, including allowlist enforcement, malformed configuration, backlog selection, direct provider-call protection, a restriction change after claiming a message, and unchanged normal-mode payloads. These automated tests use mocked provider calls; they do not establish actual delivery.

## Controlled matching trials

With `EMAIL_TEST_ONLY=true`, matching eligibility now requires **both** records' exact email addresses to appear in the validated `EMAIL_TEST_RECIPIENTS` list. The scheduled worker filters requests before expiration/advancement and filters contractor candidates. Existing offers involving an unrelated recipient cannot be accepted, purchased or used to expose contacts while the restriction is active. Normal credential, state, service, ZIP and homeowner one/three limits still apply. No records are silently reassigned and no credentials are invented or bypassed.

To activate controlled matching, set `ENABLE_LIVE_MATCHING=YES` and a timezone-aware `MATCHING_ACTIVATION_UTC` on the scheduled worker. Only requests submitted at or after that timestamp qualify. Keep the same email restriction on web and worker services, `EMAIL_SENDING_ENABLED=true`, `SMS_SENDING_ENABLED=false`, and `STRIPE_LIVE_PAYMENTS_ENABLED=false`. The existing cron checks every five minutes; offer notifications expire after 15 minutes. Set `ENABLE_LIVE_MATCHING=NO` to pause.

For the owner's initial trial use `alamotte1956@gmail.com` on the consumer form and the approved account `alamotte19562@gmail.com` on the contractor side. Match the exact service and ZIP, for example **Mold Remediation / 55401**. Submit a fresh request after activation; verify the receipt, offer email, acceptance and consumer update. The up-to-three choice needs three distinct eligible businesses to fill all slots; one account cannot occupy multiple slots. Do not add extra inboxes without designating them for testing.

The administration integrations page displays the web process's matching configuration. Worker configuration and actual execution must also be checked in Railway; an enabled web switch alone does not prove the scheduled worker ran. Stripe mode, purchase activation and evidence-backed pricing are separate gates. Matching/acceptance can be tested while purchases remain disabled; that is not a completed paid-lead test.

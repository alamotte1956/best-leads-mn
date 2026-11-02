# Temporary email testing

Set `EMAIL_TEST_ONLY=true` and `EMAIL_TEST_RECIPIENTS` to a comma-separated list of exact destination addresses before enabling email. An empty or malformed list blocks all email in this mode. Matching is case insensitive. Addresses are never substituted: other recipients' messages remain pending. Enabled SMS is independent and should remain disabled during email-only tests.

The owner-designated test addresses are alamotte1956@gmail.com for consumer requests and alamotte19562@gmail.com for contractor registration. Enter the appropriate address on each form. Do not route unrelated customer records into these inboxes.

Provider setup also requires `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, a verified sender domain, and `EMAIL_SENDING_ENABLED=true`. The notification worker is `flask --app app deliver-notifications`; saving a form queues a receipt but does not itself run that worker. Test-mode provider payloads are marked `[TEST]` and include a test notice. The administrator integrations screen shows whether this restriction is active.

A provider acceptance is not inbox delivery. Configure `RESEND_WEBHOOK_SECRET` and the signed `/webhooks/resend` endpoint to track delivery events. Reconcile `uncertain` or stuck `sending` records with the provider before retrying; never automatically resend them.

Before returning to real recipients: stop the worker, review the pending backlog, deliberately cancel obsolete test messages, configure verified production delivery, and then disable `EMAIL_TEST_ONLY`. Removing the restriction makes all otherwise eligible pending email available to the worker.

Verification: all 263 application tests pass locally, including allowlist enforcement, malformed configuration, backlog selection, direct provider-call protection, a restriction change after claiming a message, and unchanged normal-mode payloads. These automated tests use mocked provider calls; they do not establish actual delivery.

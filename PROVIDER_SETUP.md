# Resend, Twilio and Stripe setup

The code integrations are present. The Albert LaMotte Stripe sandbox is connected through the Stripe plugin and was read successfully; it has no active one-time USD prices. The application runtime still needs protected API keys and webhook secrets. Resend/Twilio account connectivity and live operation have NOT been verified. No real emails, texts or charges were created during development. Provider secrets must be set in protected server environment settings, never in chat, source, browser code or this document. `provider-settings.example` lists the settings without credentials.

## Database and operating controls

Review and apply additive migrations 001 through 004 to an isolated staging PostgreSQL database first. Migration 004 adds daily benchmark evidence and quote fields; historical price rows and payment records are retained. Obtain explicit authorization before production changes. The five expansion states and real rewards remain disabled.

`/admin/integrations` shows enabled switches, missing configuration names and recent delivery/payment statuses without showing key values. Account presence is not proof of provider verification or successful live operation.

## Resend

Resend is the selected email provider for both consumers and contractors. Consumer request receipts, contractor application receipts, contractor lead-offer notifications and contractor payment confirmations use the same Resend outbox. Consumer email remains optional; SMS delivery is separate. This integration sends transactional notifications; two-way inbox/reply handling and marketing campaigns are not implemented.

Verify the sender domain in Resend and configure its required DNS records. Set RESEND_API_KEY and RESEND_FROM_EMAIL to an authorized sender, then enable EMAIL_SENDING_ENABLED only for the intended environment. Homeowner request receipts (where an email was supplied), application receipts, lead-offer emails and payment confirmations are queued transactionally.

The worker calls https://api.resend.com/emails with a stable Idempotency-Key. `sent` means provider acceptance, not inbox delivery. Resend bounce/complaint/delivery webhook ingestion and recipient suppression automation remain follow-up work; do not claim end-to-end email delivery reporting. Resend idempotency keys expire after 24 hours, so uncertain messages are never automatically retried.

## Twilio SMS

The repository already used Twilio for inbound STOP/HELP handling. Configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, an approved TWILIO_MESSAGING_SERVICE_SID and HTTPS TWILIO_STATUS_WEBHOOK_URL ending in /webhooks/twilio/status. Complete sender/campaign approval with the provider before enabling SMS_SENDING_ENABLED. Keep the existing inbound SMS endpoint at /webhooks/twilio/sms and its separately configured public URL.

Offer texts are sent only for current pending offers to active, verified contractors with current recorded credentials, affirmative SMS consent and no STOP suppression. Status callbacks use the SDK signature validator and the configured public URL; terminal delivery states cannot be overwritten by older callbacks. A delivery_id query parameter correlates early callbacks. Homeowner SMS is not enabled because homeowner consent is not collected.

## Worker and uncertainty

Schedule `flask --app app deliver-notifications` in the approved environment. It handles up to 20 pending records per invocation. Multiple invocations claim messages using conditional database updates. Separate channel switches default off. Matching queues offer notifications in the same transaction as creating an offer. Existing matching activation controls remain unchanged.

A provider timeout or process crash after claiming a message can leave `uncertain` or `sending`. Inspect the provider's message records before manually reconciling such a record; do not blindly set it back to pending. The worker prioritizes avoiding duplicate texts over automatic retry availability. No public send endpoint or open email relay exists. Provider-side suppression is still required for opt-out races.

## Stripe Checkout

New checkout uses daily market observations, not assigned Stripe Price mappings. The fee is 85% of the lower comparable Angi/Thumbtack contractor lead fee, rounded down. Evidence must match service, state and ZIP and the current Central calendar day. The daily source adapter is NOT connected; missing evidence blocks quoting. `/admin/pricing` displays observations and readiness without editing prices. See MARKET_PRICING.md for source-access requirements, quote expiry and the trusted refresh command. Set a mode-matching STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, HTTPS origin PUBLIC_SITE_URL and timezone-aware PAYMENTS_ACTIVATION_UTC. Start in STRIPE_MODE=test with PAYMENTS_ENABLED=true for sandbox tests. Live keys additionally require STRIPE_MODE=live and STRIPE_LIVE_PAYMENTS_ENABLED=true.

Only the owner of an accepted offer can request a quote and initiate checkout, and its accepted_at must be on/after the configured activation date. Historical or undated offers are excluded. A saved, expiring quote precedes explicit payment; no automatic charges occur. Stripe receives inline USD price_data from that stored quote, with dynamic payment methods. Existing Minnesota contact access and offer acceptance are preserved. Ownership and an idempotency key control session creation; client-supplied amounts are ignored.

Register /webhooks/stripe for checkout.session.completed, checkout.session.async_payment_succeeded, checkout.session.async_payment_failed and charge.refunded. The handler checks the raw-body signature, test/live mode, linked session, metadata, amount, currency and paid status. Unpaid completion waits for successful payment. Browser return URLs never confirm payment. Distinct duplicate paid events cannot issue duplicate receipts or roll a refunded payment back to paid. Refund totals are monotonic. No rewards credits or prizes are issued by this integration.

Expired/closed checkout reconciliation, disputes and refund initiation require follow-up handling. Do not retry a checkout with a new order or arbitrary database edits; inspect Stripe first. No subscription or auto-purchase flow is included.

## Verification and release limits

Run the automated suite with isolated databases and the browser fallback checks. Tests mock sending/checkout creation but use real Stripe HMAC and Twilio signature verification locally. Before production, run real Resend staging delivery, Twilio approved-recipient tests, Stripe sandbox checkout/refund/replay tests and PostgreSQL concurrency tests. Confirm prices and customer terms. Do not describe the integration as connected or production-ready until those checks and provider configuration succeed.

Official references: [Resend send API](https://resend.com/docs/api-reference/emails/send-email), [Twilio messages](https://www.twilio.com/docs/messaging/api/message-resource), [Stripe fulfillment](https://docs.stripe.com/checkout/fulfillment).

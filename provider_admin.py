"""Provider readiness is visible without exposing credentials."""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from national import administrator
provider_admin = Blueprint('provider_admin',__name__)
PROVIDERS = {
    'Resend email':('EMAIL_SENDING_ENABLED',['RESEND_API_KEY','RESEND_FROM_EMAIL','RESEND_WEBHOOK_SECRET']),
    'Twilio SMS':('SMS_SENDING_ENABLED',['TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_MESSAGING_SERVICE_SID','TWILIO_STATUS_WEBHOOK_URL']),
    'Stripe payments':('PAYMENTS_ENABLED',['STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','PUBLIC_SITE_URL','PAYMENTS_ACTIVATION_UTC'])}
@provider_admin.get('/admin/integrations')
@administrator
def overview():
    from app import Delivery,Payment,EmailSuppression
    providers=[{'name':name,'enabled':os.environ.get(flag,'').lower()=='true',
                'missing':[key for key in keys if not os.environ.get(key)]} for name,(flag,keys) in PROVIDERS.items()]
    return render_template('integrations.html',providers=providers,
        deliveries=Delivery.query.order_by(Delivery.id.desc()).limit(100).all(),
        payments=Payment.query.order_by(Payment.id.desc()).limit(100).all(),
        suppression_count=EmailSuppression.query.count(),
        suppressions=EmailSuppression.query.order_by(EmailSuppression.created_at.desc()).limit(50).all())


@provider_admin.route('/admin/pricing',methods=['GET','POST'])
@administrator
def pricing():
    from app import MarketBenchmark
    from flask import current_app
    if request.method=='POST':
        from contractor_onboarding import require_csrf
        require_csrf()
        abort(409,'Assigned price mappings are disabled. Prices are calculated from daily competitor observations.')
    rows=MarketBenchmark.query.order_by(MarketBenchmark.observed_at.desc()).limit(100).all()
    return render_template('pricing.html',rows=rows,
        configured=callable(current_app.config.get('MARKET_BENCHMARK_COLLECTOR')))

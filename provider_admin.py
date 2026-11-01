"""Provider readiness is visible without exposing credentials."""
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from national import administrator
provider_admin = Blueprint('provider_admin',__name__)
PROVIDERS = {
    'Resend email':('EMAIL_SENDING_ENABLED',['RESEND_API_KEY','RESEND_FROM_EMAIL']),
    'Twilio SMS':('SMS_SENDING_ENABLED',['TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_MESSAGING_SERVICE_SID','TWILIO_STATUS_WEBHOOK_URL']),
    'Stripe payments':('PAYMENTS_ENABLED',['STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','PUBLIC_SITE_URL','PAYMENTS_ACTIVATION_UTC'])}
@provider_admin.get('/admin/integrations')
@administrator
def overview():
    from app import Delivery,Payment
    providers=[{'name':name,'enabled':os.environ.get(flag,'').lower()=='true',
                'missing':[key for key in keys if not os.environ.get(key)]} for name,(flag,keys) in PROVIDERS.items()]
    return render_template('integrations.html',providers=providers,
        deliveries=Delivery.query.order_by(Delivery.id.desc()).limit(100).all(),
        payments=Payment.query.order_by(Payment.id.desc()).limit(100).all())


@provider_admin.route('/admin/pricing',methods=['GET','POST'])
@administrator
def pricing():
    from app import db, LeadPrice
    from contractor_onboarding import require_csrf
    from service_catalog import SERVICES
    from national_markets import STATES
    states={value[0]:value[1] for value in STATES.values()}
    mode=os.environ.get('STRIPE_MODE','test')
    if mode not in ('test','live'):
        abort(503,'Stripe mode is not configured.')
    error=None
    if request.method=='POST':
        require_csrf()
        state=request.form.get('state','')
        service=request.form.get('service','')
        price=request.form.get('stripe_price_id','').strip()
        if state not in states or service not in SERVICES or not price.startswith('price_') or len(price)>150 or not price.replace('_','').isalnum():
            error='Choose a supported state, service and valid Stripe Price ID.'
        else:
            row=LeadPrice.query.filter_by(state_code=state,service_name=service,mode=mode).first()
            if row:row.stripe_price_id=price
            else:db.session.add(LeadPrice(state_code=state,service_name=service,mode=mode,stripe_price_id=price))
            try:db.session.commit()
            except Exception:db.session.rollback();raise
            flash('Price mapping saved. Checkout validates the configured USD one-time Price with Stripe.','success')
            return redirect(url_for('provider_admin.pricing'))
    rows=LeadPrice.query.filter_by(mode=mode).order_by(LeadPrice.state_code,LeadPrice.service_name).all()
    return render_template('pricing.html',states=states,services=SERVICES,mode=mode,rows=rows,error=error),400 if error else 200

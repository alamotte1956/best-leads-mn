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
    from communications import email_test_settings
    email_testing, email_test_recipients = email_test_settings()
    providers=[{'name':name,'enabled':os.environ.get(flag,'').lower()=='true',
                'missing':[key for key in keys if not os.environ.get(key)]} for name,(flag,keys) in PROVIDERS.items()]
    return render_template('integrations.html',providers=providers,
        email_testing=email_testing,email_test_recipients=email_test_recipients,
        deliveries=Delivery.query.order_by(Delivery.id.desc()).limit(100).all(),
        payments=Payment.query.order_by(Payment.id.desc()).limit(100).all(),
        suppression_count=EmailSuppression.query.count(),
        suppressions=EmailSuppression.query.order_by(EmailSuppression.created_at.desc()).limit(50).all())


@provider_admin.route('/admin/pricing',methods=['GET','POST'])
@administrator
def pricing():
    from app import MarketBenchmark, BenchmarkMatchType
    from flask import current_app
    if request.method=='POST':
        from contractor_onboarding import require_csrf
        require_csrf()
        abort(409,'Assigned price mappings are disabled. Prices are calculated from daily competitor observations.')
    rows=MarketBenchmark.query.order_by(MarketBenchmark.observed_at.desc()).limit(100).all()
    from market_pricing import quote_from_benchmark
    from werkzeug.exceptions import HTTPException
    match_types={row.benchmark_id:row.contractor_limit for row in BenchmarkMatchType.query.filter(
        BenchmarkMatchType.benchmark_id.in_([row.id for row in rows])).all()}
    observations=[]
    for row in rows:
        try:
            fee,expiry=quote_from_benchmark(row)
            status='Current evidence'
        except HTTPException as error:
            fee=None;status=error.description
        observations.append(dict(row=row,contractor_limit=match_types.get(row.id,1),fee=fee,status=status))
    from service_catalog import SERVICES
    from national_markets import STATES
    return render_template('pricing.html',observations=observations,services=SERVICES,states=STATES,
        configured=callable(current_app.config.get('MARKET_BENCHMARK_COLLECTOR')))


@provider_admin.get('/admin/pricing/template.csv')
@administrator
def pricing_template():
    from flask import Response
    from pricing_evidence import template_csv
    from consumer_requests import PRIVATE_HEADERS
    response=Response(template_csv(),mimetype='text/csv',headers=PRIVATE_HEADERS)
    response.headers['Content-Disposition']='attachment; filename="authorized-lead-evidence-template.csv"'
    return response


@provider_admin.post('/admin/pricing/import')
@administrator
def pricing_import():
    from contractor_onboarding import require_csrf
    from consumer_requests import PRIVATE_HEADERS
    from pricing_evidence import MAX_BYTES,import_csv
    from sqlalchemy.exc import IntegrityError
    from werkzeug.exceptions import HTTPException
    require_csrf()
    if request.form.get('authorized')!='yes':
        return 'Confirm source permission and like-for-like comparison before importing.',400,PRIVATE_HEADERS
    upload=request.files.get('evidence')
    if not upload:
        return 'Choose a normalized evidence CSV.',400,PRIVATE_HEADERS
    try:
        count=import_csv(upload.stream.read(MAX_BYTES+1))
    except ValueError as error:
        return str(error),400,PRIVATE_HEADERS
    except HTTPException:
        return 'Evidence must be valid, non-future and from the current America/Chicago day. Nothing was imported.',400,PRIVATE_HEADERS
    except IntegrityError:
        from app import db
        db.session.rollback()
        return 'An observation was imported concurrently. Retry the same file; existing evidence will not be overwritten.',409,PRIVATE_HEADERS
    flash(f'Imported {count} new observations. Identical existing observations were skipped. No payment or matching settings were changed.','success')
    return redirect(url_for('provider_admin.pricing'),code=303)

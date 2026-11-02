"""Owner-only management reporting; live receipts and recorded costs stay separate from tests."""
import csv
import io
import re
import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from flask import Blueprint, Response, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from national import administrator
from national_markets import STATES
from contractor_onboarding import require_csrf
from consumer_requests import PRIVATE_HEADERS

finance = Blueprint('finance', __name__)
CENTRAL = ZoneInfo('America/Chicago')
CATEGORIES = ('Advertising', 'Hosting', 'Domains', 'Payment processing', 'Software', 'Labor', 'Insurance', 'Other')
CODES = {info[0] for info in STATES.values()}


def define_owner_finance(db):
    class FinanceEntry(db.Model):
        __tablename__ = 'owner_finance_entries'
        id = db.Column(db.Integer, primary_key=True)
        entry_key = db.Column(db.String(64), unique=True, nullable=False)
        occurred_on = db.Column(db.Date, nullable=False, index=True)
        kind = db.Column(db.String(20), nullable=False)
        category = db.Column(db.String(40), nullable=False)
        description = db.Column(db.String(255), nullable=False)
        amount_cents = db.Column(db.Integer, nullable=False)
        mode = db.Column(db.String(10), nullable=False)
        state_code = db.Column(db.String(2))
        created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        voided_at = db.Column(db.DateTime(timezone=True))
        void_reason = db.Column(db.String(255))
        __table_args__ = (
            db.CheckConstraint('amount_cents > 0 AND amount_cents <= 100000000', name='finance_positive_amount'),
            db.CheckConstraint("kind in ('expense','other_income')", name='finance_entry_kind'),
            db.CheckConstraint("mode in ('live','test')", name='finance_entry_mode'),
        )
    class FinanceReview(db.Model):
        __tablename__ = 'owner_finance_reviews'
        id = db.Column(db.Integer, primary_key=True)
        starts_on = db.Column(db.Date, nullable=False)
        ends_on = db.Column(db.Date, nullable=False)
        mode = db.Column(db.String(10), nullable=False)
        state_code = db.Column(db.String(3), nullable=False, default='ALL')
        confirmed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=db.func.now())
        __table_args__ = (db.UniqueConstraint('starts_on','ends_on','mode','state_code',name='finance_review_period'),)
    return FinanceEntry, FinanceReview


def period(values):
    today = datetime.now(timezone.utc).astimezone(CENTRAL).date()
    try:
        start = date.fromisoformat(values.get('start', today.replace(day=1).isoformat()))
        end = date.fromisoformat(values.get('end', today.isoformat()))
    except (ValueError,TypeError):
        abort(400, 'Enter valid report dates.')
    mode = values.get('mode','live'); state = values.get('state','ALL')
    if end < start or (end-start).days > 366 or mode not in ('live','test') or state not in CODES | {'ALL'}:
        abort(400, 'Check the date range, environment and state. Reports cover up to 367 days.')
    return start,end,mode,state


def amount_cents(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{1,7}(\.[0-9]{1,2})?',value):
        raise ValueError('Enter a positive dollar amount with no more than two decimal places.')
    try: cents=int(Decimal(value)*100)
    except (ValueError,InvalidOperation): raise ValueError('Enter a valid dollar amount.')
    if not 0 < cents <= 100000000: raise ValueError('Amount must be between $0.01 and $1,000,000.')
    return cents


def report_data(start,end,mode,state):
    from app import db, Payment, Lead, LeadMarket, LeadOffer, FinanceEntry, FinanceReview
    first=datetime.combine(start,time.min,tzinfo=CENTRAL).astimezone(timezone.utc)
    last=datetime.combine(end+timedelta(days=1),time.min,tzinfo=CENTRAL).astimezone(timezone.utc)
    payments=db.session.query(Payment).join(LeadOffer, Payment.offer_id==LeadOffer.id).join(
        Lead, Lead.id==LeadOffer.lead_id).outerjoin(LeadMarket,LeadMarket.lead_id==Lead.id).filter(
        Payment.mode==mode,Payment.currency=='usd',Payment.status.in_(('paid','refunded')),
        Payment.paid_at>=first,Payment.paid_at<last)
    if state!='ALL':payments=payments.filter(func.coalesce(LeadMarket.state_code,'MN')==state)
    rows=payments.all()
    gross=sum(p.amount_cents for p in rows); refunds=sum(p.refunded_cents for p in rows)
    expenses=FinanceEntry.query.filter(FinanceEntry.occurred_on>=start,FinanceEntry.occurred_on<=end,FinanceEntry.mode==mode)
    shared=0
    if state!='ALL':
        shared=sum(e.amount_cents for e in expenses.filter(FinanceEntry.state_code.is_(None),FinanceEntry.voided_at.is_(None),FinanceEntry.kind=='expense'))
        expenses=expenses.filter(FinanceEntry.state_code==state)
    entries=expenses.order_by(FinanceEntry.occurred_on.desc(),FinanceEntry.id.desc()).all()
    active=[e for e in entries if e.voided_at is None]
    income=sum(e.amount_cents for e in active if e.kind=='other_income')
    costs=sum(e.amount_cents for e in active if e.kind=='expense')
    fees=sum(e.amount_cents for e in active if e.kind=='expense' and e.category=='Payment processing')
    net=gross-refunds+income; result=net-costs
    review=FinanceReview.query.filter_by(starts_on=start,ends_on=end,mode=mode,state_code=state).first()
    return dict(start=start,end=end,mode=mode,state=state,gross=gross,refunds=refunds,other_income=income,
        net=net,costs=costs,fees=fees,result=result,margin=(Decimal(result)*100/Decimal(net)) if net>0 else None,
        payment_count=len(rows),entries=entries,shared=shared,costs_reviewed=review is not None,
        category_totals={c:sum(e.amount_cents for e in active if e.kind=='expense' and e.category==c) for c in CATEGORIES})



def invalidate_reviews(day,mode):
    from app import FinanceReview
    # A new or voided entry changes every overlapping review, including shared cost reviews.
    FinanceReview.query.filter(FinanceReview.mode==mode,FinanceReview.starts_on<=day,FinanceReview.ends_on>=day).delete(synchronize_session=False)


@finance.after_request
def private(response):
    response.headers.update(PRIVATE_HEADERS); return response


@finance.get('/admin/finance')
@administrator
def dashboard():
    data=report_data(*period(request.args))
    return render_template('owner_finance.html',**data,categories=CATEGORIES,states=STATES,
        entry_key=secrets.token_urlsafe(24))


@finance.post('/admin/finance/entries')
@administrator
def add_entry():
    from app import db, FinanceEntry
    require_csrf(); start,end,mode,state=period(request.form)
    try:
        key=request.form.get('entry_key',''); kind=request.form.get('kind','expense')
        category=request.form.get('category',''); description=request.form.get('description','').strip()
        selected=request.form.get('entry_state','ALL')
        day=date.fromisoformat(request.form.get('occurred_on',''))
        cents=amount_cents(request.form.get('amount',''))
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,64}',key) or kind not in ('expense','other_income'):
            raise ValueError('Invalid entry. Reload the report and try again.')
        if category not in CATEGORIES or not description or len(description)>255 or selected not in CODES|{'ALL'}:
            raise ValueError('Enter a description, category and valid state.')
        if not start<=day<=end:raise ValueError('Choose an entry date within the selected report period.')
        existing=FinanceEntry.query.filter_by(entry_key=key).first()
        if existing:
            if (existing.occurred_on,existing.kind,existing.category,existing.description,existing.amount_cents,existing.mode,existing.state_code)!=(day,kind,category,description,cents,mode,None if selected=='ALL' else selected):
                abort(409,'This entry key was already used for different details.')
        else:
            db.session.add(FinanceEntry(entry_key=key,occurred_on=day,kind=kind,category=category,description=description,
                amount_cents=cents,mode=mode,state_code=None if selected=='ALL' else selected))
            invalidate_reviews(day,mode); db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing=FinanceEntry.query.filter_by(entry_key=key).first()
        if not existing or (existing.occurred_on,existing.kind,existing.category,existing.description,existing.amount_cents,existing.mode,existing.state_code)!=(day,kind,category,description,cents,mode,None if selected=='ALL' else selected):
            abort(409,'The entry could not be saved without a duplicate. Reload and review the existing records.')
    except (ValueError,TypeError) as exc:
        db.session.rollback();abort(400,str(exc))
    return redirect(url_for('finance.dashboard',start=start,end=end,mode=mode,state=state),code=303)


@finance.post('/admin/finance/entries/<int:entry_id>/void')
@administrator
def void_entry(entry_id):
    from app import db, FinanceEntry
    require_csrf(); start,end,mode,state=period(request.form)
    entry=db.session.get(FinanceEntry,entry_id)
    if not entry:abort(404)
    reason=request.form.get('reason','').strip()
    if not reason or len(reason)>255:abort(400,'Enter a correction reason within 255 characters.')
    if entry.voided_at is None:
        entry.voided_at=datetime.now(timezone.utc);entry.void_reason=reason
        invalidate_reviews(entry.occurred_on,entry.mode);db.session.commit()
    return redirect(url_for('finance.dashboard',start=start,end=end,mode=mode,state=state),code=303)


@finance.post('/admin/finance/review')
@administrator
def confirm_costs():
    from app import db, FinanceReview
    require_csrf(); start,end,mode,state=period(request.form)
    if request.form.get('confirm_costs')!='yes':abort(400,'Confirm that all costs for this period have been recorded.')
    row=FinanceReview.query.filter_by(starts_on=start,ends_on=end,mode=mode,state_code=state).first()
    if row:row.confirmed_at=datetime.now(timezone.utc)
    else:db.session.add(FinanceReview(starts_on=start,ends_on=end,mode=mode,state_code=state))
    db.session.commit()
    return redirect(url_for('finance.dashboard',start=start,end=end,mode=mode,state=state),code=303)


def csv_safe(value):
    value=str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value


@finance.get('/admin/finance/export.csv')
@administrator
def export():
    data=report_data(*period(request.args)); out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(['Management report',str(data['start']),str(data['end']),data['mode'],data['state']])
    writer.writerow(['Refunds are allocated to the original payment date; this is not a bank or tax ledger.'])
    for label,key in [('Gross lead receipts','gross'),('Recorded refunds','refunds'),('Other income','other_income'),('Recorded expenses','costs'),('Recorded result','result')]:
        writer.writerow([label,f"{data[key]/100:.2f}"])
    writer.writerow([]);writer.writerow(['Date','Kind','Category','Description','Amount USD','State','Status','Void reason'])
    for e in data['entries']:
        writer.writerow([e.occurred_on,e.kind,e.category,csv_safe(e.description),f'{e.amount_cents/100:.2f}',e.state_code or 'Shared',
            'Voided' if e.voided_at else 'Active',csv_safe(e.void_reason or '')])
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename="restoration-financial-report.csv"'})

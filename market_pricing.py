"""Daily competitor evidence; no assigned prices or fabricated market fallback."""
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
from flask import abort
from sqlalchemy import select

MARKET_ZONE = ZoneInfo('America/Chicago')


def define_benchmark(db):
    class MarketBenchmark(db.Model):
        __tablename__ = 'market_lead_benchmarks'
        id = db.Column(db.Integer, primary_key=True)
        state_code = db.Column(db.String(2), nullable=False)
        service_name = db.Column(db.String(100), nullable=False)
        zip_code = db.Column(db.String(5), nullable=False)
        observed_at = db.Column(db.DateTime(timezone=True), nullable=False)
        angi_cents = db.Column(db.Integer, nullable=False)
        thumbtack_cents = db.Column(db.Integer, nullable=False)
        angi_reference = db.Column(db.String(255), nullable=False)
        thumbtack_reference = db.Column(db.String(255), nullable=False)
        comparison_basis = db.Column(db.String(100), nullable=False)
        import_key = db.Column(db.String(150), unique=True, nullable=False)
        __table_args__ = (db.CheckConstraint('angi_cents > 0 AND thumbtack_cents > 0'),)
    return MarketBenchmark


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def validate_benchmark(row,now=None):
    now=now or datetime.now(timezone.utc)
    observed=aware(row.observed_at)
    if observed > now or observed.astimezone(MARKET_ZONE).date() != now.astimezone(MARKET_ZONE).date():
        abort(503,'A fresh daily market comparison is required.')
    if (type(row.angi_cents) is not int or type(row.thumbtack_cents) is not int
            or min(row.angi_cents,row.thumbtack_cents) <= 0
            or not row.angi_reference.strip() or not row.thumbtack_reference.strip()
            or row.comparison_basis != 'comparable_contractor_lead_fee'):
        abort(503,'Comparable contractor lead-fee evidence is required.')
    return min(row.angi_cents,row.thumbtack_cents)*85//100


def quote_from_benchmark(row,now=None):
    now=now or datetime.now(timezone.utc)
    # Round down: the platform price never exceeds 85% of either observation.
    validate_benchmark(row,now)
    amount=min(row.angi_cents,row.thumbtack_cents)*85//100
    if amount < 1:
        abort(503,'The observed fee cannot produce a payable quote.')
    next_day=now.astimezone(MARKET_ZONE).date()+timedelta(days=1)
    midnight=datetime.combine(next_day,time.min,MARKET_ZONE).astimezone(timezone.utc)
    expires=min(now+timedelta(hours=1),midnight)
    # Hosted Checkout requires at least 30 minutes of session validity.
    if (expires-now).total_seconds() < 31*60:
        abort(503,'The daily quote window is ending. Fresh daily observations are needed before checkout.')
    return amount,expires


def current_benchmark(lead,now=None):
    from app import MarketBenchmark, BenchmarkMatchType
    from lead_choice import match_limit
    from sqlalchemy import func
    now=now or datetime.now(timezone.utc)
    today_start=datetime.combine(now.astimezone(MARKET_ZONE).date(),time.min,MARKET_ZONE).astimezone(timezone.utc)
    from national_coverage import lead_state
    from national_markets import code_enabled
    state = lead_state(lead)
    if not code_enabled(state):
        abort(503, 'This state has not been approved for launch.')
    row=MarketBenchmark.query.outerjoin(BenchmarkMatchType,BenchmarkMatchType.benchmark_id==MarketBenchmark.id).filter(
        func.coalesce(BenchmarkMatchType.contractor_limit,1)==match_limit(lead),MarketBenchmark.state_code==state,
        MarketBenchmark.service_name==lead.service_needed,MarketBenchmark.zip_code==lead.zip_code,
        MarketBenchmark.observed_at>=today_start,MarketBenchmark.observed_at<=now
    ).order_by(MarketBenchmark.observed_at.desc(),MarketBenchmark.id.desc()).first()
    if row is None:
        abort(503,'No fresh comparable Angi and Thumbtack lead fees are available for this market.')
    return row


def refresh_benchmarks():
    """Trusted server collector only. No public page scraping or client prices."""
    from flask import current_app
    collector=current_app.config.get('MARKET_BENCHMARK_COLLECTOR')
    if not callable(collector):
        raise RuntimeError('An authorized Angi/Thumbtack data collector is not configured.')
    return import_benchmark_records(collector())


def import_benchmark_records(records,now=None):
    """Atomically import authorized observations, retaining immutable evidence."""
    from app import db, MarketBenchmark, BenchmarkMatchType
    from lead_choice import parse_choice
    now=now or datetime.now(timezone.utc)
    from service_catalog import SERVICES
    from national_markets import STATES
    states={row[0] for row in STATES.values()}
    count=0
    try:
        for data in records:
            data=dict(data)
            limit=parse_choice(data.pop('contractor_limit',None))
            row=MarketBenchmark(**data)
            if row.state_code not in states or row.service_name not in SERVICES or not row.zip_code.isdigit() or len(row.zip_code)!=5:
                raise ValueError('Market scope does not match the supported catalog.')
            validate_benchmark(row,now)
            if min(row.angi_cents,row.thumbtack_cents)*85//100 < 1:
                raise ValueError('The observed fee cannot produce a payable quote.')
            if not row.import_key or len(row.import_key)>150:
                raise ValueError('A stable observation import key is required.')
            previous=db.session.execute(select(MarketBenchmark).where(MarketBenchmark.import_key==row.import_key)).scalar_one_or_none()
            if previous:
                prior_type=db.session.get(BenchmarkMatchType,previous.id)
                fields=('state_code','service_name','zip_code','angi_cents','thumbtack_cents',
                        'angi_reference','thumbtack_reference','comparison_basis')
                if (any(getattr(previous,key)!=getattr(row,key) for key in fields)
                        or aware(previous.observed_at)!=aware(row.observed_at)
                        or (prior_type.contractor_limit if prior_type else 1)!=limit):
                    raise ValueError('An import key already identifies different evidence. Historical evidence cannot be overwritten.')
                continue
            db.session.add(row);db.session.flush()
            db.session.add(BenchmarkMatchType(benchmark_id=row.id,contractor_limit=limit));count+=1
        db.session.commit()
    except Exception:
        db.session.rollback();raise
    return count

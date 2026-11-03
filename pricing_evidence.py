"""Bounded normalized CSV intake; never scrapes or assumes source permission."""
import csv
import io
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from werkzeug.exceptions import HTTPException

MAX_BYTES=256*1024
MAX_ROWS=500
FIELDS=('state_code','service_name','zip_code','contractor_limit','observed_at',
        'currency','angi_cents','thumbtack_cents','angi_reference','thumbtack_reference',
        'comparison_basis','import_key')


def template_csv():
    stream=io.StringIO(newline='')
    csv.writer(stream).writerow(FIELDS)
    return stream.getvalue()


def reference(value):
    value=value.strip()
    if not 1<=len(value)<=255 or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Source references must contain 1–255 printable characters.')
    # Private document IDs are supported. Do not admit signed/account URLs.
    if '://' in value:
        parts=urlsplit(value)
        if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Use a private document ID or an HTTPS reference without credentials, query strings or fragments.')
    return value


def parse_csv(raw):
    if len(raw)>MAX_BYTES:
        raise ValueError('CSV must be no larger than 256 KB.')
    try:
        stream=io.StringIO(raw.decode('utf-8-sig'),newline='')
        reader=csv.DictReader(stream,strict=True)
        if reader.fieldnames is None or len(reader.fieldnames)!=len(FIELDS) or set(reader.fieldnames)!=set(FIELDS):
            raise ValueError('CSV columns must match the downloaded template exactly.')
        from service_catalog import SERVICES
        from national_markets import STATES
        states={row[0] for row in STATES.values()}
        records=[]
        for number,data in enumerate(reader,start=2):
            if len(records)>=MAX_ROWS:
                raise ValueError('CSV may contain at most 500 observations.')
            try:
                if None in data or any(value is None for value in data.values()):
                    raise ValueError('Every row must have exactly the template columns.')
                data={key:value.strip() for key,value in data.items()}
                if data.pop('currency')!='USD':
                    raise ValueError('Both observations must be comparable USD contractor lead fees.')
                if (data['state_code'] not in states or data['service_name'] not in SERVICES
                        or not re.fullmatch(r'[0-9]{5}',data['zip_code'])):
                    raise ValueError('Use a catalog state, exact service name and five-digit ZIP.')
                if data['contractor_limit'] not in ('1','3'):
                    raise ValueError('Lead type must be 1 or 3; never substitute one type for the other.')
                data['contractor_limit']=int(data['contractor_limit'])
                for key in ('angi_cents','thumbtack_cents'):
                    if not re.fullmatch(r'[0-9]{1,9}',data[key]) or not 1<=int(data[key])<=100000000:
                        raise ValueError('Lead fees must be positive integer cents, at most 100000000.')
                    data[key]=int(data[key])
                observed=datetime.fromisoformat(data['observed_at'].replace('Z','+00:00'))
                if observed.tzinfo is None or observed.utcoffset() is None:
                    raise ValueError('Observation time must include a UTC offset or Z.')
                data['observed_at']=observed.astimezone(timezone.utc)
                for key in ('angi_reference','thumbtack_reference'):
                    data[key]=reference(data[key])
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,149}',data['import_key']):
                    raise ValueError('Use a stable import ID of 1–150 letters, digits, dots, colons, underscores or hyphens.')
                if data['comparison_basis']!='comparable_contractor_lead_fee':
                    raise ValueError('Homeowner estimates and incomparable lead fees are not accepted.')
                from app import MarketBenchmark
                from market_pricing import validate_benchmark
                validate_benchmark(MarketBenchmark(**{k:v for k,v in data.items() if k!='contractor_limit'}))
            except (ValueError,HTTPException):
                # Never echo uploaded cells, which might mistakenly contain private data.
                raise ValueError(f'Row {number} is invalid. Check scope, type, USD cents, source references, import ID and a non-future observation from today in America/Chicago.') from None
            records.append(data)
        if not records:
            raise ValueError('CSV must contain at least one observation. The template contains no sample prices.')
        return records
    except (UnicodeError,csv.Error):
        raise ValueError('Upload a valid UTF-8 CSV using the template.') from None


def import_csv(raw):
    from market_pricing import import_benchmark_records
    return import_benchmark_records(parse_csv(raw))

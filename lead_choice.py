"""Immutable homeowner matching choice and clear contractor disclosures."""
from sqlalchemy import text


def define_lead_choice(db):
    class LeadMatchPreference(db.Model):
        __tablename__='lead_match_preferences'
        lead_id=db.Column(db.Integer,db.ForeignKey('leads.id'),primary_key=True)
        contractor_limit=db.Column(db.Integer,nullable=False)
        created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        __table_args__=(db.CheckConstraint('contractor_limit IN (1,3)',name='lead_choice_one_or_three'),)
    class BenchmarkMatchType(db.Model):
        __tablename__='benchmark_match_types'
        benchmark_id=db.Column(db.Integer,db.ForeignKey('market_lead_benchmarks.id'),primary_key=True)
        contractor_limit=db.Column(db.Integer,nullable=False)
        __table_args__=(db.CheckConstraint('contractor_limit IN (1,3)',name='benchmark_choice_one_or_three'),)
    return LeadMatchPreference,BenchmarkMatchType


def parse_choice(value):
    # Old forms/clients retain the existing one-contractor behavior.
    if value is None:return 1
    if type(value) is int and value in (1,3):return value
    if type(value) is str and value in ('1','3'):return int(value)
    raise ValueError('Choose one contractor or up to three contractors.')


def match_limit(lead,db_session=None):
    from app import db,LeadMatchPreference
    db_session=db_session or db.session
    row=db_session.get(LeadMatchPreference,lead.id)
    return row.contractor_limit if row else 1


def description(limit):
    return ('Single-contractor lead — no more than one contractor can accept this platform request.' if limit==1 else
            'Shared lead — up to three contractors can accept this platform request and may receive the homeowner’s contact details.')


def offer_description(offer):
    from app import db,Lead
    lead=db.session.get(Lead,offer.lead_id)
    return description(match_limit(lead))


# Used inside the same atomic UPDATE as the offer acceptance. PostgreSQL paths
# additionally hold the shared per-lead advisory lock; SQLite serializes writers.
CAPACITY_SQL = """
    AND (SELECT COUNT(DISTINCT other.contractor_id) FROM lead_offers other
         WHERE other.lead_id=lead_offers.lead_id AND other.status='accepted')
        < COALESCE((SELECT contractor_limit FROM lead_match_preferences preference
                    WHERE preference.lead_id=lead_offers.lead_id),1)
    AND NOT EXISTS (SELECT 1 FROM lead_offers duplicate
                    WHERE duplicate.lead_id=lead_offers.lead_id
                      AND duplicate.contractor_id=lead_offers.contractor_id
                      AND duplicate.status='accepted')
"""


def close_filled_slots(db_session,lead_id):
    # Runs only after an accepted transition, under the same transaction/lead lock.
    db_session.execute(text("""
        UPDATE lead_offers SET status='cancelled'
        WHERE lead_id=:lead_id AND status='pending'
        AND (SELECT COUNT(DISTINCT contractor_id) FROM lead_offers accepted
             WHERE accepted.lead_id=:lead_id AND accepted.status='accepted')
            >= COALESCE((SELECT contractor_limit FROM lead_match_preferences
                         WHERE lead_id=:lead_id),1)
    """),{'lead_id':lead_id})

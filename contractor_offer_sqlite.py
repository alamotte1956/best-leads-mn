"""Atomic local SQLite offer actions. Production keeps PostgreSQL lead locks."""
from sqlalchemy import text
from lead_choice import CAPACITY_SQL

def transition(session, offer_id, contractor_id, action):
    if action not in ('accepted', 'declined'):
        raise ValueError('Invalid action')
    column = 'accepted_at' if action == 'accepted' else 'declined_at'
    # The single SQLite writer serializes this statement, including its subquery.
    result = session.execute(text(f'''
        UPDATE lead_offers SET status = :action, {column} = strftime('%Y-%m-%d %H:%M:%f','now')
        WHERE id = :offer_id AND contractor_id = :contractor_id
        AND status = 'pending' AND accepted_at IS NULL AND declined_at IS NULL
        AND julianday(expires_at) > julianday('now') AND julianday(offered_at) <= julianday('now')
        AND EXISTS (SELECT 1 FROM leads WHERE leads.id = lead_offers.lead_id AND leads.status = 'New')
        {CAPACITY_SQL}
        RETURNING id, lead_id, contractor_id, {column}
    '''), {'action': action, 'offer_id': offer_id, 'contractor_id': contractor_id}).mappings().first()
    if result and action=='accepted':
        from lead_choice import close_filled_slots
        close_filled_slots(session,result['lead_id'])
    return dict(result) if result else None

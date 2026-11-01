"""Atomic local SQLite offer actions. Production keeps PostgreSQL lead locks."""
from sqlalchemy import text

def transition(session, offer_id, contractor_id, action):
    if action not in ('accepted', 'declined'):
        raise ValueError('Invalid action')
    column = 'accepted_at' if action == 'accepted' else 'declined_at'
    # The single SQLite writer serializes this statement, including its subquery.
    result = session.execute(text(f'''
        UPDATE lead_offers SET status = :action, {column} = CURRENT_TIMESTAMP
        WHERE id = :offer_id AND contractor_id = :contractor_id
        AND status = 'pending' AND accepted_at IS NULL AND declined_at IS NULL
        AND expires_at > CURRENT_TIMESTAMP AND offered_at <= CURRENT_TIMESTAMP
        AND EXISTS (SELECT 1 FROM leads WHERE leads.id = lead_offers.lead_id AND leads.status = 'New')
        AND NOT EXISTS (SELECT 1 FROM lead_offers other
            WHERE other.lead_id = lead_offers.lead_id AND other.status = 'accepted')
        RETURNING id, lead_id, contractor_id, {column}
    '''), {'action': action, 'offer_id': offer_id, 'contractor_id': contractor_id}).mappings().first()
    return dict(result) if result else None

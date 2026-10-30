from sqlalchemy import text
from app import app, db

with app.app_context():
    result = db.session.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM leads) AS leads,
                (SELECT COUNT(*) FROM contractors) AS contractors,
                (SELECT COUNT(*) FROM lead_offers) AS offers
        """)
    ).one()

    print("DATABASE CONNECTION: PASS")
    print("Homeowner leads:", result.leads)
    print("Contractors:", result.contractors)
    print("Contractor offers:", result.offers)

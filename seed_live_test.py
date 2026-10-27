import app
with app.app.app_context():
    new_lead = app.Lead(name='David Sterling', phone='(612) 555-0988', email='dsterling@example.com', zip_code='55402', service_type='Water Damage Restoration', status='New')
    app.db.session.add(new_lead)
    app.db.session.commit()
    print('Live consumer lead test record added successfully.')

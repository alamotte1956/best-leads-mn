import app
with app.app.app_context():
    app.db.create_all()
    if not app.Contractor.query.first():
        c = app.Contractor(company_name='Twin Cities Water Pros', contact_name='Dave Miller', phone='(612) 555-0144', email='info@twincitieswaterpros.com', license_number='BC998877', service_type='Water Damage Restoration', service_radius_zip='55401')
        app.db.session.add(c)
    if not app.Lead.query.filter_by(name='David Sterling').first():
        l = app.Lead(name='David Sterling', phone='(612) 555-0988', email='dsterling@example.com', zip_code='55402', service_type='Water Damage Restoration', status='New')
        app.db.session.add(l)
    app.db.session.commit()
    print('Database seeded successfully.')

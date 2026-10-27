import app
with app.app.app_context():
    if not app.Lead.query.first():
        sample_lead = app.Lead(name='Sarah Jenkins', phone='(612) 555-0188', email='sarah@example.com', zip_code='55401', service_type='Water Damage Restoration', status='New')
        sample_contractor = app.Contractor(company_name='Twin Cities Water Pros', contact_name='Dave Miller', phone='(612) 555-0144', email='info@twincitieswaterpros.com', license_number='BC998877', service_type='Water Damage Restoration', service_radius_zip='55401')
        app.db.session.add(sample_lead)
        app.db.session.add(sample_contractor)
        app.db.session.commit()
        print('Sample lead and contractor seeded successfully.')
    else:
        print('Sample records already exist.')

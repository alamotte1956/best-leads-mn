import app
with app.app.app_context():
    more_leads = [
        app.Lead(name='Robert Larson', phone='(952) 555-0211', email='robert@example.com', zip_code='55435', service_type='Roofing & Storm Repair', status='New'),
        app.Lead(name='Elena Rostova', phone='(651) 555-0399', email='elena@example.com', zip_code='55101', service_type='Mold Remediation', status='Contacted')
    ]
    more_contractors = [
        app.Contractor(company_name='Metro Roofing & Remodeling', contact_name='Tom Bradley', phone='(952) 555-0199', email='support@metroroofingmn.com', license_number='BC887766', service_type='Roofing & Storm Repair', service_radius_zip='55435'),
        app.Contractor(company_name='NorthStar Mold & Air', contact_name='Sarah Connor', phone='(651) 555-0455', email='contact@northstarmold.com', license_number='BC776655', service_type='Mold Remediation', service_radius_zip='55101')
    ]
    app.db.session.add_all(more_leads)
    app.db.session.add_all(more_contractors)
    app.db.session.commit()
    print('Additional sample marketplace records seeded successfully.')

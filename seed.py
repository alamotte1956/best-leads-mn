from app import app, db, Contractor
with app.app_context():
    db.create_all()
    if not Contractor.query.first():
        sample = Contractor(
            company_name='Twin Cities Water Pros',
            contact_name='Mike Larson',
            phone='(612) 555-0144',
            email='dispatch@twincitieswaterpros.com',
            license_number='BC789123',
            service_type='Water Damage Restoration',
            service_radius_zip='55401',
            rating=5.0,
            verified=True
        )
        db.session.add(sample)
        db.session.commit()
        print('Sample contractor seeded successfully.')
    else:
        print('Database already contains records.')

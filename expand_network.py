from app import app, db, Contractor, Lead

with app.app_context():
    db.create_all()
    
    # Add premier Twin Cities restoration partners if not already present
    pros = [
        {
            'company_name': 'Twin Cities Water Pros',
            'contact_name': 'Mike Larson',
            'phone': '(612) 555-0144',
            'email': 'dispatch@twincitieswaterpros.com',
            'license_number': 'BC789123',
            'service_type': 'Water Damage Restoration',
            'service_radius_zip': '55401',
            'rating': 5.0,
            'verified': True
        },
        {
            'company_name': 'Metro Storm & Roofing Experts',
            'contact_name': 'Sarah Jenkins',
            'phone': '(612) 555-0188',
            'email': 'claims@metrostormmn.com',
            'license_number': 'BC456789',
            'service_type': 'Storm & Wind Repair',
            'service_radius_zip': '55101',
            'rating': 4.9,
            'verified': True
        },
        {
            'company_name': 'Minnesota Mold & Air Quality',
            'contact_name': 'David O\'Connor',
            'phone': '(651) 555-0122',
            'email': 'help@mnmoldfree.com',
            'license_number': 'BC987654',
            'service_type': 'Mold Remediation',
            'service_radius_zip': '55402',
            'rating': 5.0,
            'verified': True
        },
        {
            'company_name': 'North Star Fire & Smoke Restoration',
            'contact_name': 'Robert Vance',
            'phone': '(612) 555-0177',
            'email': 'emergency@northstarfire.com',
            'license_number': 'BC321654',
            'service_type': 'Fire & Smoke Restoration',
            'service_radius_zip': '55403',
            'rating': 4.9,
            'verified': True
        }
    ]

    for p in pros:
        if not Contractor.query.filter_by(license_number=p['license_number']).first():
            contractor = Contractor(**p)
            db.session.add(contractor)

    # Add sample high-intent emergency lead
    if not Lead.query.first():
        sample_lead = Lead(
            name='Jessica Reynolds',
            phone='(612) 555-0199',
            email='jessica.reynolds@example.com',
            zip_code='55401',
            service_type='Water Damage Restoration',
            description='Burst pipe in basement affecting finished drywall and flooring. Needs urgent extraction.',
            status='New - Instant Match'
        )
        db.session.add(sample_lead)

    db.session.commit()
    print('Twin Cities contractor network expanded and sample lead seeded successfully.')

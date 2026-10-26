@app.route('/contractors/signup', methods=['GET', 'POST'], strict_slashes=False)
def contractor_signup():
    if request.method == 'POST':
        try:
            new_contractor = Contractor(
                company_name=request.form.get('company_name'),
                contact_name=request.form.get('contact_name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                license_number=request.form.get('license_number')
            )
            db.session.add(new_contractor)
            db.session.commit()
            flash('Contractor registration successful!', 'success')
            return redirect(url_for('contractor_signup'))
        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Email or license may already be registered.', 'error')
    return render_template('contractor_signup.html')

@app.route('/admin', strict_slashes=False)
def admin_dashboard():
    leads = Lead.query.all()
    contractors = Contractor.query.all()
    return render_template('admin.html', leads=leads, contractors=contractors)
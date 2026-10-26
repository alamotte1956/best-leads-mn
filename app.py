import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'restoration-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///leads.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='New')

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    service_radius_zip = db.Column(db.String(10), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    credits = db.Column(db.Integer, default=5)
    status = db.Column(db.String(20), default='Active')

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        zip_code = request.form.get('zip_code')
        service_type = request.form.get('service_type')
        
        new_lead = Lead(name=name, phone=phone, email=email, zip_code=zip_code, service_type=service_type)
        db.session.add(new_lead)
        db.session.commit()
        
        flash('Your restoration request has been submitted successfully! Local pros are being notified.', 'success')
        return redirect(url_for('index'))
        
    return render_template('index.html')

@app.route('/contractors/signup', methods=['GET', 'POST'])
def contractor_signup():
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        contact_name = request.form.get('contact_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        license_number = request.form.get('license_number')
        service_radius_zip = request.form.get('service_radius_zip')
        service_type = request.form.get('service_type')
        
        new_contractor = Contractor(
            company_name=company_name,
            contact_name=contact_name,
            phone=phone,
            email=email,
            license_number=license_number,
            service_radius_zip=service_radius_zip,
            service_type=service_type
        )
        db.session.add(new_contractor)
        db.session.commit()
        
        flash('Contractor account created successfully! Welcome to the Restoration Contractors MN network.', 'success')
        return redirect(url_for('contractor_signup'))
        
    return render_template('contractor_signup.html')

@app.route('/admin')
def admin():
    leads = Lead.query.all()
    contractors = Contractor.query.all()
    return render_template('admin.html', leads=leads, contractors=contractors)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

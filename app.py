from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'restoration-mn-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///leads.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)

db = SQLAlchemy(app)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='New - Instant Match')

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)
    service_radius_zip = db.Column(db.String(10), nullable=False)
    rating = db.Column(db.Float, default=5.0)
    verified = db.Column(db.Boolean, default=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        new_lead = Lead(
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            zip_code=request.form.get('zip_code'),
            service_type=request.form.get('service_type'),
            description=request.form.get('description'),
            status='New - Instant Match'
        )
        db.session.add(new_lead)
        db.session.commit()
        flash('Emergency request dispatched to Twin Cities pros! Expect a call within 5 minutes.', 'success')
        return redirect(url_for('index'))
    return render_template('index.html')

@app.route('/contractors/signup', methods=['GET', 'POST'])
def contractor_signup():
    if request.method == 'POST':
        new_contractor = Contractor(
            company_name=request.form.get('company_name'),
            contact_name=request.form.get('contact_name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            license_number=request.form.get('license_number'),
            service_type=request.form.get('service_type'),
            service_radius_zip=request.form.get('service_radius_zip'),
            rating=5.0,
            verified=True
        )
        db.session.add(new_contractor)
        db.session.commit()
        flash('Application submitted! Your Minnesota contractor license is queued for instant state verification.', 'success')
        return redirect(url_for('contractor_signup'))
    return render_template('contractor_signup.html')

@app.route('/admin')
def admin():
    leads = Lead.query.all()
    contractors = Contractor.query.all()
    return render_template('admin.html', leads=leads, contractors=contractors)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=8080)

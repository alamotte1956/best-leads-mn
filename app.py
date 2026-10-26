import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///leads.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'], strict_slashes=False)
def index():
    if request.method == 'POST':
        try:
            new_lead = Lead(
                name=request.form.get('name'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                zip_code=request.form.get('zip_code'),
                service_type=request.form.get('service_type')
            )
            db.session.add(new_lead)
            db.session.commit()
            flash('Your restoration request has been submitted successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while submitting your request. Please try again.', 'error')
    return render_template('index.html')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

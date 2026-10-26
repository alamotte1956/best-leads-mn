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
    homeowner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    damage_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='New')

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    is_active_subscriber = db.Column(db.Boolean, default=True)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit-lead', methods=['POST'])
def submit_lead():
    try:
        new_lead = Lead(
            homeowner_name=request.form.get('homeowner_name'),
            phone=request.form.get('phone'),
            city=request.form.get('city'),
            zip_code=request.form.get('zip_code'),
            damage_type=request.form.get('damage_type')
        )
        db.session.add(new_lead)
        db.session.commit()
        flash('Your request has been submitted successfully. A licensed contractor will contact you shortly.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while submitting your request. Please try again.', 'error')
    return redirect(url_for('index'))

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
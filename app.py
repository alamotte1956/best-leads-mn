import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')

# Database Configuration (PostgreSQL on Railway or local SQLite fallback)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///best_leads.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    homeowner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    damage_type = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='Unassigned')

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    is_active_subscriber = db.Column(db.Boolean, default=False)

# Ensure database tables are created within application context
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
        flash('Lead submitted successfully! A verified contractor will contact you shortly.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error submitting lead. Please try again.', 'error')
    return redirect(url_for('index'))

@app.route('/contractors/signup', methods=['GET', 'POST'])
def contractor_signup():
    if request.method == 'POST':
        try:
            new_contractor = Contractor(
                company_name=request.form.get('company_name'),
                contact_name=request.form.get('contact_name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                license_number=request.form.get('license_number'),
                is_active_subscriber=True  # Auto-activate for testing/sandbox
            )
            db.session.add(new_contractor)
            db.session.commit()
            flash('Registration successful! Welcome to the network.', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Email already registered or invalid input.', 'error')
    return render_template('contractor_signup.html')

@app.route('/admin')
def admin_dashboard():
    leads = Lead.query.all()
    contractors = Contractor.query.all()
    return render_template('admin.html', leads=leads, contractors=contractors)

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
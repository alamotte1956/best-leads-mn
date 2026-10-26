import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///leads.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    damage_type = db.Column(db.String(50), nullable=False)

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    service_zips = db.Column(db.String(500), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        lead = Lead(
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            zip_code=request.form.get('zip_code'),
            damage_type=request.form.get('damage_type')
        )
        db.session.add(lead)
        db.session.commit()
        flash('Lead submitted successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('index.html')

@app.route('/contractors/signup', methods=['GET', 'POST'])
def contractor_signup():
    if request.method == 'POST':
        contractor = Contractor(
            company_name=request.form.get('company_name'),
            contact_name=request.form.get('contact_name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            service_zips=request.form.get('service_zips')
        )
        db.session.add(contractor)
        db.session.commit()
        flash('Contractor registered successfully!', 'success')
        return redirect(url_for('contractor_signup'))
    return render_template('contractor_signup.html')

@app.route('/admin', strict_slashes=False)
def admin_dashboard():
    leads = Lead.query.all()
    contractors = Contractor.query.all()
    return render_template('admin.html', leads=leads, contractors=contractors)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
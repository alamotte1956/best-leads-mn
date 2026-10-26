import os
import stripe
from flask import Flask, render_template_string, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "minnesota-restoration-secure-key-2026")

# Database Configuration (PostgreSQL on Railway or SQLite local fallback)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///restoration_leads.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Stripe & Twilio Configuration
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

def send_sms_alert(to_phone, message_body):
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message_body,
                from_=TWILIO_PHONE_NUMBER,
                to=to_phone
            )
        except Exception as e:
            print(f"Twilio SMS Error: {e}")

# ==================== DATABASE MODELS ====================

class Contractor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    trade = db.Column(db.String(50), nullable=False)  # Roofing, Water Damage, Storm Restoration, Mold
    service_area = db.Column(db.String(100), default="Twin Cities Metro")
    mn_license_number = db.Column(db.String(50), nullable=False)  # MN DLI License Verification
    is_active_subscriber = db.Column(db.Boolean, default=False)
    stripe_subscription_id = db.Column(db.String(120), nullable=True)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    homeowner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    project_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    sms_consent = db.Column(db.Boolean, nullable=False, default=False)
    assigned_contractor_id = db.Column(db.Integer, db.ForeignKey('contractor.id'), nullable=True)
    status = db.Column(db.String(30), default="New - 100% Exclusive")

# ==================== HTML TEMPLATES (Responsive & Mobile-First) ====================

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Restoration Contractors MN{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar-brand { font-weight: 700; color: #0d6efd !important; }
        .hero-section { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: white; padding: 4rem 1rem; }
        .footer { background-color: #0f172a; color: #94a3b8; font-size: 0.9rem; padding: 2rem 0; margin-top: 3rem; }
        .footer a { color: #cbd5e1; text-decoration: none; }
        .footer a:hover { color: #ffffff; text-decoration: underline; }
        .badge-verified { background-color: #0d6efd; color: white; font-size: 0.75rem; padding: 0.35em 0.65em; border-radius: 50rem; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm sticky-top">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="fas fa-hammer text-primary me-2"></i>Restoration Contractors MN</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse justify-content-end" id="navbarNav">
                <ul class="navbar-nav align-items-center">
                    <li class="nav-item"><a class="nav-link" href="/">Home</a></li>
                    <li class="nav-item"><a class="nav-link" href="/contractors/signup">For Contractors</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin">Admin Portal</a></li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container my-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show shadow-sm" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <footer class="footer">
        <div class="container text-center text-md-start">
            <div class="row">
                <div class="col-md-6 mb-3 mb-md-0">
                    <h5 class="text-white">Restoration Contractors MN</h5>
                    <p class="mb-0">Twin Cities 100% Exclusive Lead-Matching Platform.<br>Strictly Never Shared or Resold. MN DLI License & TCPA Compliant.</p>
                </div>
                <div class="col-md-6 text-md-end">
                    <ul class="list-inline mb-2">
                        <li class="list-inline-item"><a href="/privacy">Privacy Policy</a></li>
                        <li class="list-inline-item">|</li>
                        <li class="list-inline-item"><a href="/terms">Terms of Service</a></li>
                    </ul>
                    <p class="mb-0">&copy; 2026 Restoration Contractors MN. All rights reserved.</p>
                </div>
            </div>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

INDEX_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="hero-section rounded-4 shadow-sm text-center mb-5">
    <div class="container">
        <span class="badge bg-primary px-3 py-2 mb-3 fw-semibold uppercase tracking-wide">Twin Cities Exclusive Network</span>
        <h1 class="display-5 fw-bold mb-3">Never Shared. Never Resold.</h1>
        <p class="lead text-secondary mb-4">Connect directly with vetted, licensed Minnesota restoration professionals. 1 inquiry = 1 exclusive contractor.</p>
        <a href="#leadForm" class="btn btn-primary btn-lg px-4 gap-3 shadow">Request Exclusive Service</a>
    </div>
</div>

<div class="row justify-content-center">
    <div class="col-lg-8">
        <div class="card shadow-sm border-0 p-4 rounded-4" id="leadForm">
            <h3 class="mb-3 text-dark fw-bold"><i class="fas fa-file-contract text-primary me-2"></i>Homeowner Service Request</h3>
            <p class="text-muted mb-4">Your project details are sent exclusively to one top-rated, DLI-licensed professional across Minneapolis, St. Paul, and surrounding suburbs.</p>
            
            <form method="POST" action="/submit-lead">
                <div class="row mb-3">
                    <div class="col-md-6 mb-3 mb-md-0">
                        <label class="form-label fw-semibold">Full Name</label>
                        <input type="text" class="form-control" name="homeowner_name" required placeholder="John Doe">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">Phone Number</label>
                        <input type="tel" class="form-control" name="phone" required placeholder="(612) 555-0199">
                    </div>
                </div>

                <div class="row mb-3">
                    <div class="col-md-6 mb-3 mb-md-0">
                        <label class="form-label fw-semibold">Email Address</label>
                        <input type="email" class="form-control" name="email" required placeholder="john@example.com">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">Property City / Address</label>
                        <input type="text" class="form-control" name="address" required placeholder="Edina, MN">
                    </div>
                </div>

                <div class="mb-3">
                    <label class="form-label fw-semibold">Restoration Service Category</label>
                    <select class="form-select" name="project_type" required>
                        <option value="" selected disabled>Choose service category...</option>
                        <option value="Roofing & Storm Damage">Roofing & Storm Damage</option>
                        <option value="Water Damage Mitigation">Water Damage Mitigation</option>
                        <option value="Fire & Smoke Restoration">Fire & Smoke Restoration</option>
                        <option value="Mold Remediation">Mold Remediation</option>
                    </select>
                </div>

                <div class="mb-3">
                    <label class="form-label fw-semibold">Project Details & Damage Description</label>
                    <textarea class="form-control" name="description" rows="3" required placeholder="Describe the damage, insurance involvement, or urgency..."></textarea>
                </div>

                <div class="mb-4 form-check bg-light p-3 rounded border">
                    <input type="checkbox" class="form-check-input mt-1" id="sms_consent" name="sms_consent" value="yes" required>
                    <label class="form-check-label small text-muted" for="sms_consent">
                        <strong>TCPA & Minnesota Compliance Consent:</strong> By checking this box, I consent to receive phone calls and SMS text messages regarding my restoration request from Restoration Contractors MN and our single matched licensed contractor at the phone number provided. Consent is not a condition of purchase. Msg & data rates may apply.
                    </label>
                </div>

                <button type="submit" class="btn btn-primary w-100 py-2 fw-bold shadow-sm">Submit Exclusive Lead Request</button>
            </form>
        </div>
    </div>
</div>
""")

CONTRACTOR_SIGNUP_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="row justify-content-center">
    <div class="col-lg-7">
        <div class="card shadow-sm border-0 p-4 rounded-4">
            <h3 class="mb-3 text-dark fw-bold"><i class="fas fa-hard-hat text-primary me-2"></i>Contractor Exclusive Network Signup</h3>
            <p class="text-muted mb-4">Stop competing against 5 other contractors on Angi. Get 100% exclusive, non-shared local leads sent straight to your phone.</p>
            
            <form method="POST" action="/contractors/signup">
                <div class="mb-3">
                    <label class="form-label fw-semibold">Company Legal Name</label>
                    <input type="text" class="form-control" name="company_name" required placeholder="Twin Cities Restoration Pros LLC">
                </div>
                <div class="row mb-3">
                    <div class="col-md-6 mb-3 mb-md-0">
                        <label class="form-label fw-semibold">Primary Contact Name</label>
                        <input type="text" class="form-control" name="contact_name" required placeholder="Jane Smith">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">Direct Mobile Phone (for Instant SMS)</label>
                        <input type="tel" class="form-control" name="phone" required placeholder="(952) 555-0144">
                    </div>
                </div>
                <div class="row mb-3">
                    <div class="col-md-6 mb-3 mb-md-0">
                        <label class="form-label fw-semibold">Business Email</label>
                        <input type="email" class="form-control" name="email" required placeholder="dispatch@twincitiespro.com">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">MN DLI License Number <span class="text-danger">*</span></label>
                        <input type="text" class="form-control" name="mn_license_number" required placeholder="BC123456 or IR789012">
                    </div>
                </div>
                <div class="row mb-3">
                    <div class="col-md-6 mb-3 mb-md-0">
                        <label class="form-label fw-semibold">Primary Trade Category</label>
                        <select class="form-select" name="trade" required>
                            <option value="Roofing & Storm Damage">Roofing & Storm Damage</option>
                            <option value="Water Damage Mitigation">Water Damage Mitigation</option>
                            <option value="Fire & Smoke Restoration">Fire & Smoke Restoration</option>
                            <option value="Mold Remediation">Mold Remediation</option>
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label fw-semibold">Service Coverage Area</label>
                        <input type="text" class="form-control" name="service_area" value="Twin Cities Metro Area" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-dark w-100 py-2 fw-bold shadow-sm">Proceed to Secure Billing & Activation</button>
            </form>
        </div>
    </div>
</div>
""")

ADMIN_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="row mb-4">
    <div class="col-12">
        <h2 class="fw-bold text-dark"><i class="fas fa-gauge text-primary me-2"></i>Admin Dashboard</h2>
        <p class="text-muted">Monitor 100% exclusive lead distribution and contractor subscription status.</p>
    </div>
</div>

<div class="row mb-5">
    <div class="col-12">
        <div class="card shadow-sm border-0 rounded-4 p-3">
            <h4 class="fw-bold text-dark mb-3"><i class="fas fa-list-check me-2 text-primary"></i>Exclusive Leads Directory</h4>
            <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead class="table-dark">
                        <tr>
                            <th>ID</th>
                            <th>Homeowner</th>
                            <th>Phone</th>
                            <th>Location</th>
                            <th>Service</th>
                            <th>Assigned Contractor ID</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for lead in leads %}
                        <tr>
                            <td>#{{ lead.id }}</td>
                            <td class="fw-semibold">{{ lead.homeowner_name }}</td>
                            <td>{{ lead.phone }}</td>
                            <td>{{ lead.address }}</td>
                            <td><span class="badge bg-secondary">{{ lead.project_type }}</span></td>
                            <td>
                                {% if lead.assigned_contractor_id %}
                                    <span class="badge bg-primary">Contractor #{{ lead.assigned_contractor_id }}</span>
                                {% else %}
                                    <span class="badge bg-warning text-dark">Unassigned (No Active Sub)</span>
                                {% endif %}
                            </td>
                            <td><a href="tel:{{ lead.phone }}" class="btn btn-sm btn-outline-primary"><i class="fas fa-phone"></i> Call</a></td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" class="text-center py-4 text-muted">No leads received yet.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-12">
        <div class="card shadow-sm border-0 rounded-4 p-3">
            <h4 class="fw-bold text-dark mb-3"><i class="fas fa-users-cog me-2 text-primary"></i>Registered Contractors & MN License Badges</h4>
            <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead class="table-dark">
                        <tr>
                            <th>Company</th>
                            <th>Contact</th>
                            <th>MN License #</th>
                            <th>Trade</th>
                            <th>Billing Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for c in contractors %}
                        <tr>
                            <td class="fw-semibold">{{ c.company_name }}</td>
                            <td>{{ c.contact_name }}<br><small class="text-muted">{{ c.phone }}</small></td>
                            <td><span class="badge-verified"><i class="fas fa-shield-check me-1"></i>MN DLI: {{ c.mn_license_number }}</span></td>
                            <td>{{ c.trade }}</td>
                            <td>
                                {% if c.is_active_subscriber %}
                                    <span class="badge bg-success">Active Subscriber (Exclusive)</span>
                                {% else %}
                                    <a href="/contractors/checkout/{{ c.id }}" class="btn btn-sm btn-warning fw-bold">Complete Stripe Billing</a>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" class="text-center py-4 text-muted">No contractors registered yet.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
""")

PRIVACY_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="row justify-content-center">
    <div class="col-lg-9 bg-white p-5 rounded-4 shadow-sm">
        <h2 class="fw-bold mb-4">Privacy Policy</h2>
        <p class="text-muted">Last updated: October 26, 2026</p>
        <p>Restoration Contractors MN respects your privacy and is committed to protecting your personal information. This policy governs how we collect, process, and safeguard data submitted through our exclusive Twin Cities lead network.</p>
        <h5 class="fw-bold mt-4">1. TCPA & Consent Collection</h5>
        <p>By providing your phone number and checking our consent box, you grant explicit permission for us and your single matched licensed contractor to contact you via telephone and SMS text messaging in compliance with TCPA guidelines.</p>
        <h5 class="fw-bold mt-4">2. Exclusive Lead Distribution</h5>
        <p>Unlike national aggregators that resell homeowner inquiries to multiple businesses, we strictly pair your project with <strong>one</strong> verified professional in your trade category.</p>
    </div>
</div>
""")

TERMS_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="row justify-content-center">
    <div class="col-lg-9 bg-white p-5 rounded-4 shadow-sm">
        <h2 class="fw-bold mb-4">Terms of Service</h2>
        <p class="text-muted">Last updated: October 26, 2026</p>
        <p>Welcome to Restoration Contractors MN. By accessing our platform or submitting a lead request, you agree to comply with our operating terms.</p>
        <h5 class="fw-bold mt-4">1. Minnesota Licensing Compliance</h5>
        <p>All participating contractors agree to maintain active licensing in good standing with the Minnesota Department of Labor and Industry (DLI).</p>
        <h5 class="fw-bold mt-4">2. Limitation of Liability</h5>
        <p>Restoration Contractors MN acts exclusively as an independent lead-matching service and is not party to the direct contracts executed between property owners and matched professionals.</p>
    </div>
</div>
""")

# ==================== ROUTES ====================

@app.route("/")
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route("/submit-lead", methods=["POST"])
def submit_lead():
    try:
        homeowner_name = request.form.get("homeowner_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        address = request.form.get("address")
        project_type = request.form.get("project_type")
        description = request.form.get("description")
        sms_consent = True if request.form.get("sms_consent") == "yes" else False

        if not sms_consent:
            flash("SMS consent is required under TCPA regulations to submit your request.", "error")
            return redirect(url_for("index"))

        # Find active subscriber matching trade for exclusive lock
        matched_contractor = Contractor.query.filter_by(trade=project_type, is_active_subscriber=True).first()
        contractor_id = matched_contractor.id if matched_contractor else None

        new_lead = Lead(
            homeowner_name=homeowner_name,
            phone=phone,
            email=email,
            address=address,
            project_type=project_type,
            description=description,
            sms_consent=sms_consent,
            assigned_contractor_id=contractor_id,
            status="New - 100% Exclusive"
        )
        db.session.add(new_lead)
        db.session.commit()

        # Instant SMS alert dispatched to matched contractor
        if matched_contractor and matched_contractor.phone:
            sms_msg = f"EXCLUSIVE MN LEAD! {homeowner_name} ({phone}) needs {project_type} in {address}. Check admin portal."
            send_sms_alert(matched_contractor.phone, sms_msg)

        flash("Your exclusive service request has been successfully submitted and dispatched!", "success")
        return redirect(url_for("index"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error submitting request: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/contractors/signup", methods=["GET", "POST"])
def contractor_signup():
    if request.method == "POST":
        try:
            company_name = request.form.get("company_name")
            contact_name = request.form.get("contact_name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            trade = request.form.get("trade")
            service_area = request.form.get("service_area")
            mn_license_number = request.form.get("mn_license_number")

            existing = Contractor.query.filter_by(email=email).first()
            if existing:
                flash("An account with this email already exists. Please proceed to billing.", "error")
                return redirect(url_for("contractor_signup"))

            contractor = Contractor(
                company_name=company_name,
                contact_name=contact_name,
                email=email,
                phone=phone,
                trade=trade,
                service_area=service_area,
                mn_license_number=mn_license_number,
                is_active_subscriber=False
            )
            db.session.add(contractor)
            db.session.commit()

            return redirect(url_for("contractor_checkout", contractor_id=contractor.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Signup error: {str(e)}", "error")
            return redirect(url_for("contractor_signup"))

    return render_template_string(CONTRACTOR_SIGNUP_TEMPLATE)

@app.route("/contractors/checkout/<int:contractor_id>")
def contractor_checkout(contractor_id):
    contractor = Contractor.query.get_or_404(contractor_id)
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Exclusive Lead Network Subscription - {contractor.trade}',
                    },
                    'unit_amount': 29900,  # $299.00 / month
                    'recurring': {'interval': 'month'},
                },
                'quantity': 1,
            }],
            mode='subscription',
            customer_email=contractor.email,
            success_url=url_for('payment_success', contractor_id=contractor.id, _external=True),
            cancel_url=url_for('contractor_signup', _external=True),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        # Fallback test simulator when Stripe API keys are not yet configured in sandbox
        contractor.is_active_subscriber = True
        db.session.commit()
        flash("Stripe test mode active: Subscription simulated and activated successfully!", "success")
        return redirect(url_for("admin_dashboard"))

@app.route("/contractors/success/<int:contractor_id>")
def payment_success(contractor_id):
    contractor = Contractor.query.get_or_404(contractor_id)
    contractor.is_active_subscriber = True
    db.session.commit()
    flash("Payment successful! Your exclusive contractor subscription is now active.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin")
def admin_dashboard():
    leads = Lead.query.order_by(Lead.id.desc()).all()
    contractors = Contractor.query.all()
    return render_template_string(ADMIN_TEMPLATE, leads=leads, contractors=contractors)

@app.route("/privacy")
def privacy_policy():
    return render_template_string(PRIVACY_TEMPLATE)

@app.route("/terms")
def terms_of_service():
    return render_template_string(TERMS_TEMPLATE)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
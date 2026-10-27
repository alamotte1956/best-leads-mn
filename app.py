"""Restoration Contractors MN - replacement Flask application.

Preserves existing Contractor and Lead database columns.
This version does NOT send SMS or assign leads automatically.
"""
import os
import re
import secrets
import logging
from datetime import datetime, timezone

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    render_template_string, request, session, url_for
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "")
if not app.config["SECRET_KEY"]:
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"):
        raise RuntimeError("Set SECRET_KEY in Railway environment variables.")
    app.config["SECRET_KEY"] = "development-only-replace-before-deployment"

db_url = os.environ.get("DATABASE_URL", "sqlite:///contractors.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
db = SQLAlchemy(app)
logging.basicConfig(level=logging.INFO)


class Contractor(db.Model):
    __tablename__ = "contractors"
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    zip_codes = db.Column(db.String(500), nullable=False)
    exclusive_leads = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=False)
    license_number = db.Column(db.String(50))
    service_type = db.Column(db.String(100))
    service_radius_zip = db.Column(db.String(10))
    rating = db.Column(db.Float)
    verified = db.Column(db.Boolean)
    is_test = db.Column(db.Boolean, nullable=False, default=False)


class Lead(db.Model):
    __tablename__ = "leads"
    id = db.Column(db.Integer, primary_key=True)
    homeowner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    zip_code = db.Column(db.String(10), nullable=False)
    service_needed = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default="New")
    description = db.Column(db.Text)


# Existing schema retained. create_all creates missing tables, but DOES NOT
# migrate existing tables. Use migrations for future column changes.
with app.app_context():
    db.create_all()


def clean(value, limit=150):
    return str(value or "").strip()[:limit]


def valid_zip(value):
    return bool(re.fullmatch(r"\d{5}", value))


def valid_email(value):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def valid_phone(value):
    return len(re.sub(r"\D", "", value)) in range(10, 16)


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/signup", methods=["GET", "POST"])
@app.route("/contractors/apply", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        supplied = request.form.get("_csrf", "")
        if not supplied or not secrets.compare_digest(supplied, session.get("_csrf", "")):
            abort(400, "Invalid form token. Refresh and try again.")

        company = clean(request.form.get("company_name"))
        contact = clean(request.form.get("contact_name"))
        email = clean(request.form.get("email"), 120).lower()
        phone = clean(request.form.get("phone"), 20)
        zip_codes = clean(
            request.form.get("zip_codes") or
            request.form.get("service_radius_zip") or
            request.form.get("zip_code"), 500
        )
        zip_list = [z.strip() for z in zip_codes.split(",") if z.strip()]
        if not all([company, contact, valid_email(email), valid_phone(phone)]) or not zip_list or not all(valid_zip(z) for z in zip_list):
            flash("Please enter a valid business name, contact, email, phone and 5-digit ZIP code(s).", "danger")
        else:
            try:
                contractor = Contractor(
                    company_name=company,
                    contact_name=contact,
                    email=email,
                    phone=phone,
                    zip_codes=",".join(zip_list),
                    exclusive_leads=True,
                    active=False,  # MUST be approved after verification
                )
                db.session.add(contractor)
                db.session.commit()
                flash("Application received. Approval is required before leads can be assigned.", "success")
                return redirect(url_for("signup"))
            except IntegrityError:
                db.session.rollback()
                flash("An application already exists for that email address.", "danger")
            except Exception:
                db.session.rollback()
                app.logger.exception("Contractor registration failed")
                flash("We could not save your application. Please try again later.", "danger")
    # Existing ZIP contains contractor_signup.html, not signup.html.
    return render_template("contractor_signup.html")


@app.route("/api/leads", methods=["POST"])
def submit_lead():
    if not request.is_json:
        return jsonify({"status": "error", "message": "JSON body required"}), 415
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    name = clean(data.get("homeowner_name"), 100)
    phone = clean(data.get("phone"), 20)
    email = clean(data.get("email"), 120).lower()
    zip_code = clean(data.get("zip_code"), 10)
    service = clean(data.get("service_needed"), 100)

    if not name or not valid_phone(phone) or not valid_zip(zip_code) or not service:
        return jsonify({"status": "error", "message": "Valid name, phone, ZIP and service are required"}), 400
    if email and not valid_email(email):
        return jsonify({"status": "error", "message": "Invalid email address"}), 400

    try:
        lead = Lead(
            homeowner_name=name, phone=phone, email=email or None,
            zip_code=zip_code, service_needed=service, status="New"
        )
        db.session.add(lead)
        db.session.commit()
        # No automatic assignment yet. Do not report "matched" when no
        # exclusive assignment has actually been created.
        return jsonify({
            "status": "success",
            "message": "Request received. Contractor matching is pending.",
            "lead_id": lead.id,
            "assignment_status": "pending"
        }), 201
    except Exception:
        db.session.rollback()
        app.logger.exception("Lead creation failed")
        return jsonify({"status": "error", "message": "Unable to save request"}), 500


LEGAL_STYLE = """
<style>
body{font-family:Arial,sans-serif;max-width:850px;margin:45px auto;padding:0 20px;
color:#243342;line-height:1.65}a{color:#1768a0}h1,h2{line-height:1.2}
.notice{padding:12px;background:#fff5dc;border-left:4px solid #d49c2b}
</style>
"""
LEGAL_HEADER = '<p><a href="/">Home</a> | <a href="/privacy">Privacy</a> | <a href="/terms">Terms</a></p>'


@app.route("/privacy")
def privacy():
    return render_template_string(
        LEGAL_STYLE + LEGAL_HEADER + """
        <h1>Privacy Policy</h1>
        <p class="notice"><strong>Draft for review:</strong> Confirm the contact address,
        retention practices, third-party providers and consent disclosures before
        treating this as a final legal policy.</p>
        <p>Restoration Contractors MN collects information you provide when requesting
        contractor matching or applying as a contractor, such as name, phone number,
        email address, ZIP code, project details and business information.</p>
        <h2>How information is used</h2>
        <p>We use submitted information to respond to requests, evaluate contractor
        applications, operate our service, prevent abuse and maintain records.</p>
        <h2>Sharing</h2>
        <p>Information may be shared with a selected participating contractor for
        the purpose of responding to your request, and with service providers that
        support hosting, communications and operations. We do not claim to sell
        your request to multiple contractors.</p>
        <h2>Text messaging</h2>
        <p>SMS notifications will be offered only where the required consent and
        messaging arrangements are in place. Consent to marketing messages is not
        required to request contractor matching. Mobile opt-in information is not
        shared with third parties for their own marketing.</p>
        <h2>Security and requests</h2>
        <p>We use administrative and technical safeguards, but no system is
        completely secure. To request access, correction or deletion, use the
        contact information published on our website.</p>
        <p><em>Last updated: October 27, 2026.</em></p>
        """
    )


@app.route("/terms")
def terms():
    return render_template_string(
        LEGAL_STYLE + LEGAL_HEADER + """
        <h1>Terms of Service</h1>
        <p class="notice"><strong>Draft for review:</strong> Have these terms checked
        against your actual operations and applicable law before launch.</p>
        <h2>Our service</h2>
        <p>Restoration Contractors MN operates a contractor-matching service.
        We do not perform restoration or construction work ourselves through
        this website. Availability of a match is not guaranteed.</p>
        <h2>Independent contractors</h2>
        <p>Participating contractors are independent businesses. Consumers should
        independently review licenses, insurance, qualifications, estimates,
        agreements and warranties before hiring.</p>
        <h2>Requests</h2>
        <p>By submitting a request, you authorize us to use the supplied details
        to process your request and share relevant information with a selected
        contractor for that purpose, subject to the Privacy Policy.</p>
        <h2>No emergency dispatch guarantee</h2>
        <p>The website is not an emergency response service and does not guarantee
        a particular response time. For an immediate threat to life or safety,
        contact emergency services.</p>
        <h2>Communications</h2>
        <p>Where SMS is offered, message frequency may vary, message and data rates
        may apply, and users can reply STOP to opt out or HELP for assistance.</p>
        <p><em>Last updated: October 27, 2026.</em></p>
        """
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

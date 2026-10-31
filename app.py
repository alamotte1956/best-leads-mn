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
from contractor_login_attempt_model import define_contractor_login_attempt
ContractorLoginAttempt = define_contractor_login_attempt(db)

from lead_offer_model import define_lead_offer
LeadOffer = define_lead_offer(db)
from contractor_password_token_model import define_contractor_password_setup_token
ContractorPasswordSetupToken = define_contractor_password_setup_token(db)

from admin_login_attempt import define_admin_login_attempt
AdminLoginAttempt = define_admin_login_attempt(db)

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
    sms_consent = db.Column(db.Boolean, nullable=False, default=False)
    sms_consent_at = db.Column(db.DateTime(timezone=True))
    sms_consent_method = db.Column(db.String(50))
    password_hash = db.Column(db.String(512), nullable=True)
    sms_opted_out_at = db.Column(db.DateTime(timezone=True))


class ContractorService(db.Model):
    """Additional services offered by a registered contractor."""
    __tablename__ = "contractor_services"

    id = db.Column(db.Integer, primary_key=True)
    contractor_id = db.Column(
        db.Integer,
        db.ForeignKey("contractors.id"),
        nullable=False,
        index=True
    )
    service_name = db.Column(db.String(100), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "contractor_id",
            "service_name",
            name="uq_contractor_service"
        ),
    )


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
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True, default=lambda: datetime.now(timezone.utc))


# Existing schema retained. create_all creates missing tables, but DOES NOT
# migrate existing tables. Use migrations for future column changes.


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


class SmsSuppression(db.Model):
    """Phone numbers that must not receive automated SMS."""
    __tablename__ = "sms_suppressions"

    id = db.Column(db.Integer, primary_key=True)
    phone_normalized = db.Column(
        db.String(10),
        unique=True,
        nullable=False,
        index=True
    )
    opted_out_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False
    )
    source = db.Column(
        db.String(50),
        nullable=False,
        default="twilio_stop"
    )


class SmsNotification(db.Model):
    """Durable record of a planned contractor SMS notification."""

    __tablename__ = "sms_notifications"

    id = db.Column(db.Integer, primary_key=True)

    notification_key = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    lead_id = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )

    contractor_id = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="pending",
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    twilio_message_sid = db.Column(
        db.String(100),
        nullable=True,
    )

with app.app_context():
    db.create_all()



@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    from admin_auth import (
        admin_auth_configured,
        verify_admin_password,
    )

    if not admin_auth_configured():
        return ("Administrator login is not configured.", 503)

    if request.method == "POST":
        from admin_login_db_guard import (
            is_locked,
            record_failure,
            clear_failures,
        )

        # Use Flask's direct remote address, not an untrusted
        # X-Forwarded-For header.
        identifier = request.remote_addr or "unknown"

        from admin_login_lock import lock_identifier

        try:
            if db.session.get_bind().dialect.name == "postgresql":
                lock_identifier(db, identifier)
        except Exception:
            db.session.rollback()
            raise

        if is_locked(db, AdminLoginAttempt, identifier):
            db.session.rollback()
            return render_template(
                "admin_login.html",
                error="Too many attempts. Try again in 15 minutes.",
            ), 429

        supplied = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")

        if not supplied or not secrets.compare_digest(
            supplied, expected
        ):
            db.session.rollback()
            abort(400)

        password = request.form.get("password", "")

        if verify_admin_password(password):
            clear_failures(db, AdminLoginAttempt, identifier)
            db.session.commit()
            session.clear()
            from admin_session_security import (
                current_password_fingerprint,
            )

            session["admin_authenticated"] = True
            session["admin_login_at"] = datetime.now(
                timezone.utc
            ).timestamp()
            session["admin_password_fingerprint"] = (
                current_password_fingerprint()
            )
            session.permanent = True
            return redirect(url_for("admin_dashboard"))

        record_failure(db, AdminLoginAttempt, identifier)
        db.session.commit()

        return render_template(
            "admin_login.html",
            error="Incorrect administrator password.",
        ), 401

    return render_template(
        "admin_login.html",
        error=None,
    )



@app.route('/admin/contractors/<int:contractor_id>/status', methods=['POST'])
def admin_contractor_status(contractor_id):
    if session.get('admin_authenticated') is not True:
        return redirect(url_for('admin_login'))

    from admin_session_security import session_password_valid
    from admin_auth import admin_auth_configured

    login_at = session.get('admin_login_at')
    now = datetime.now(timezone.utc).timestamp()

    if (
        not session_password_valid(session.get('admin_password_fingerprint'))
        or not isinstance(login_at, (int, float))
        or now < login_at
        or now - login_at > 3600
        or not admin_auth_configured()
    ):
        session.clear()
        return redirect(url_for('admin_login'))

    supplied = request.form.get('_csrf', '')
    expected = session.get('_csrf', '')

    if not supplied or not secrets.compare_digest(supplied, expected):
        abort(400)

    action = request.form.get('action', '')

    if action not in ('approve', 'deactivate'):
        abort(400)

    contractor = db.session.get(Contractor, contractor_id)

    if contractor is None:
        abort(404)

    try:
        if action == 'approve':
            contractor.active = True
            contractor.verified = True
        else:
            contractor.active = False

        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('Contractor status update failed')
        abort(500)

    if action == 'approve':
        flash('Contractor approved and marked verified.', 'success')
    else:
        flash('Contractor deactivated.', 'success')

    return redirect(url_for('admin_dashboard'))


@app.route("/admin")
def admin_dashboard():
    if session.get("admin_authenticated") is not True:
        return redirect(url_for("admin_login"))

    from admin_session_security import session_password_valid

    if not session_password_valid(
        session.get("admin_password_fingerprint")
    ):
        session.clear()
        return redirect(url_for("admin_login"))

    login_at = session.get("admin_login_at")
    if not isinstance(login_at, (int, float)):
        session.clear()
        return redirect(url_for("admin_login"))

    elapsed = datetime.now(timezone.utc).timestamp() - login_at
    if elapsed < 0 or elapsed > 3600:
        session.clear()
        return redirect(url_for("admin_login"))

    from admin_auth import admin_auth_configured

    if not admin_auth_configured():
        session.clear()
        return ("Administrator login is not configured.", 503)

    leads = Lead.query.order_by(
        Lead.id.desc()
    ).limit(200).all()

    verified_contractor_count = Contractor.query.filter_by(
        active=True,
        verified=True
    ).count()

    contractors = Contractor.query.order_by(
        Contractor.id.desc()
    ).limit(200).all()

    return render_template(
        "admin.html",
        verified_contractor_count=verified_contractor_count,
        leads=leads,
        contractors=contractors,
    )


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    supplied = request.form.get("_csrf", "")
    expected = session.get("_csrf", "")

    if not supplied or not secrets.compare_digest(
        supplied, expected
    ):
        abort(400)

    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/signup", methods=["GET", "POST"])
@app.route("/contractors/apply", methods=["GET", "POST"])
@app.route("/contractor-signup", methods=["GET", "POST"])
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
        license_number = clean(request.form.get("license_number"), 50)
        service_type = clean(request.form.get("service_type"), 100)
        additional_services = list(dict.fromkeys(
            clean(value, 100)
            for value in request.form.getlist("additional_services")
            if clean(value, 100)
        ))
        if not all([company, contact, valid_email(email), valid_phone(phone), license_number, service_type]) or not zip_list or not all(valid_zip(z) for z in zip_list):
            flash("Please enter a valid business name, contact, email, phone and 5-digit ZIP code(s).", "danger")
        else:
            try:
                consent_requested = request.form.get("sms_consent") == "yes"
                normalized_phone = normalize_sms_phone(phone)

                suppression = None
                if normalized_phone:
                    suppression = SmsSuppression.query.filter_by(
                        phone_normalized=normalized_phone
                    ).first()

                consent_given = (
                    consent_requested
                    and normalized_phone is not None
                    and suppression is None
                )

                contractor = Contractor(
                    company_name=company,
                    contact_name=contact,
                    email=email,
                    phone=phone,
                    zip_codes=",".join(zip_list),
                    license_number=clean(
                        request.form.get("license_number"), 50
                    ),
                    service_type=clean(
                        request.form.get("service_type"), 100
                    ),
                    service_radius_zip=zip_list[0],
                    exclusive_leads=True,
                    active=False,
                    verified=False,  # MUST be approved after verification
                    is_test=False,
                    sms_consent=consent_given,
                    sms_consent_at=datetime.now(timezone.utc) if consent_given else None,
                    sms_consent_method="contractor_signup_form_v1" if consent_given else None,
                    sms_opted_out_at=None,
                )
                db.session.add(contractor)
                db.session.flush()

                selected_services = list(dict.fromkeys(
                    [service_type] + additional_services
                ))

                for service_name in selected_services:
                    db.session.add(
                        ContractorService(
                            contractor_id=contractor.id,
                            service_name=service_name
                        )
                    )

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


@app.route("/request-received")
def homeowner_request_received():
    return render_template("request_received.html")


@app.route("/api/leads", methods=["POST"])
def submit_lead():
    is_json_submission = request.is_json

    if is_json_submission:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    elif request.mimetype in (
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ):
        data = request.form
    else:
        return jsonify({
            "status": "error",
            "message": "Unsupported submission format"
        }), 415

    name = clean(data.get("homeowner_name") or data.get("name"), 100)
    phone = clean(data.get("phone"), 20)
    email = clean(data.get("email"), 120).lower()
    zip_code = clean(data.get("zip_code"), 10)
    service = clean(data.get("service_needed"), 100)
    description = clean(data.get("description"), 5000)

    if not name or not valid_phone(phone) or not valid_zip(zip_code) or not service:
        return jsonify({"status": "error", "message": "Valid name, phone, ZIP and service are required"}), 400
    if email and not valid_email(email):
        return jsonify({"status": "error", "message": "Invalid email address"}), 400

    try:
        lead = Lead(
            homeowner_name=name, phone=phone, email=email or None,
            zip_code=zip_code, service_needed=service,
            description=description or None, status="New"
        )
        db.session.add(lead)
        db.session.commit()
        # No automatic assignment yet. Do not report "matched" when no
        # exclusive assignment has actually been created.
        if not is_json_submission:
            return redirect(url_for("homeowner_request_received"))

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



def normalize_sms_phone(value):
    """Normalize US phone numbers to ten digits."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def contractor_sms_eligible(contractor):
    """Return True only when automated SMS is permitted."""
    if contractor is None:
        return False

    if not (
        contractor.active is True
        and contractor.verified is True
        and contractor.is_test is False
        and contractor.sms_consent is True
        and contractor.sms_consent_at is not None
        and bool(contractor.sms_consent_method)
        and contractor.sms_opted_out_at is None
    ):
        return False

    normalized = normalize_sms_phone(contractor.phone)

    if normalized is None:
        return False

    suppressed = SmsSuppression.query.filter_by(
        phone_normalized=normalized
    ).first()

    return suppressed is None


@app.route("/webhooks/twilio/sms", methods=["POST"])
def twilio_sms_webhook():
    from sms_optout import is_stop_request, revoke_sms_consent
    from twilio_security import validate_twilio_request

    # Use the configured public URL, not an untrusted Host header.
    public_url = (
        "https://www.restorationcontractorsmn.com"
        "/webhooks/twilio/sms"
    )

    signature = request.headers.get("X-Twilio-Signature", "")

    if not validate_twilio_request(
        public_url,
        request.form,
        signature
    ):
        abort(403)

    message = request.form.get("Body", "")

    if not is_stop_request(message):
        return ("", 204)

    sender = normalize_sms_phone(request.form.get("From"))

    if sender is None:
        return ("", 204)

    try:
        received_at = datetime.now(timezone.utc)

        # Atomic insert prevents duplicate STOP records when
        # multiple webhook requests arrive simultaneously.
        if db.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif db.engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            raise RuntimeError("Unsupported SMS suppression database")

        statement = insert(SmsSuppression).values(
            phone_normalized=sender,
            opted_out_at=received_at,
            source="twilio_stop"
        ).on_conflict_do_nothing(
            index_elements=["phone_normalized"]
        )

        db.session.execute(statement)

        contractors = Contractor.query.all()

        for contractor in contractors:
            if normalize_sms_phone(contractor.phone) == sender:
                revoke_sms_consent(contractor, received_at)

        db.session.commit()

        return ("", 204)

    except Exception:
        db.session.rollback()
        app.logger.exception("SMS opt-out processing failed")
        return ("", 500)


LEGAL_STYLE = """
<style>
body{font-family:Arial,sans-serif;max-width:850px;margin:45px auto;padding:0 20px;
color:#243342;line-height:1.65}a{color:#1768a0}h1,h2{line-height:1.2}
.notice{padding:14px;background:#ffffff;border:1px solid #dce5ee;border-left:4px solid #1768a0;border-radius:8px;box-shadow:0 3px 12px rgba(16,37,62,.05)}
</style>
"""
LEGAL_HEADER = "{% include 'partials/brand_header.html' %}\n" + '<p><a href="/">Home</a> | <a href="/privacy">Privacy</a> | <a href="/terms">Terms</a> | <a href="/sms-policy">SMS Policy</a></p>'



@app.route("/sms-policy")
def sms_policy():
    return render_template("legal/sms_policy.html")

@app.route("/privacy")
def privacy():
    return render_template_string(
        LEGAL_STYLE + '\n<style>\nbody { max-width:none; margin:0; padding:0; }\nbody > p, body > h1, body > h2, body > ul, body > ol {\n  box-sizing:border-box; max-width:890px; margin-left:auto; margin-right:auto; padding-left:20px; padding-right:20px;\n}\n</style>\n' + LEGAL_HEADER + """
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

        <h2>Contractor SMS / Text Messaging</h2>
        <p>Contractors who provide a mobile number and affirmatively
        select the optional SMS consent checkbox at
        <a href="/contractor-signup">our contractor registration page</a>
        may receive operational text messages about lead matching,
        dispatch, scheduling, service alerts and project updates.
        This program does not send promotional or marketing texts.
        Homeowner communications are handled by email.</p>
        <p>SMS enrollment is voluntary and is not required to register,
        purchase services or do business with us. Message frequency
        varies. Message and data rates may apply. Reply STOP to opt out
        or HELP for assistance. We also honor opt-out requests received
        through any reasonable method.</p>
        <p>Mobile opt-in information and SMS consent records are never
        sold or shared with third parties, affiliates or lead generators
        for their marketing or promotional purposes. We may share mobile
        numbers with service providers solely to operate our messaging
        program, subject to appropriate confidentiality protections.</p>
        <p>For assistance, call 612-701-7064 or write to Restoration
        Contractors MN, 10805 173rd St W. #127, Lakeville, MN 55044.
        See our <a href="/sms-policy">SMS Terms &amp; Conditions</a>.</p>
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
        LEGAL_STYLE + '\n<style>\nbody { max-width:none; margin:0; padding:0; }\nbody > p, body > h1, body > h2, body > ul, body > ol {\n  box-sizing:border-box; max-width:890px; margin-left:auto; margin-right:auto; padding-left:20px; padding-right:20px;\n}\n</style>\n' + LEGAL_HEADER + """
        <h1>Terms of Service</h1>
        <p class="notice"><strong>Draft for review:</strong> Have these terms checked
        against your actual operations and applicable law before launch.</p>
        <h2>Our service</h2>
        <p>Restoration Contractors MN operates a contractor-matching service.
        We do not perform restoration or construction work ourselves through
        this website. Availability of a match is not guaranteed.</p>

        <h2>Contractor Lead Notifications</h2>
        <p>Eligible contractors may receive lead opportunities based on
        service category, geographic coverage and account status.
        Registration does not guarantee any particular lead or revenue.
        When a lead offer has a displayed acceptance deadline, it may
        expire if not accepted in time. The planned sequential matching
        process uses a 15-minute acceptance window.</p>
        <p>Contractors may voluntarily enroll in operational SMS
        notifications through an unchecked-by-default consent checkbox.
        SMS consent is not required to register or use our services.
        Reply STOP to opt out or HELP for assistance. See our
        <a href="/sms-policy">SMS Terms &amp; Conditions</a>.</p>
        <p>Any contractor lead fees or payment obligations must be
        disclosed in the applicable contractor agreement or accepted
        pricing terms. Receiving an SMS alone does not authorize
        an undisclosed charge.</p>
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


# BEGIN RCMN RESTORATION LANDING PAGES
from restoration_landing_legacy import restoration_landing_pages
app.register_blueprint(restoration_landing_pages)

# END RCMN RESTORATION LANDING PAGES



# Contractor authentication routes
@app.route("/contractor/login", methods=["GET", "POST"])
def contractor_login():
    import os
    import secrets
    from contractor_authentication import authenticate_contractor
    from contractor_session_security import create_contractor_session_data

    if request.method == "GET":
        return render_template("contractor_login.html")

    supplied = request.form.get("_csrf", "")
    expected = session.get("_csrf", "")

    if not supplied or not expected or not secrets.compare_digest(
        supplied, expected
    ):
        abort(400)

    email = request.form.get("email", "")
    password = request.form.get("password", "")

    lock_secret = os.environ.get("CONTRACTOR_LOGIN_LOCK_SECRET")

    if not lock_secret or len(lock_secret) < 32:
        app.logger.error("Contractor login secret is not configured")
        abort(503)

    try:
        contractor = authenticate_contractor(
            db.session,
            Contractor,
            email,
            password,
            lock_secret,
        )

        contractor_id = contractor.id if contractor is not None else None

        # Commit failed attempts as well as successful resets.
        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Contractor authentication failed")
        abort(503)

    if contractor_id is None:
        flash("Invalid credentials or account unavailable.", "error")
        return redirect(url_for("contractor_login"))

    # Preserve administrator session information if present.
    session.pop("contractor_id", None)
    session.pop("contractor_login_at", None)

    session.update(create_contractor_session_data(contractor_id))

    return redirect(url_for("contractor_dashboard"))


@app.route("/contractor/logout", methods=["POST"])
def contractor_logout():
    import secrets

    supplied = request.form.get("_csrf", "")
    expected = session.get("_csrf", "")

    if not supplied or not expected or not secrets.compare_digest(
        supplied, expected
    ):
        abort(400)

    session.pop("contractor_id", None)
    session.pop("contractor_login_at", None)

    return redirect(url_for("contractor_login"))


@app.route("/contractor/dashboard", methods=["GET"])
def contractor_dashboard():
    from datetime import datetime, timezone
    from contractor_session_security import contractor_session_valid

    contractor_id = session.get("contractor_id")

    if not isinstance(contractor_id, int) or isinstance(contractor_id, bool):
        return redirect(url_for("contractor_login"))

    contractor = db.session.get(Contractor, contractor_id)

    if not contractor_session_valid(dict(session), contractor):
        session.pop("contractor_id", None)
        session.pop("contractor_login_at", None)
        return redirect(url_for("contractor_login"))

    rows = (
        db.session.query(LeadOffer, Lead)
        .join(Lead, Lead.id == LeadOffer.lead_id)
        .filter(LeadOffer.contractor_id == contractor_id)
        .order_by(LeadOffer.offered_at.desc())
        .limit(100)
        .all()
    )

    offers = []

    for offer, lead in rows:
        offers.append({
            "id": offer.id,
            "lead_id": offer.lead_id,
            "service_needed": lead.service_needed,
            "zip_code": lead.zip_code,
            "status": offer.status,
            "expires_at": offer.expires_at,
        })

    return render_template(
        "contractor_offers.html",
        offers=offers,
        server_now=datetime.now(timezone.utc),
    )



@app.route("/contractor/offers/<int:offer_id>/accept", methods=["POST"])
def contractor_accept_offer(offer_id):
    import secrets

    from contractor_session_security import contractor_session_valid
    from contractor_offer_transactions import accept_contractor_offer

    contractor_id = session.get("contractor_id")

    if (
        not isinstance(contractor_id, int)
        or isinstance(contractor_id, bool)
    ):
        return redirect(url_for("contractor_login"))

    contractor = db.session.get(Contractor, contractor_id)

    if not contractor_session_valid(dict(session), contractor):
        session.pop("contractor_id", None)
        session.pop("contractor_login_at", None)
        return redirect(url_for("contractor_login"))

    supplied = request.form.get("_csrf", "")
    expected = session.get("_csrf", "")

    if (
        not supplied
        or not expected
        or not secrets.compare_digest(supplied, expected)
    ):
        abort(400)

    try:
        result = accept_contractor_offer(
            db.session,
            offer_id,
            contractor_id,
        )

        if result is None:
            db.session.rollback()
            flash(
                "Offer unavailable, expired, or already accepted.",
                "error",
            )
            return redirect(url_for("contractor_dashboard"))

        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Contractor offer acceptance failed")
        abort(503)

    flash("Lead offer accepted successfully.", "success")
    return redirect(url_for("contractor_dashboard"))



@app.route("/contractor/offers/<int:offer_id>/decline", methods=["POST"])
def contractor_decline_offer(offer_id):
    import secrets

    from contractor_session_security import contractor_session_valid
    from contractor_offer_decline import decline_contractor_offer

    contractor_id = session.get("contractor_id")

    if (
        not isinstance(contractor_id, int)
        or isinstance(contractor_id, bool)
    ):
        return redirect(url_for("contractor_login"))

    contractor = db.session.get(Contractor, contractor_id)

    if not contractor_session_valid(dict(session), contractor):
        session.pop("contractor_id", None)
        session.pop("contractor_login_at", None)
        return redirect(url_for("contractor_login"))

    supplied = request.form.get("_csrf", "")
    expected = session.get("_csrf", "")

    if (
        not supplied
        or not expected
        or not secrets.compare_digest(supplied, expected)
    ):
        abort(400)

    try:
        result = decline_contractor_offer(
            db.session,
            offer_id,
            contractor_id,
        )

        if result is None:
            db.session.rollback()
            flash(
                "Offer unavailable, expired, or already handled.",
                "error",
            )
            return redirect(url_for("contractor_dashboard"))

        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception("Contractor offer decline failed")
        abort(503)

    flash("Lead offer declined successfully.", "success")
    return redirect(url_for("contractor_dashboard"))




@app.route("/admin/owner-command-center", methods=["GET"])
def owner_command_center():
    from datetime import datetime, timezone
    from owner_command_center_data import load_owner_dashboard_data

    if not session.get("admin_authenticated"):
        return redirect(url_for("admin_login"))

    login_at = session.get("admin_login_at")

    if isinstance(login_at, bool) or not isinstance(login_at, (int, float)):
        return redirect(url_for("admin_login"))

    elapsed = datetime.now(timezone.utc).timestamp() - login_at

    if not (0 <= elapsed <= 3600):
        return redirect(url_for("admin_login"))

    data = load_owner_dashboard_data(
        db,
        Lead,
        Contractor,
        LeadOffer,
    )

    return render_template(
        "owner_command_center.html",
        **data,
    )

# RESTORATION_SERVICE_LANDING_ROUTES_V1
from restoration_landing_pages import LANDING_PAGES

LANDING_PHOTOS = {
    "water-damage": "photo-1581578731548-c64695cc6952",
    "storm-hail-damage": "photo-1500673922987-e212871fec22",
    "roof-repair": "photo-1635424710928-0544e8512eae",
    "basement-flooding": "photo-1523413651479-597eb2da0ad6",
    "mold-remediation": "photo-1584622650111-993a426fbf0a",
    "fire-smoke-damage": "photo-1487958449943-2429e8be8625",
    "sewer-backup": "photo-1504307651254-35680f356dfd",
    "frozen-pipes": "photo-1457269449834-928af64c684d",
    "siding-repair": "photo-1600596542815-ffad4c1539a9",
    "emergency-tarping": "photo-1500530855697-b586d89ba3ee",
}

@app.route("/services/<slug>", methods=["GET"])
def restoration_service_page(slug):
    page = LANDING_PAGES.get(slug)

    if page is None:
        abort(404)

    photo_id = LANDING_PHOTOS[slug]
    photo = (
        "https://images.unsplash.com/"
        + photo_id
        + "?auto=format&fit=crop&w=1600&q=85"
    )

    return render_template(
        "restoration_service.html",
        slug=slug,
        page=page,
        photo=photo,
        all_pages=LANDING_PAGES,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

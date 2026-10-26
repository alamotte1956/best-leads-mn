import os
from datetime import datetime, timedelta
import sqlite3
from flask import Flask, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")
DB_PATH = os.environ.get("DATABASE_URL", "leads.db").replace("sqlite:///", "")

STYLE = """
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }
  .container { max-width: 900px; margin: 40px auto; padding: 0 20px; }
  .card { background: white; border-radius: 12px; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,.1); margin-bottom: 20px; }
  h1, h2 { margin-top: 0; }
  .badge { display: inline-block; background: #0ea5e9; color: white; padding: 6px 12px; border-radius: 20px; font-size: 14px; margin-bottom: 16px; }
  .red { color: #dc2626; font-weight: 600; }
  .nav a { margin-right: 16px; color: #0ea5e9; text-decoration: none; }
  label { display: block; margin: 14px 0 6px; font-weight: 500; }
  input, select, textarea { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
  button, .btn { background: #0ea5e9; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-size: 16px; }
  .services { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin: 10px 0 20px; }
  .services label { font-weight: normal; display: flex; align-items: center; gap: 8px; }
  .services input { width: auto; }
  footer { text-align: center; padding: 30px; color: #64748b; font-size: 14px; }
  .note { font-size: 14px; color: #64748b; }
</style>
"""

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS contractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            contact TEXT,
            phone TEXT,
            email TEXT,
            services TEXT,
            service_area TEXT,
            exclusive_only TEXT,
            created_at TEXT,
            active INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT,
            zip TEXT,
            details TEXT,
            price REAL,
            status TEXT DEFAULT 'available',
            created_at TEXT,
            expires_at TEXT,
            sold_to INTEGER
        );
        """)

init_db()

def is_expired(lead):
    if not lead["expires_at"]:
        return False
    try:
        return datetime.fromisoformat(lead["expires_at"]) < datetime.utcnow()
    except Exception:
        return False

@app.route("/")
def home():
    logged_in = "contractor_email" in session
    auth_nav = (
        '<a href="/available_leads">Available Leads</a> <a href="/contractor_logout">Logout</a>'
        if logged_in
        else '<a href="/available_leads">Available Leads</a> <a href="/signup">Sign Up</a> <a href="/contractor_login">Login</a>'
    )
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <div class="badge">EXCLUSIVE LEADS ONLY · NO SHARED LEADS</div>
        <h1>Best Leads</h1>
        <p>Premium exclusive Twin Cities contractor leads. One contractor per job. Contact information remains hidden until you accept.</p>
        <p class="red">Leads expire after 24 hours if not accepted.</p>
        <div class="nav">
          {auth_nav}
          <a href="/contractors">Manage Contractors</a>
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
        </div>
      </div>
    </div>
    <footer>Albert R LaMotte dba Restoration Contractors MN · Exclusive matching · Minnesota law applies</footer>
    """)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        d = request.form.to_dict()
        services = request.form.get("services_joined") or request.form.get("services") or ""
        d["services"] = services
        d["service_area"] = request.form.get("service_area", "")
        d["exclusive_only"] = request.form.get("exclusive_only", "No")
        d["created_at"] = datetime.utcnow().isoformat()
        with get_db() as db:
            db.execute("""
                INSERT INTO contractors (company, contact, phone, email, services, service_area, exclusive_only, created_at)
                VALUES (:company, :contact, :phone, :email, :services, :service_area, :exclusive_only, :created_at)
            """, d)
        return render_template_string(f"""{STYLE}<div class="container"><div class="card"><h2>Application Received</h2><p>Thank you. We will review and activate your account for exclusive leads.</p><a href="/" class="btn">Return Home</a></div></div>""")

    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <h2>Contractor Sign Up</h2>
        <p>Apply for exclusive Twin Cities leads. No shared leads.</p>
        <form method="post" onsubmit="return joinServices(this)">
          <label>Company Name *</label>
          <input name="company" required>
          <label>Contact Person *</label>
          <input name="contact" required>
          <label>Phone *</label>
          <input name="phone" required>
          <label>Email *</label>
          <input name="email" type="email" required>
          <label>Services Offered * (check all that apply)</label>
          <div class="services">
            <label><input type="checkbox" name="services" value="water damage"> Water Damage</label>
            <label><input type="checkbox" name="services" value="dry out"> Dry Out</label>
            <label><input type="checkbox" name="services" value="mold mitigation"> Mold Mitigation</label>
            <label><input type="checkbox" name="services" value="mold inspection"> Mold Inspection</label>
            <label><input type="checkbox" name="services" value="mold remediation"> Mold Remediation</label>
            <label><input type="checkbox" name="services" value="indoor air quality"> Indoor Air Quality</label>
            <label><input type="checkbox" name="services" value="roofing"> Roofing</label>
            <label><input type="checkbox" name="services" value="siding"> Siding</label>
            <label><input type="checkbox" name="services" value="windows"> Windows</label>
            <label><input type="checkbox" name="services" value="gutters"> Gutters</label>
            <label><input type="checkbox" name="services" value="remodeling"> Remodeling</label>
            <label><input type="checkbox" name="services" value="kitchen"> Kitchen</label>
            <label><input type="checkbox" name="services" value="bathroom"> Bathroom</label>
            <label><input type="checkbox" name="services" value="addition"> Addition</label>
            <label><input type="checkbox" name="services" value="flooring"> Flooring</label>
            <label><input type="checkbox" name="services" value="painting"> Painting</label>
            <label><input type="checkbox" name="services" value="hvac"> HVAC</label>
            <label><input type="checkbox" name="services" value="plumbing"> Plumbing</label>
            <label><input type="checkbox" name="services" value="electrical"> Electrical</label>
            <label><input type="checkbox" name="services" value="landscaping"> Landscaping</label>
            <label><input type="checkbox" name="services" value="decks"> Decks</label>
            <label><input type="checkbox" name="services" value="fencing"> Fencing</label>
            <label><input type="checkbox" name="services" value="other"> Other</label>
          </div>
          <input type="hidden" name="services_joined" id="services_joined">
          <label>Primary Service Area *</label>
          <input name="service_area" required placeholder="e.g. Twin Cities, Edina, Minnetonka, or full metro">
          <label style="font-weight:500;"><input type="checkbox" name="exclusive_only" value="Yes" style="width:auto; margin-right:8px;"> I only want exclusive (non-shared) leads</label>
          <button type="submit">Apply Now</button>
          <p class="note">By submitting you agree to receive exclusive leads and confirm the information is accurate. Minnesota law applies.</p>
        </form>
      </div>
    </div>
    <script>
      function joinServices(form) {{
        const checked = Array.from(form.querySelectorAll('input[name="services"]:checked')).map(cb => cb.value);
        document.getElementById('services_joined').value = checked.join(', ');
        if (checked.length === 0) {{
          alert('Please select at least one service.');
          return false;
        }}
        return true;
      }}
    </script>
    """)

@app.route("/available_leads")
def available_leads():
    if "contractor_email" not in session:
        return redirect(url_for("contractor_login"))
    with get_db() as db:
        rows = db.execute("SELECT * FROM leads WHERE status='available' ORDER BY created_at DESC").fetchall()
    cards = ""
    if not rows:
        cards = '<div class="card"><p>No exclusive leads available right now.</p></div>'
    else:
        for r in rows:
            expired = is_expired(r)
            price = r["price"] or 0
            cards += f'''
            <div class="card">
              <strong>{r["service"]}</strong> · ZIP {r["zip"]}<br>
              <span class="red">{"EXPIRED" if expired else "Available"}</span> · ${price}<br>
              <form method="post" action="/accept_lead">
                <input type="hidden" name="lead_id" value="{r["id"]}">
                <button type="submit" {"disabled" if expired else ""}>Accept Lead</button>
              </form>
            </div>'''
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <h2>Available Exclusive Leads</h2>
        <p>Contact info is completely hidden until you accept the lead.</p>
        <p class="red">Leads expire after 24 hours if not accepted.</p>
        <p><a href="/">← Home</a></p>
      </div>
      {cards}
    </div>
    """)

@app.route("/accept_lead", methods=["POST"])
def accept_lead():
    if "contractor_email" not in session:
        return redirect(url_for("contractor_login"))
    lead_id = request.form.get("lead_id")
    contractor_id = session.get("contractor_id")
    if lead_id and contractor_id:
        with get_db() as db:
            db.execute("UPDATE leads SET status='accepted', sold_to=? WHERE id=? AND status='available'", (contractor_id, lead_id))
    return redirect(url_for("available_leads"))

@app.route("/contractors")
def contractors():
    with get_db() as db:
        rows = db.execute("SELECT * FROM contractors ORDER BY created_at DESC").fetchall()
    cards = ""
    for r in rows:
        status = "Active" if r["active"] else "Inactive"
        cls = "" if r["active"] else "inactive"
        cards += f'''
        <div class="card {cls}">
          <strong>{r["company"]}</strong> — {r["contact"]}<br>
          {r["phone"]} · {r["email"]}<br>
          Services: {r["services"] or "—"}<br>
          Service Area: {r["service_area"] or "—"}<br>
          Status: {status}
          <form method="post" action="/toggle_contractor" style="margin-top:10px;">
            <input type="hidden" name="id" value="{r["id"]}">
            <button type="submit">{"Deactivate" if r["active"] else "Activate"}</button>
          </form>
        </div>'''
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <h2>Contractor Management</h2>
        <p>Activate or deactivate contractors for exclusive lead matching.</p>
        <p><a href="/">← Home</a></p>
      </div>
      {cards or '<div class="card"><p>No contractors yet.</p></div>'}
    </div>
    """)

@app.route("/toggle_contractor", methods=["POST"])
def toggle_contractor():
    cid = request.form.get("id")
    if cid:
        with get_db() as db:
            db.execute("UPDATE contractors SET active = 1 - active WHERE id = ?", (cid,))
    return redirect(url_for("contractors"))

@app.route("/contractor_login", methods=["GET", "POST"])
def contractor_login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        with get_db() as db:
            contractor = db.execute("SELECT * FROM contractors WHERE email = ?", (email,)).fetchone()
            if contractor:
                session["contractor_email"] = contractor["email"]
                session["contractor_id"] = contractor["id"]
                return redirect(url_for("available_leads"))
            else:
                error = "Email not found. Please sign up first."
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <h2>Contractor Login</h2>
        {"<p class='red'>" + error + "</p>" if error else ""}
        <form method="post">
          <label>Email</label><input name="email" type="email" required>
          <label>Password</label><input name="password" type="password">
          <button type="submit">Login</button>
        </form>
        <p><a href="/">← Home</a></p>
      </div>
    </div>
    """)

@app.route("/contractor_logout")
def contractor_logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/privacy")
def privacy():
    return render_template_string(f"""{STYLE}<div class="container"><div class="card">
  <h1>Privacy Policy</h1>
  <p><strong>Effective Date:</strong> October 26, 2026</p>
  <p>Albert R LaMotte dba Restoration Contractors MN (“we,” “us,” or “our”) operates the websites restorationcontractorsmn.com and contractors.restorationcontractorsmn.com and the exclusive lead-matching service. This Privacy Policy explains how we collect, use, and share information. It is governed by Minnesota law.</p>

  <h2>1. Information We Collect</h2>
  <p><strong>From homeowners:</strong> Name, phone number, email address, ZIP code, service requested, project details, and any other information submitted on the consumer form.</p>
  <p><strong>From contractors:</strong> Company name, contact name, phone number, email address, services offered, service area, and any other information submitted during signup.</p>
  <p><strong>Automatically collected:</strong> IP address, browser type, device information, and pages visited through standard server logs.</p>
  <p><strong>Communications:</strong> Records of emails or text messages related to lead matching or account management.</p>

  <h2>2. How We Use Information</h2>
  <ul>
    <li>To match homeowners with one exclusive contractor.</li>
    <li>To notify contractors of available exclusive leads and to notify homeowners when a contractor accepts their lead.</li>
    <li>To manage contractor accounts and process lead acceptance.</li>
    <li>To send transactional emails and SMS messages related to lead matching.</li>
    <li>To improve the sites, prevent fraud, and comply with Minnesota law.</li>
  </ul>

  <h2>3. SMS and Email Communications</h2>
  <p>By providing your phone number and checking the consent box (or submitting the form), you expressly consent to receive text messages and emails from us related to exclusive lead matching. Message and data rates may apply. Reply STOP to any SMS to opt out. You may unsubscribe from emails using the link in the message or by contacting us. Consent is not a condition of using the matching service.</p>

  <h2>4. Sharing of Information</h2>
  <p>Homeowner contact information is shared <strong>only</strong> with the single contractor who accepts the exclusive lead. Contractor contact information is shared with the homeowner only after the contractor accepts the lead. We do not sell, rent, or share the same lead with multiple contractors. We may share information with service providers (hosting, email, SMS) solely to operate the service, and as required by law.</p>

  <h2>5. Data Retention</h2>
  <p>We retain information as long as needed to provide the service, resolve disputes, and comply with legal obligations under Minnesota law.</p>

  <h2>6. Your Rights</h2>
  <p>Minnesota residents may request access to, correction of, or deletion of their personal information by contacting us. We will respond in accordance with applicable Minnesota law.</p>

  <h2>7. Contact</h2>
  <p>Albert R LaMotte dba Restoration Contractors MN<br>
  Email: info@restorationcontractorsmn.com</p>

  <h2>8. Changes</h2>
  <p>We may update this Privacy Policy. The updated version will be posted on the sites with a new effective date.</p>

  <p><a href="/">← Home</a></p>
</div></div>
""")

@app.route("/terms")
def terms():
    return render_template_string(f"""{STYLE}<div class="container"><div class="card">
  <h1>Terms & Conditions</h1>
  <p><strong>Effective Date:</strong> October 26, 2026</p>
  <p>These Terms & Conditions (“Terms”) govern your use of the websites restorationcontractorsmn.com and contractors.restorationcontractorsmn.com and the exclusive lead-matching service operated by Albert R LaMotte dba Restoration Contractors MN (“we,” “us,” or “our”).</p>

  <h2>1. Exclusive Leads Only</h2>
  <p>All leads provided through this service are exclusive. A lead is offered to only one contractor at a time. We do not sell or share the same lead with multiple contractors. Contact information remains hidden until the contractor accepts the lead.</p>

  <h2>2. Homeowner Terms</h2>
  <p>By submitting a lead form, you authorize us to share your contact information and project details with one contractor who accepts the exclusive lead. You agree that the contractor is an independent business, not our employee or agent. You acknowledge that the Minnesota Home Solicitation Sales Act (Minn. Stat. §§ 325G.06–325G.11) and other applicable Minnesota consumer protection laws may apply to any in-home solicitation or contract with the contractor. You may cancel certain home solicitation contracts within the time periods required by Minnesota law.</p>

  <h2>3. Contractor Terms</h2>
  <p>Contractors must provide accurate information. Acceptance of a lead constitutes an agreement to contact the homeowner promptly. Contractors may accept or reject a lead. Unaccepted leads expire after 24 hours. Contractors are independent businesses. We do not guarantee the quality, outcome, or legality of any work performed.</p>

  <h2>4. Minnesota Law</h2>
  <p>These Terms and all agreements related to the service are governed by the laws of the State of Minnesota, without regard to conflict-of-law principles. Any disputes shall be resolved in the state or federal courts located in Minnesota. The Minnesota Home Solicitation Sales Act and other applicable Minnesota statutes apply where relevant.</p>

  <h2>5. No Shared Leads</h2>
  <p>We expressly do not operate a shared-lead model. Each lead is exclusive to one contractor.</p>

  <h2>6. Limitation of Liability</h2>
  <p>To the fullest extent permitted by Minnesota law, we are not liable for the acts, omissions, quality of work, or contractual disputes between homeowners and contractors. Our role is limited to exclusive lead matching.</p>

  <h2>7. SMS and Email Consent</h2>
  <p>By providing a phone number and submitting a form, you consent to receive transactional SMS and email messages related to lead matching. You may opt out of SMS by replying STOP.</p>

  <h2>8. Changes</h2>
  <p>We may update these Terms. Continued use of the sites after changes constitutes acceptance of the updated Terms.</p>

  <h2>9. Contact</h2>
  <p>Albert R LaMotte dba Restoration Contractors MN<br>
  Email: info@restorationcontractorsmn.com</p>

  <p><a href="/">← Home</a></p>
</div></div>
""")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

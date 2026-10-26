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
  .container { max-width: 1000px; margin: 40px auto; padding: 0 20px; }
  .card { background: white; border-radius: 12px; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,.1); margin-bottom: 20px; }
  h1, h2 { margin-top: 0; }
  .badge { display: inline-block; background: #0ea5e9; color: white; padding: 6px 12px; border-radius: 20px; font-size: 14px; margin-bottom: 16px; }
  .red { color: #dc2626; font-weight: 600; }
  .nav a { margin-right: 16px; color: #0ea5e9; text-decoration: none; }
  label { display: block; margin: 14px 0 6px; font-weight: 500; }
  input, select, textarea { width: 100%; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
  button, .btn { background: #0ea5e9; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-size: 16px; text-decoration: none; display: inline-block; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }
  th { background: #f1f5f9; }
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
            name TEXT,
            phone TEXT,
            email TEXT,
            details TEXT,
            price REAL,
            status TEXT DEFAULT 'available',
            created_at TEXT,
            expires_at TEXT,
            sold_to INTEGER
        );
        """)

init_db()

@app.route("/")
def home():
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <div class="badge">EXCLUSIVE LEADS ONLY · NO SHARED LEADS</div>
        <h1>Best Leads</h1>
        <p>Premium exclusive Twin Cities contractor leads. One contractor per job.</p>
        <p class="red">Leads expire after 24 hours if not accepted.</p>
        <div class="nav">
          <a href="/signup">Contractor Signup</a>
          <a href="/contractor_login">Login</a>
          <a href="/available">Available Leads</a>
          <a href="/admin">Admin</a>
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
        </div>
      </div>
    </div>
    """)

@app.route("/admin")
def admin():
    with get_db() as db:
        leads = db.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
        contractors = db.execute("SELECT * FROM contractors ORDER BY id DESC").fetchall()
        sold = db.execute("SELECT COUNT(*) as c, COALESCE(SUM(price),0) as rev FROM leads WHERE status='sold'").fetchone()
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <h1>Admin — Best Leads</h1>
        <p>Sales Summary: <strong>{sold['c']}</strong> leads sold · <strong>${sold['rev']:.0f}</strong> revenue</p>
        <div class="nav">
          <a href="/">Home</a>
          <a href="/available">Available Leads</a>
        </div>
      </div>
      <div class="card">
        <h2>All Leads</h2>
        <table>
          <tr><th>ID</th><th>Service</th><th>ZIP</th><th>Contact</th><th>Price</th><th>Status</th></tr>
          {''.join(f"<tr><td>{l['id']}</td><td>{l['service']}</td><td>{l['zip']}</td><td>{l['name'] or ''}<br>{l['phone'] or ''}</td><td>${l['price'] or 0}</td><td>{l['status']}</td></tr>" for l in leads) or '<tr><td colspan="6">No leads yet.</td></tr>'}
        </table>
      </div>
      <div class="card">
        <h2>Contractors</h2>
        <table>
          <tr><th>ID</th><th>Company</th><th>Contact</th><th>Phone</th><th>Active</th></tr>
          {''.join(f"<tr><td>{c['id']}</td><td>{c['company']}</td><td>{c['contact']}</td><td>{c['phone']}</td><td>{'Yes' if c['active'] else 'No'}</td></tr>" for c in contractors) or '<tr><td colspan="5">No contractors yet.</td></tr>'}
        </table>
      </div>
    </div>
    """)

@app.route("/privacy")
def privacy():
    return render_template_string(STYLE + """
    <div class="container"><div class="card">
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
      <p>Albert R LaMotte dba Restoration Contractors MN<br>Email: info@restorationcontractorsmn.com</p>
      <h2>8. Changes</h2>
      <p>We may update this Privacy Policy. The updated version will be posted on the sites with a new effective date.</p>
      <p><a href="/">← Home</a></p>
    </div></div>
    """)

@app.route("/terms")
def terms():
    return render_template_string(STYLE + """
    <div class="container"><div class="card">
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
      <p>Albert R LaMotte dba Restoration Contractors MN<br>Email: info@restorationcontractorsmn.com</p>
      <p><a href="/">← Home</a></p>
    </div></div>
    """)

@app.route("/signup")
def signup():
    return render_template_string(f"""
    {STYLE}
    <div class="container"><div class="card">
      <h1>Contractor Signup</h1>
      <p>Join to receive exclusive Twin Cities restoration leads.</p>
      <form method="post" action="/signup">
        <label>Company Name</label><input name="company" required>
        <label>Contact Name</label><input name="contact" required>
        <label>Phone</label><input name="phone" required>
        <label>Email</label><input name="email" type="email" required>
        <label>Services</label><textarea name="services" required></textarea>
        <button type="submit">Apply</button>
      </form>
      <p class="note"><a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></p>
    </div></div>
    """)

@app.route("/signup", methods=["POST"])
def signup_post():
    data = request.form
    with get_db() as db:
        db.execute("""
            INSERT INTO contractors (company, contact, phone, email, services, created_at, active)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (data.get("company"), data.get("contact"), data.get("phone"), data.get("email"), data.get("services"), datetime.utcnow().isoformat()))
        db.commit()
    return redirect("/signup?success=1")

@app.route("/available")
def available():
    return render_template_string(f"""
    {STYLE}
    <div class="container"><div class="card">
      <h1>Available Exclusive Leads</h1>
      <p class="red">Leads expire after 24 hours if not accepted.</p>
      <p>Contact information is hidden until you accept the lead.</p>
      <a href="/" class="btn">Back</a>
    </div></div>
    """)

@app.route("/contractor_login")
def contractor_login():
    return render_template_string(f"""
    {STYLE}
    <div class="container"><div class="card">
      <h1>Contractor Login</h1>
      <form method="post">
        <label>Email</label><input name="email" type="email" required>
        <label>Password</label><input name="password" type="password" required>
        <button type="submit">Login</button>
      </form>
    </div></div>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

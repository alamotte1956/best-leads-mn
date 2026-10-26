from datetime import datetime, timedelta
import os
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
  .inactive { opacity: 0.7; background: #f1f5f9; }
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
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <div class="badge">EXCLUSIVE LEADS ONLY · NO SHARED LEADS</div>
        <h1>Best Leads</h1>
        <p>Premium exclusive Twin Cities contractor leads. One contractor per job. Contact information remains hidden until you accept.</p>
        <p class="red">Leads expire after 24 hours if not accepted.</p>
        <div class="nav">
          <a href="/available_leads">Available Leads</a>
          <a href="/signup">Sign Up</a>
          <a href="/contractor_login">Login</a>
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
    lead_id = request.form.get("lead_id")
    if lead_id:
        with get_db() as db:
            db.execute("UPDATE leads SET status='accepted' WHERE id=? AND status='available'", (lead_id,))
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
          Exclusive Only: {r["exclusive_only"] or "No"}<br>
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
    if request.method == "POST":
        session["contractor_email"] = request.form.get("email")
        return redirect(url_for("home"))
    return render_template_string(f"""
    {STYLE}
    <div class="container">
      <div class="card">
        <h2>Contractor Login</h2>
        <form method="post">
          <label>Email</label><input name="email" type="email" required>
          <label>Password</label><input name="password" type="password">
          <button type="submit">Login</button>
        </form>
        <p><a href="/">← Home</a></p>
      </div>
    </div>
    """)

@app.route("/privacy")
def privacy():
    return render_template_string(f"""{STYLE}<div class="container"><div class="card"><h1>Privacy Policy</h1><p>Contractor information is used solely for account management and exclusive lead matching. Contact details are not shared with homeowners until a lead is accepted. No shared leads. Operated by Albert R LaMotte dba Restoration Contractors MN.</p><a href="/">← Home</a></div></div>""")

@app.route("/terms")
def terms():
    return render_template_string(f"""{STYLE}<div class="container"><div class="card"><h1>Terms</h1><p>Exclusive lead service operated by Albert R LaMotte dba Restoration Contractors MN. Contractors are charged only upon acceptance of a lead. All agreements are governed by Minnesota law, including the Home Solicitation Sales Act. No shared leads.</p><a href="/">← Home</a></div></div>""")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
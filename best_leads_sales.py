"""
Best Leads — Lead Sales Database
Separate server for selling exclusive restoration leads to contractors.
SQLite database tracks contractors, available leads, and sales.
"""
from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta
import os
import stripe

app = Flask(__name__)
app.secret_key = "best-leads-sales-2026"
DB = "best_leads.db"
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

def expire_old_assignments():
    """Return assigned leads to available if not paid within 2 hours."""
    cutoff = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    with get_db() as db:
        db.execute(
            "UPDATE leads SET status='available', sold_to=NULL, sold_at=NULL WHERE status='assigned' AND sold_at < ?",
            (cutoff,)
        )

def find_best_contractor(service_type, zip_code):
    """Auto-match: approved contractor whose services include the lead type and service area covers the ZIP."""
    with get_db() as db:
        contractors = db.execute(
            "SELECT * FROM contractors WHERE status='approved' AND active=1"
        ).fetchall()
    service = (service_type or "").lower().replace("_", " ")
    matches = []
    for c in contractors:
        services = (c["services_offered"] or "").lower()
        area = (c["service_area"] or "").lower()
        if service and service in services:
            if zip_code and (zip_code in area or "full" in area or "twin" in area):
                matches.append((c, 2))
            else:
                matches.append((c, 1))
    if not matches:
        return None
    matches.sort(key=lambda x: -x[1])
    return matches[0][0]

def calculate_auto_price(service_type, urgency, score):
    """Return competitive price: 20% below typical Angi shared-lead rates."""
    base = {
        "water_damage": 75, "dry_out": 65, "mold_mitigation": 55, "mold_inspection": 45,
        "mold_remediation": 70, "iaq_testing": 40, "iaq": 40, "remodeling": 60,
        "kitchen": 70, "bathroom": 65, "addition": 80, "roofing": 85, "siding": 70,
        "windows": 60, "painting": 45, "flooring": 50, "hvac": 55, "plumbing": 50,
        "electrical": 50, "landscaping": 40, "other": 50,
    }
    price = base.get((service_type or "").lower(), 55)
    if urgency == "emergency":
        price = int(price * 1.35)
    elif urgency == "asap":
        price = int(price * 1.15)
    if (score or 0) >= 80:
        price = int(price * 1.2)
    elif (score or 0) >= 60:
        price = int(price * 1.05)
    return max(25, int(price * 0.80))

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS contractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            service_area TEXT,
            license_number TEXT,
            insurance TEXT,
            insurance_expires TEXT,
            years_in_business TEXT,
            services_offered TEXT,
            avg_job_size TEXT,
            preferred_contact TEXT,
            website TEXT,
            google_profile TEXT,
            contractor_refs TEXT,
            exclusive_only TEXT,
            active INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            license_verified INTEGER DEFAULT 0,
            insurance_verified INTEGER DEFAULT 0,
            background_checked INTEGER DEFAULT 0,
            created TEXT
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contractor_id INTEGER,
            lead_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created TEXT
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_type TEXT,
            urgency TEXT,
            zip TEXT,
            name TEXT,
            phone TEXT,
            email TEXT,
            score INTEGER,
            priority_level TEXT,
            price INTEGER,
            status TEXT DEFAULT 'available',
            created TEXT,
            sold_to INTEGER,
            sold_at TEXT,
            FOREIGN KEY(sold_to) REFERENCES contractors(id)
        );
        """)
        cols = [r[1] for r in db.execute("PRAGMA table_info(contractors)").fetchall()]
        for col in ["license_number", "insurance", "insurance_expires", "years_in_business",
                    "services_offered", "avg_job_size", "preferred_contact", "website",
                    "google_profile", "contractor_refs", "exclusive_only", "status",
                    "license_verified", "insurance_verified", "background_checked"]:
            if col not in cols:
                db.execute(f"ALTER TABLE contractors ADD COLUMN {col} TEXT")

init_db()

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Best Leads — Sales Database</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 30px auto; padding: 16px; background: #f8fafc; color: #1e293b; }
  h1 { margin: 0 0 8px; }
  .sub { color: #64748b; margin-bottom: 24px; }
  table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 0.92rem; }
  th { background: #0f172a; color: white; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.75rem; background: #e0f2fe; color: #0369a1; }
  .sold { background: #dcfce7; color: #166534; }
  .avail { background: #fef9c3; color: #854d0e; }
  a { color: #0ea5e9; text-decoration: none; }
  .card { background: white; padding: 16px; border-radius: 10px; margin-bottom: 20px; }
  form input, form select { padding: 8px; margin: 4px 8px 4px 0; border: 1px solid #cbd5e1; border-radius: 6px; }
  button { background: #0ea5e9; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; }
</style>
</head>
<body>
  <h1>Best Leads</h1>
  <p class="sub">Lead sales database — contractors & exclusive restoration leads · <strong>No shared leads.</strong> One contractor per job. · <a href="/available">Available Leads</a> · <a href="/hub">Hub</a></p>
  {{ content|safe }}
</body>
</html>
"""

@app.route("/")
@app.route("/admin")
def home():
    try:
        expire_old_assignments()
    except Exception:
        pass
    with get_db() as db:
        leads = db.execute("""
            SELECT l.*, c.name as contractor_name
            FROM leads l LEFT JOIN contractors c ON l.sold_to = c.id
            ORDER BY l.id DESC
        """).fetchall()
        contractors = db.execute("SELECT * FROM contractors WHERE status IN ('approved','paused') OR active=1").fetchall()
        pending = db.execute("SELECT * FROM contractors WHERE active=0 OR status='pending'").fetchall()

    contractor_html = "".join(
        "<li><strong><a href='/contractor/{}'>{}</a></strong> — {} — Bought: {} — <a href='/toggle_contractor/{}'>{}</a></li>".format(
            c["id"], c["name"], c["phone"] or "",
            db_count(c["id"]),
            c["id"],
            "turn off" if c["active"] else "turn on"
        )
        for c in contractors
    ) or "<li>None approved yet</li>"

    pending_html = "".join(
        "<li><strong>{}</strong> — {} — <a href='/approve_contractor/{}'>approve</a></li>".format(
            c["name"], c["phone"] or "", c["id"]
        )
        for c in pending
    ) or "<li>None pending</li>"

    rows = ""
    for l in leads:
        status_cls = "sold" if l["status"] == "sold" else "avail"
        sold = l["contractor_name"] or "—"
        rows += f"""
        <tr>
          <td>{l['id']}</td>
          <td>{l['service_type'] or ''}<br><small>{l['urgency'] or ''}</small></td>
          <td>{l['zip'] or ''}</td>
          <td>{l['name'] or ''}<br><small>{l['phone'] or ''}</small></td>
          <td>{l['score'] or ''}</td>
          <td>${l['price'] or 0}</td>
          <td><span class="badge {status_cls}">{l['status']}</span></td>
          <td>{sold}</td>
        </tr>"""
    if not rows:
        rows = "<tr><td colspan='8'>No leads yet.</td></tr>"

    content = f"""
    <div class="card">
      <h2>All Leads</h2>
      <table>
        <tr><th>ID</th><th>Service</th><th>ZIP</th><th>Contact</th><th>Score</th><th>Price</th><th>Status</th><th>Sold To</th></tr>
        {rows}
      </table>
    </div>
    <div class="card">
      <h2>Contractors</h2>
      <h3>Pending Approval</h3>
      <ul>{pending_html}</ul>
      <h3>Approved</h3>
      <ul>{contractor_html}</ul>
      <p><a href="/signup">Contractor Signup Form</a></p>
    </div>
    """
    return render_template_string(HTML, content=content)

def db_count(cid):
    with get_db() as db:
        return db.execute("SELECT COUNT(*) FROM leads WHERE sold_to=? AND status='sold'", (cid,)).fetchone()[0]

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        d = request.form
        services = d.get("services_offered", "")
        with get_db() as db:
            db.execute(
                """INSERT INTO contractors
                   (name, phone, email, service_area, license_number, insurance, insurance_expires,
                    years_in_business, services_offered, avg_job_size, preferred_contact,
                    website, google_profile, contractor_refs, exclusive_only, status, active, created)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d.get("name"), d.get("phone"), d.get("email"), d.get("service_area"),
                 d.get("license_number"), d.get("insurance"), d.get("insurance_expires"),
                 d.get("years_in_business"), services, d.get("avg_job_size"),
                 d.get("preferred_contact"), d.get("website"), d.get("google_profile"),
                 d.get("contractor_refs"), d.get("exclusive_only"), "pending", 0,
                 datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
        return "<h2>Thank you!</h2><p>Your application has been received and is pending review.</p><p><a href='/signup'>Back</a></p>"

    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contractor Signup — Restoration Contractors MN</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, sans-serif; background: #f1f5f9; margin: 0; padding: 32px 16px; color: #0f172a; }
    .wrap { max-width: 680px; margin: 0 auto; }
    .card { background: white; padding: 36px; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); }
    h1 { font-size: 1.75rem; margin: 0 0 8px; }
    .sub { color: #64748b; margin-bottom: 28px; }
    label { display: block; margin: 16px 0 6px; font-weight: 600; font-size: 0.95rem; }
    input, select, textarea { width: 100%; padding: 12px 14px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 1rem; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: #0ea5e9; box-shadow: 0 0 0 3px rgba(14,165,233,0.15); }
    .services { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin-top: 8px; }
    .services label { font-weight: 500; margin: 0; display: flex; align-items: center; gap: 8px; }
    .services input { width: auto; margin: 0; }
    button { width: 100%; background: #0ea5e9; color: white; border: none; padding: 16px; border-radius: 10px; font-size: 1.05rem; font-weight: 600; margin-top: 24px; cursor: pointer; }
    button:hover { background: #0284c7; }
    .note { font-size: 0.85rem; color: #64748b; margin-top: 16px; }
    @media (max-width: 540px) { .services { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Contractor Signup</h1>
      <p class="sub">Receive exclusive Twin Cities leads. No shared leads. One contractor per job.</p>
      <form method="post" onsubmit="return joinServices(this)">
        <label>Company / Contractor Name *</label>
        <input name="name" required>
        <label>Phone *</label>
        <input name="phone" type="tel" required placeholder="(612) 555-1234">
        <label>Email *</label>
        <input name="email" type="email" required>
        <label>Minnesota License Number *</label>
        <input name="license_number" required placeholder="BC or CR license">
        <label>Liability Insurance *</label>
        <select name="insurance" required>
          <option value="">Select</option>
          <option value="Yes — Full">Yes — Full coverage</option>
          <option value="Yes — Partial">Yes — Partial</option>
          <option value="No">No</option>
        </select>
        <label>Insurance Expiration</label>
        <input name="insurance_expires" type="date">
        <label>Years in Business *</label>
        <input name="years_in_business" type="number" min="0" required>
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
        <input type="hidden" name="services_offered" id="services_joined">
        <label>Primary Service Area *</label>
        <input name="service_area" required placeholder="e.g. Twin Cities, Edina, Minnetonka, or full metro">
        <label>Average Job Size</label>
        <input name="avg_job_size" placeholder="e.g. $5k–$15k">
        <label>Preferred Contact</label>
        <select name="preferred_contact">
          <option value="phone">Phone</option>
          <option value="text">Text / SMS</option>
          <option value="email">Email</option>
        </select>
        <label>Website</label>
        <input name="website" placeholder="https://">
        <label>Google Business Profile</label>
        <input name="google_profile" placeholder="Link or short description">
        <label>References / Notes</label>
        <textarea name="contractor_refs" rows="3" placeholder="Optional"></textarea>
        <label style="font-weight:500;"><input type="checkbox" name="exclusive_only" value="Yes" style="width:auto; margin-right:8px;"> I only want exclusive (non-shared) leads</label>
        <button type="submit">Apply Now</button>
        <p class="note">By submitting you agree to receive exclusive leads and confirm the information is accurate. Minnesota law applies.</p>
      </form>
    </div>
  </div>
  <script>
    function joinServices(form) {
      const checked = Array.from(form.querySelectorAll('input[name="services"]:checked')).map(cb => cb.value);
      document.getElementById('services_joined').value = checked.join(', ');
      if (checked.length === 0) {
        alert('Please select at least one service.');
        return false;
      }
      return true;
    }
  </script>
</body>
</html>
"""

@app.route("/approve_contractor/<int:cid>")
def approve_contractor(cid):
    with get_db() as db:
        db.execute("UPDATE contractors SET active=1, status='approved' WHERE id=?", (cid,))
    return redirect(url_for("home"))

@app.route("/toggle_contractor/<int:cid>")
def toggle_contractor(cid):
    with get_db() as db:
        row = db.execute("SELECT active FROM contractors WHERE id=?", (cid,)).fetchone()
        if row:
            new_active = 0 if row["active"] else 1
            new_status = "approved" if new_active else "paused"
            db.execute("UPDATE contractors SET active=?, status=? WHERE id=?", (new_active, new_status, cid))
    return redirect(url_for("home"))

@app.route("/hub")
def hub():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Restoration Contractors MN — System Hub</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #f8fafc; margin: 0; padding: 40px 16px; }
    .wrap { max-width: 720px; margin: 0 auto; }
    .section { background: white; border-radius: 12px; padding: 22px; margin-bottom: 18px; }
    a { display: block; padding: 12px; text-decoration: none; color: #0f172a; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Restoration Contractors MN</h1>
    <div class="section">
      <h2>Homeowners</h2>
      <a href="https://www.restorationcontractorsmn.com/">Submit a Request</a>
    </div>
    <div class="section">
      <h2>Contractors</h2>
      <a href="https://contractors.restorationcontractorsmn.com/signup">Sign Up as a Contractor</a>
      <a href="https://contractors.restorationcontractorsmn.com/available">Available Exclusive Leads</a>
    </div>
    <div class="section">
      <h2>Admin</h2>
      <a href="https://contractors.restorationcontractorsmn.com/admin">Admin Dashboard</a>
    </div>
  </div>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)

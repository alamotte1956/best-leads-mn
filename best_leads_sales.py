from flask import Flask, request, session, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")
DB_PATH = "sales.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
                active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                email TEXT,
                zip TEXT,
                service_type TEXT,
                details TEXT,
                price REAL DEFAULT 0,
                status TEXT DEFAULT 'available',
                assigned_to INTEGER,
                created_at TEXT
            );
        """)

init_db()

@app.route("/")
def home():
    return """
    <div style="font-family:system-ui;max-width:800px;margin:40px auto;padding:20px">
      <h1>Best Leads</h1>
      <p>Exclusive Twin Cities Leads — One Contractor Per Job</p>
      <p><strong>No shared leads.</strong> Contact information is hidden until you accept the lead.</p>
      <p>Leads expire after 24 hours if not accepted.</p>
      <p>
        <a href="/available_leads">View Available Leads</a> ·
        <a href="/signup">Contractor Sign Up</a> ·
        <a href="/contractor_login">Contractor Login</a>
      </p>
    </div>
    """

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        d = request.form.to_dict()
        d["created_at"] = datetime.utcnow().isoformat()
        with get_db() as db:
            db.execute("""
                INSERT INTO contractors (company, contact, phone, email, services, created_at)
                VALUES (:company, :contact, :phone, :email, :services, :created_at)
            """, d)
        return "<h2>Application received. We will review and activate your account.</h2><a href='/'>Home</a>"
    return """
    <div style="font-family:system-ui;max-width:600px;margin:40px auto;padding:20px">
      <h2>Contractor Sign Up</h2>
      <form method="post">
        <label>Company</label><br><input name="company" required style="width:100%;padding:8px;margin:8px 0"><br>
        <label>Contact Name</label><br><input name="contact" required style="width:100%;padding:8px;margin:8px 0"><br>
        <label>Phone</label><br><input name="phone" required style="width:100%;padding:8px;margin:8px 0"><br>
        <label>Email</label><br><input name="email" type="email" required style="width:100%;padding:8px;margin:8px 0"><br>
        <label>Services</label><br><input name="services" required style="width:100%;padding:8px;margin:8px 0"><br>
        <p>By submitting you agree to the terms. Exclusive leads only. No shared leads.</p>
        <button type="submit" style="padding:12px 24px;background:#0ea5e9;color:#fff;border:none;border-radius:6px">Submit Application</button>
      </form>
    </div>
    """

@app.route("/available_leads")
def available_leads():
    with get_db() as db:
        rows = db.execute("SELECT * FROM leads WHERE status='available' ORDER BY created_at DESC").fetchall()
    html = """
    <div style="font-family:system-ui;max-width:800px;margin:40px auto;padding:20px">
      <h2>Available Exclusive Leads</h2>
      <p>Contact info hidden until accepted. Leads expire after 24 hours of not being accepted.</p>
      <p style="color:#dc2626"><strong>Red note: Leads expire after 24 hours if not accepted.</strong></p>
    """
    if not rows:
        return html + "<p>No leads available right now.</p></div>"
    for r in rows:
        price = r["price"] or 0
        html += f"""
        <div style="border:1px solid #e2e8f0;padding:16px;margin:16px 0;border-radius:8px;background:#fff">
          <strong>{r['service_type']}</strong> in {r['zip']}<br>
          Price: ${price:.0f}<br>
          <em>Contact hidden until you accept.</em><br>
          <small>Created: {r['created_at']}</small>
        </div>
        """
    return html + "</div>"

@app.route("/contractor_login", methods=["GET", "POST"])
def contractor_login():
    if request.method == "POST":
        session["contractor_email"] = request.form.get("email")
        return redirect(url_for("home"))
    return """
    <div style="font-family:system-ui;max-width:400px;margin:60px auto;padding:20px">
      <h2>Contractor Login</h2>
      <form method="post">
        <label>Email</label><br><input name="email" type="email" required style="width:100%;padding:8px;margin:8px 0"><br>
        <label>Password</label><br><input name="password" type="password" style="width:100%;padding:8px;margin:8px 0"><br>
        <button type="submit" style="padding:12px 24px;background:#0ea5e9;color:#fff;border:none;border-radius:6px">Login</button>
      </form>
      <p><a href="/">Home</a></p>
    </div>
    """

@app.route("/privacy")
def privacy():
    return "<div style='max-width:720px;margin:40px auto;padding:20px;font-family:system-ui'><h1>Privacy Policy</h1><p>Contractor data is used for account management and lead matching only. No shared leads.</p><a href='/'>Home</a></div>"

@app.route("/terms")
def terms():
    return "<div style='max-width:720px;margin:40px auto;padding:20px;font-family:system-ui'><h1>Terms</h1><p>Exclusive lead service. You are charged only when you accept a lead. Governed by Minnesota law. Albert R LaMotte dba Restoration Contractors MN.</p><a href='/'>Home</a></div>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

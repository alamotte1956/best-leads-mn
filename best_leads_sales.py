from flask import Flask, request, session, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
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
    <h1>Best Leads</h1>
    <p>Exclusive Twin Cities Leads — One Contractor Per Job</p>
    <p><strong>No shared leads.</strong> Contact information is hidden until you accept the lead.</p>
    <p>Leads expire after 24 hours if not accepted.</p>
    <a href="/available_leads">View Available Leads</a> |
    <a href="/signup">Contractor Sign Up</a> |
    <a href="/contractor_login">Contractor Login</a>
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
    <h2>Contractor Sign Up</h2>
    <form method="post">
      <label>Company</label><input name="company" required><br>
      <label>Contact Name</label><input name="contact" required><br>
      <label>Phone</label><input name="phone" required><br>
      <label>Email</label><input name="email" type="email" required><br>
      <label>Services (e.g. water damage, roofing)</label><input name="services" required><br>
      <p>By submitting you agree to the terms of Restoration Contractors MN. Exclusive leads only. No shared leads.</p>
      <button type="submit">Submit Application</button>
    </form>
    """

@app.route("/available_leads")
def available_leads():
    with get_db() as db:
        rows = db.execute("SELECT * FROM leads WHERE status='available' ORDER BY created_at DESC").fetchall()
    html = "<h2>Available Exclusive Leads</h2><p>Contact info hidden until accepted. Leads expire after 24 hours of not being accepted.</p>"
    if not rows:
        return html + "<p>No leads available right now.</p>"
    for r in rows:
        price = r["price"] or 0
        html += f"""
        <div style="border:1px solid #ccc;padding:12px;margin:12px 0;border-radius:8px">
          <strong>{r['service_type']}</strong> in {r['zip']}<br>
          Price: ${price:.0f}<br>
          <em>Contact hidden until you accept.</em><br>
          <small>Created: {r['created_at']}</small>
        </div>
        """
    return html

@app.route("/contractor_login", methods=["GET", "POST"])
def contractor_login():
    if request.method == "POST":
        email = request.form.get("email")
        session["contractor_email"] = email
        return redirect(url_for("home"))
    return """
    <h2>Contractor Login</h2>
    <form method="post">
      <label>Email</label><input name="email" type="email" required><br>
      <label>Password</label><input name="password" type="password"><br>
      <button type="submit">Login</button>
    </form>
    <p><a href="/">Home</a></p>
    """

@app.route("/privacy")
def privacy():
    return "<h1>Privacy Policy</h1><p>Contractor data is used for account management and lead matching only. No shared leads.</p><a href='/'>Home</a>"

@app.route("/terms")
def terms():
    return "<h1>Terms</h1><p>Exclusive lead service. You are charged only when you accept a lead. Governed by Minnesota law.</p><a href='/'>Home</a>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

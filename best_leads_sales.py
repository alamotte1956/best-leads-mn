from flask import Flask, request, session, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
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
                company TEXT, contact TEXT, phone TEXT, email TEXT,
                services TEXT, active INTEGER DEFAULT 1, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, phone TEXT, email TEXT, zip TEXT,
                service_type TEXT, details TEXT, price REAL,
                status TEXT DEFAULT 'available', assigned_to INTEGER,
                created_at TEXT
            );
        """)

init_db()

@app.route("/")
def home():
    return """
    <h1>Best Leads</h1>
    <p>Exclusive Twin Cities Leads — One Contractor Per Job</p>
    <p>No shared leads. Contact info hidden until you accept.</p>
    <a href="/available_leads">View Available Leads</a> |
    <a href="/signup">Contractor Sign Up</a> |
    <a href="/contractor_login">Login</a>
    """

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        d = request.form.to_dict()
        d["created_at"] = datetime.utcnow().isoformat()
        with get_db() as db:
            db.execute("""INSERT INTO contractors (company,contact,phone,email,services,created_at)
                          VALUES (:company,:contact,:phone,:email,:services,:created_at)""", d)
        return "<h2>Application received.</h2><a href='/'>Home</a>"
    return """
    <h2>Contractor Sign Up</h2>
    <form method="post">
      Company: <input name="company" required><br>
      Contact: <input name="contact" required><br>
      Phone: <input name="phone" required><br>
      Email: <input name="email" type="email" required><br>
      Services: <input name="services" required><br>
      <button>Submit</button>
    </form>
    """

@app.route("/available_leads")
def available_leads():
    with get_db() as db:
        rows = db.execute("SELECT * FROM leads WHERE status='available'").fetchall()
    html = "<h2>Available Exclusive Leads</h2>"
    for r in rows:
        html += f"<p>{r['service_type']} in {r['zip']} — ${r['price'] or 0}<br>Contact hidden until accepted</p>"
    return html or "No leads yet"

@app.route("/contractor_login", methods=["GET","POST"])
def contractor_login():
    if request.method == "POST":
        email = request.form.get("email")
        session["contractor"] = email
        return redirect(url_for("home"))
    return """
    <h2>Contractor Login</h2>
    <form method="post">
      Email: <input name="email" type="email" required><br>
      Password: <input name="password" type="password"><br>
      <button>Login</button>
    </form>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

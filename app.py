from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from functools import wraps
import sqlite3
import os
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "centex-secret-key")

DB_FILE = "users.db"
DATA_FILE = "site_data.json"


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "site_title": "CentexRantsAndGaming",
            "site_description": "Gaming • Rants • Entertainment",
            "videos": [],
            "merch": []
        }
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "site_title": "CentexRantsAndGaming",
            "site_description": "Gaming • Rants • Entertainment",
            "videos": [],
            "merch": []
        }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def user_count():
    conn = db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


@app.context_processor
def variables():
    return {
        "logged_in": bool(session.get("user_id")),
        "user_email": session.get("user_email"),
        "admin_logged_in": bool(session.get("admin_logged_in"))
    }


@app.route("/")
def home():
    return render_template("index.html", data=load_data())


@app.route("/merch")
def merch():
    return render_template("merch.html", data=load_data())


# =========================
# USER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if "@" not in email:
            error = "Bitte eine gültige E-Mail-Adresse eingeben."
        elif len(password) < 8:
            error = "Das Passwort muss mindestens 8 Zeichen haben."
        elif password != password2:
            error = "Die Passwörter stimmen nicht überein."
        else:
            conn = db()

            existing = conn.execute(
                "SELECT id FROM users WHERE email=?",
                (email,)
            ).fetchone()

            if existing:
                error = "Diese E-Mail ist bereits registriert."
                conn.close()
            else:
                cursor = conn.execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, generate_password_hash(password))
                )

                conn.commit()
                user_id = cursor.lastrowid
                conn.close()

                session["user_id"] = user_id
                session["user_email"] = email

                return redirect(url_for("account"))

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            return redirect(url_for("account"))

        error = "E-Mail oder Passwort ist falsch."

    return render_template("login.html", error=error)


@app.route("/account")
def account():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template("account.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_email", None)
    return redirect(url_for("home"))


# =========================
# ADMIN
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""

    if request.method == "POST":
        password = request.form.get("password", "")
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        if password == admin_password:
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))

        error = "Falsches Admin-Passwort."

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin():
    return render_template(
        "admin.html",
        data=load_data(),
        user_count=user_count()
    )


@app.route("/admin/settings", methods=["POST"])
@admin_required
def settings():
    data = load_data()

    data["site_title"] = request.form.get("site_title", "").strip()
    data["site_description"] = request.form.get("site_description", "").strip()

    save_data(data)
    return redirect(url_for("admin"))


@app.route("/admin/video/add", methods=["POST"])
@admin_required
def video_add():
    data = load_data()

    data["videos"].append({
        "title": request.form.get("title", ""),
        "url": request.form.get("url", ""),
        "description": request.form.get("description", "")
    })

    save_data(data)
    return redirect(url_for("admin"))


@app.route("/admin/video/edit/<int:index>", methods=["POST"])
@admin_required
def video_edit(index):
    data = load_data()

    if 0 <= index < len(data["videos"]):
        data["videos"][index] = {
            "title": request.form.get("title", ""),
            "url": request.form.get("url", ""),
            "description": request.form.get("description", "")
        }

    save_data(data)
    return redirect(url_for("admin"))


@app.route("/admin/video/delete/<int:index>", methods=["POST"])
@admin_required
def video_delete(index):
    data = load_data()

    if 0 <= index < len(data["videos"]):
        data["videos"].pop(index)

    save_data(data)
    return redirect(url_for("admin"))


@app.route("/admin/merch/add", methods=["POST"])
@admin_required
def merch_add():
    data = load_data()

    data["merch"].append({
        "name": request.form.get("name", ""),
        "price": request.form.get("price", ""),
        "description": request.form.get("description", "")
    })

    save_data(data)
    return redirect(url_for("admin"))


@app.route("/admin/merch/edit/<int:index>", methods=["POST"])
@admin_required
def merch_edit(index):
    data = load_data()

    if 0 <= index < len(data["merch"]):
        data["merch"][index] = {
            "name": request.form.get("name", ""),
            "price": request.form.get("price", ""),
            "description": request.form.get("description", "")
        }

    save_data(data)
    return redirect(url_for("admin"))


@app.route("/admin/merch/delete/<int:index>", methods=["POST"])
@admin_required
def merch_delete(index):
    data = load_data()

    if 0 <= index < len(data["merch"]):
        data["merch"].pop(index)

    save_data(data)
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)

import sqlite3
import os
import io
import uuid
import smtplib
import ssl
from email.message import EmailMessage
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, send_file, send_from_directory, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

try:
    import email_config as mail_cfg
except ImportError:
    mail_cfg = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "gorev_takip.db"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "txt", "zip"}

EMAIL_ENABLED = bool(
    mail_cfg
    and getattr(mail_cfg, "SMTP_USER", "")
    and getattr(mail_cfg, "SMTP_PASSWORD", "")
    and mail_cfg.SMTP_USER != "ornek@gmail.com"
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "afad-gorev-takip-degistirin-bu-anahtari")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB üst sınır

STATUSES = ["Bekliyor", "Devam Ediyor", "Tamamlandı", "İptal"]
PRIORITIES = ["Düşük", "Orta", "Yüksek", "Acil"]
STALE_DAYS = 7  # bu kadar gündür güncellenmeyen açık işlemler "durağan" sayılır
MONTHLY_ACTIVITY_TYPES = {
    "Bilgi Sistemleri": ["Bakım/Onarım", "Kurulum", "Destek", "Diğer"],
    "Eğitim": [
        "Okul Farkındalık ve Simülasyon Merkezi Eğitimi",
        "Afet Farkındalık Eğitimleri",
        "Enkazda Arama ve Kurtarma Eğitimi",
        "Yangın Farkındalık Eğitimi",
        "KBRN Eğitimi",
        "Sivil Savunma Eğitimi",
        "TAMP/AYDES Eğitimi",
        "Hizmet İçi Eğitimler",
        "Kamu Kurumları Eğitimleri",
        "Diğer Eğitimler",
    ],
    "AFAD Proje": ["Yapılan Çalışmalar"],
}
MONTHLY_ACTIVITY_STATUSES = ["Tamamlandı", "Devam ediyor", "Rutin", "Planlandı"]

# Panel tablosunda tıklanabilir sıralama için: sütun adı -> SQL ifadesi.
# Öncelik/Durum alfabetik değil, listedeki mantıksal sıraya göre sıralanır.
_PRIORITY_CASE = "CASE tasks.priority " + " ".join(
    f"WHEN '{p}' THEN {i}" for i, p in enumerate(PRIORITIES)
) + " END"
_STATUS_CASE = "CASE tasks.status " + " ".join(
    f"WHEN '{s}' THEN {i}" for i, s in enumerate(STATUSES)
) + " END"
SORT_COLUMNS = {
    "title": "tasks.title",
    "priority": _PRIORITY_CASE,
    "status": _STATUS_CASE,
    "progress": "tasks.progress",
    "due_date": "tasks.due_date",
}


# ---------- Veritabanı ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def send_email(to_addr, subject, body):
    """E-posta gönderir. Ayarlar yapılmamışsa veya adres boşsa sessizce False döner."""
    if not EMAIL_ENABLED or not to_addr:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{mail_cfg.FROM_NAME} <{mail_cfg.SMTP_USER}>"
        msg["To"] = to_addr
        msg.set_content(body)

        use_ssl = getattr(mail_cfg, "SMTP_USE_SSL", False)
        if use_ssl:
            with smtplib.SMTP_SSL(mail_cfg.SMTP_HOST, mail_cfg.SMTP_PORT, timeout=20) as server:
                server.login(mail_cfg.SMTP_USER, mail_cfg.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(mail_cfg.SMTP_HOST, mail_cfg.SMTP_PORT, timeout=20) as server:
                server.starttls()
                server.login(mail_cfg.SMTP_USER, mail_cfg.SMTP_PASSWORD)
                server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError, ssl.SSLError, ValueError) as e:
        app.logger.error(f"E-posta gönderilemedi ({to_addr}): {e}")
        return False


def init_db():
    first_run = not os.path.exists(DB_PATH)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','manager')),
            department TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            department TEXT NOT NULL,
            assigned_to INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Bekliyor',
            priority TEXT NOT NULL DEFAULT 'Orta',
            created_at TEXT NOT NULL,
            due_date TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(assigned_to) REFERENCES users(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS task_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(author_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            uploaded_by INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(uploaded_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY(manager_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS task_personnel (
            task_id INTEGER NOT NULL,
            personnel_id INTEGER NOT NULL,
            PRIMARY KEY (task_id, personnel_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(personnel_id) REFERENCES personnel(id)
        );

        CREATE TABLE IF NOT EXISTS monthly_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            client_id TEXT NOT NULL,
            unit TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            activity_date TEXT NOT NULL,
            status TEXT NOT NULL,
            sessions INTEGER NOT NULL DEFAULT 0,
            participants INTEGER NOT NULL DEFAULT 0,
            institution TEXT NOT NULL DEFAULT '',
            participant_group TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(owner_id, client_id),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS monthly_report_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            unit TEXT NOT NULL,
            ongoing TEXT NOT NULL DEFAULT '',
            issues TEXT NOT NULL DEFAULT '',
            UNIQUE(owner_id, month, unit),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS monthly_report_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            approved_at TEXT,
            UNIQUE(owner_id, month),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS monthly_report_preferences (
            owner_id INTEGER PRIMARY KEY,
            left_logo TEXT NOT NULL DEFAULT '',
            right_logo TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );
        """
    )
    if first_run:
        # Varsayılan admin (Ali - Müdür Yardımcısı) ve örnek şube müdürü
        db.execute(
            "INSERT INTO users (username, password_hash, full_name, role, department) VALUES (?,?,?,?,?)",
            ("admin", generate_password_hash("degistir123", method="pbkdf2:sha256"), "Ali (Müdür Yardımcısı)", "admin", None),
        )
        db.commit()

    # Mevcut kurulumlar için otomatik geçiş: email sütunu yoksa ekle
    existing_cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in existing_cols:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT")
        db.commit()

    # Mevcut kurulumlar için otomatik geçiş: progress sütunu yoksa ekle
    existing_task_cols = [r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()]
    if "progress" not in existing_task_cols:
        db.execute("ALTER TABLE tasks ADD COLUMN progress INTEGER NOT NULL DEFAULT 0")
        db.commit()

    db.close()


# ---------- Yardımcılar ----------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Bu sayfaya erişim yetkiniz yok.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "manager":
            flash("Bu sayfaya erişim yetkiniz yok.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()


def is_overdue(row):
    if row["due_date"] and row["status"] not in ("Tamamlandı", "İptal"):
        try:
            return date.fromisoformat(row["due_date"]) < date.today()
        except ValueError:
            return False
    return False


def is_stale(row):
    if row["status"] not in ("Tamamlandı", "İptal") and row["updated_at"]:
        try:
            updated = datetime.fromisoformat(row["updated_at"])
            return (datetime.now() - updated).days >= STALE_DAYS
        except ValueError:
            return False
    return False


def days_since_update(row):
    try:
        updated = datetime.fromisoformat(row["updated_at"])
        return (datetime.now() - updated).days
    except (ValueError, TypeError):
        return None


app.jinja_env.globals.update(
    is_overdue=is_overdue, is_stale=is_stale, days_since_update=days_since_update,
    STATUSES=STATUSES, PRIORITIES=PRIORITIES, STALE_DAYS=STALE_DAYS,
)


# ---------- Auth ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]
            return redirect(url_for("dashboard"))
        flash("Kullanıcı adı veya şifre hatalı.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Dashboard ----------

@app.route("/")
@login_required
def dashboard():
    db = get_db()
    user = current_user()

    dept_filter = request.args.get("department", "")
    status_filter = request.args.get("status", "")
    user_filter = request.args.get("assigned_to", "")
    q = request.args.get("q", "").strip()

    query = """
        SELECT tasks.*, u.full_name AS assigned_name, u.department AS assigned_dept,
               c.full_name AS creator_name
        FROM tasks
        JOIN users u ON tasks.assigned_to = u.id
        JOIN users c ON tasks.created_by = c.id
        WHERE 1=1
    """
    params = []

    if user["role"] == "manager":
        query += " AND tasks.assigned_to = ?"
        params.append(user["id"])
    else:
        if dept_filter:
            query += " AND tasks.department = ?"
            params.append(dept_filter)
        if user_filter:
            query += " AND tasks.assigned_to = ?"
            params.append(user_filter)

    if status_filter:
        query += " AND tasks.status = ?"
        params.append(status_filter)

    if q:
        query += " AND (tasks.title LIKE ? OR tasks.description LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    sort = request.args.get("sort", "")
    sort_dir = request.args.get("dir", "asc")
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    if sort in SORT_COLUMNS:
        order_expr = SORT_COLUMNS[sort]
        if sort == "due_date":
            query += f" ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, {order_expr} {sort_dir.upper()}"
        else:
            query += f" ORDER BY {order_expr} {sort_dir.upper()}"
    else:
        sort = ""
        query += " ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC, priority DESC"

    tasks = db.execute(query, params).fetchall()

    departments = [r["department"] for r in db.execute(
        "SELECT DISTINCT department FROM users WHERE department IS NOT NULL ORDER BY department"
    ).fetchall()]
    managers = db.execute(
        "SELECT id, full_name, department FROM users WHERE role='manager' AND is_active=1 ORDER BY full_name"
    ).fetchall()

    # Özet sayılar (admin görünümü için genel; manager için kendi işleri)
    if user["role"] == "admin":
        summary_rows = db.execute(
            "SELECT department, status, COUNT(*) as cnt FROM tasks GROUP BY department, status"
        ).fetchall()
        overall_rows = db.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall()
    else:
        summary_rows = db.execute(
            "SELECT department, status, COUNT(*) as cnt FROM tasks WHERE assigned_to=? GROUP BY department, status",
            (user["id"],),
        ).fetchall()
        overall_rows = db.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE assigned_to=? GROUP BY status", (user["id"],)
        ).fetchall()

    summary = {}
    for r in summary_rows:
        summary.setdefault(r["department"], {s: 0 for s in STATUSES})
        summary[r["department"]][r["status"]] = r["cnt"]

    overall_counts = {s: 0 for s in STATUSES}
    for r in overall_rows:
        overall_counts[r["status"]] = r["cnt"]
    overall_total = sum(overall_counts.values())

    overdue_count = sum(1 for t in tasks if is_overdue(t))
    stale_count = sum(1 for t in tasks if is_stale(t) and not is_overdue(t))

    return render_template(
        "dashboard.html",
        tasks=tasks,
        user=user,
        departments=departments,
        managers=managers,
        summary=summary,
        overall_counts=overall_counts,
        overall_total=overall_total,
        overdue_count=overdue_count,
        stale_count=stale_count,
        dept_filter=dept_filter,
        status_filter=status_filter,
        user_filter=user_filter,
        q=q,
        sort=sort,
        sort_dir=sort_dir,
    )


# ---------- Görev (İşlem) CRUD ----------

@app.route("/tasks/new", methods=["GET", "POST"])
@login_required
def new_task():
    db = get_db()
    user = current_user()

    if user["role"] == "admin":
        managers = db.execute(
            "SELECT id, full_name, department FROM users WHERE role='manager' AND is_active=1 ORDER BY full_name"
        ).fetchall()
        personnel_options = []
    else:
        managers = [user]
        personnel_options = db.execute(
            "SELECT * FROM personnel WHERE manager_id=? AND is_active=1 ORDER BY full_name", (user["id"],)
        ).fetchall()

    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form.get("description", "").strip()
        assigned_to = int(request.form["assigned_to"])
        priority = request.form.get("priority", "Orta")
        due_date = request.form.get("due_date") or None
        personnel_ids = [int(pid) for pid in request.form.getlist("personnel_ids")]

        assigned_user = db.execute("SELECT * FROM users WHERE id=?", (assigned_to,)).fetchone()
        now = datetime.now().isoformat(timespec="seconds")

        cursor = db.execute(
            """INSERT INTO tasks
               (title, description, department, assigned_to, created_by, status, priority, created_at, due_date, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (title, description, assigned_user["department"], assigned_to, user["id"],
             "Bekliyor", priority, now, due_date, now),
        )
        new_task_id = cursor.lastrowid
        for pid in personnel_ids:
            db.execute("INSERT INTO task_personnel (task_id, personnel_id) VALUES (?,?)", (new_task_id, pid))
        db.commit()

        if assigned_user["email"]:
            base_url = mail_cfg.BASE_URL if mail_cfg else ""
            body = (
                f"Merhaba {assigned_user['full_name']},\n\n"
                f"Size yeni bir işlem atandı:\n\n"
                f"Başlık: {title}\n"
                f"Öncelik: {priority}\n"
                f"Termin: {due_date or 'Belirtilmemiş'}\n"
                f"Açıklama: {description or '-'}\n\n"
                f"Sisteme giriş yaparak detayları görüp durumunu güncelleyebilirsiniz:\n{base_url}\n\n"
                f"AFAD Görev Takip Sistemi"
            )
            email_ok = send_email(assigned_user["email"], f"[Görev Takip] Yeni işlem: {title}", body)
            if not email_ok:
                flash(
                    f"İşlem oluşturuldu, ancak {assigned_user['full_name']} adlı kullanıcıya "
                    f"e-posta bildirimi gönderilemedi. Bağlantı/ayarları kontrol edin.",
                    "warning",
                )

        flash("İşlem oluşturuldu.", "success")
        return redirect(url_for("dashboard"))

    return render_template("task_form.html", managers=managers, user=user, task=None, personnel_options=personnel_options)


@app.route("/tasks/<int:task_id>", methods=["GET", "POST"])
@login_required
def task_detail(task_id):
    db = get_db()
    user = current_user()
    task = db.execute(
        """SELECT tasks.*, u.full_name AS assigned_name
           FROM tasks
           JOIN users u ON tasks.assigned_to = u.id
           WHERE tasks.id=?""",
        (task_id,),
    ).fetchone()

    if not task:
        flash("İşlem bulunamadı.", "error")
        return redirect(url_for("dashboard"))

    if user["role"] == "manager" and task["assigned_to"] != user["id"]:
        flash("Bu işleme erişim yetkiniz yok.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        new_status = request.form.get("status")
        note = request.form.get("note", "").strip()
        now = datetime.now().isoformat(timespec="seconds")

        try:
            progress = int(request.form.get("progress", task["progress"]))
        except (TypeError, ValueError):
            progress = task["progress"]
        progress = max(0, min(100, progress))

        completed_at = task["completed_at"]
        if new_status == "Tamamlandı" and task["status"] != "Tamamlandı":
            completed_at = now
            progress = 100
        elif new_status != "Tamamlandı":
            completed_at = None

        db.execute(
            "UPDATE tasks SET status=?, progress=?, updated_at=?, completed_at=? WHERE id=?",
            (new_status, progress, now, completed_at, task_id),
        )

        if user["role"] == "manager":
            personnel_ids = [int(pid) for pid in request.form.getlist("personnel_ids")]
            db.execute("DELETE FROM task_personnel WHERE task_id=?", (task_id,))
            for pid in personnel_ids:
                db.execute("INSERT INTO task_personnel (task_id, personnel_id) VALUES (?,?)", (task_id, pid))
        if note:
            db.execute(
                "INSERT INTO task_notes (task_id, author_id, note, created_at) VALUES (?,?,?,?)",
                (task_id, user["id"], note, now),
            )
        db.commit()
        flash("Güncellendi.", "success")
        return redirect(url_for("task_detail", task_id=task_id))

    notes = db.execute(
        """SELECT task_notes.*, u.full_name FROM task_notes
           JOIN users u ON task_notes.author_id = u.id
           WHERE task_id=? ORDER BY created_at DESC""",
        (task_id,),
    ).fetchall()

    attachments = db.execute(
        """SELECT attachments.*, u.full_name FROM attachments
           JOIN users u ON attachments.uploaded_by = u.id
           WHERE task_id=? ORDER BY uploaded_at DESC""",
        (task_id,),
    ).fetchall()

    assigned_personnel = db.execute(
        """SELECT p.* FROM task_personnel tp JOIN personnel p ON tp.personnel_id = p.id
           WHERE tp.task_id=? ORDER BY p.full_name""",
        (task_id,),
    ).fetchall()
    assigned_personnel_ids = {p["id"] for p in assigned_personnel}

    personnel_options = []
    if user["role"] == "manager":
        placeholders = ",".join("?" * len(assigned_personnel_ids)) or "0"
        personnel_options = db.execute(
            f"SELECT * FROM personnel WHERE manager_id=? AND (is_active=1 OR id IN ({placeholders})) ORDER BY full_name",
            (user["id"], *assigned_personnel_ids),
        ).fetchall()

    return render_template(
        "task_detail.html", task=task, notes=notes, attachments=attachments, user=user,
        personnel_options=personnel_options, assigned_personnel=assigned_personnel,
        assigned_personnel_ids=assigned_personnel_ids,
    )


@app.route("/tasks/<int:task_id>/attach", methods=["POST"])
@login_required
def upload_attachment(task_id):
    db = get_db()
    user = current_user()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        abort(404)
    if user["role"] == "manager" and task["assigned_to"] != user["id"]:
        flash("Bu işleme erişim yetkiniz yok.", "error")
        return redirect(url_for("dashboard"))

    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Dosya seçilmedi.", "error")
        return redirect(url_for("task_detail", task_id=task_id))

    if not allowed_file(file.filename):
        flash("Bu dosya türüne izin verilmiyor. İzin verilenler: " + ", ".join(sorted(ALLOWED_EXTENSIONS)), "error")
        return redirect(url_for("task_detail", task_id=task_id))

    original_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    task_folder = os.path.join(UPLOAD_DIR, str(task_id))
    os.makedirs(task_folder, exist_ok=True)
    file.save(os.path.join(task_folder, stored_name))

    now = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO attachments (task_id, original_name, stored_name, uploaded_by, uploaded_at) VALUES (?,?,?,?,?)",
        (task_id, original_name, stored_name, user["id"], now),
    )
    db.commit()
    flash("Dosya eklendi.", "success")
    return redirect(url_for("task_detail", task_id=task_id))


@app.route("/tasks/<int:task_id>/attachments/<int:attachment_id>")
@login_required
def download_attachment(task_id, attachment_id):
    db = get_db()
    user = current_user()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        abort(404)
    if user["role"] == "manager" and task["assigned_to"] != user["id"]:
        abort(403)

    att = db.execute(
        "SELECT * FROM attachments WHERE id=? AND task_id=?", (attachment_id, task_id)
    ).fetchone()
    if not att:
        abort(404)

    task_folder = os.path.join(UPLOAD_DIR, str(task_id))
    return send_from_directory(task_folder, att["stored_name"], as_attachment=True, download_name=att["original_name"])


# ---------- Raporlar ----------

def filtered_tasks(department="", start_date="", end_date="", status=""):
    db = get_db()
    query = """
        SELECT tasks.*, u.full_name AS assigned_name
        FROM tasks JOIN users u ON tasks.assigned_to = u.id
        WHERE 1=1
    """
    params = []
    if department:
        query += " AND tasks.department = ?"
        params.append(department)
    if start_date:
        query += " AND date(tasks.created_at) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(tasks.created_at) <= date(?)"
        params.append(end_date)
    if status:
        query += " AND tasks.status = ?"
        params.append(status)
    query += " ORDER BY tasks.department, tasks.created_at"
    return db.execute(query, params).fetchall()


def build_report(tasks):
    report = {}
    for t in tasks:
        dept = t["department"] or "Atanmamış"
        report.setdefault(dept, {"tasks": [], "counts": {s: 0 for s in STATUSES}, "overdue": 0, "stale": 0, "completion_days": []})
        report[dept]["tasks"].append(t)
        report[dept]["counts"][t["status"]] += 1
        if is_overdue(t):
            report[dept]["overdue"] += 1
        elif is_stale(t):
            report[dept]["stale"] += 1
        if t["status"] == "Tamamlandı" and t["completed_at"]:
            try:
                d1 = datetime.fromisoformat(t["created_at"])
                d2 = datetime.fromisoformat(t["completed_at"])
                report[dept]["completion_days"].append((d2 - d1).days)
            except ValueError:
                pass

    for data in report.values():
        days = data["completion_days"]
        data["avg_days"] = round(sum(days) / len(days), 1) if days else None
    return report


@app.route("/reports")
@login_required
@admin_required
def reports():
    db = get_db()
    department = request.args.get("department", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    status = request.args.get("status", "")

    tasks = filtered_tasks(department, start_date, end_date, status)
    report = build_report(tasks)

    departments = [r["department"] for r in db.execute(
        "SELECT DISTINCT department FROM users WHERE department IS NOT NULL ORDER BY department"
    ).fetchall()]

    return render_template(
        "reports.html",
        report=report,
        departments=departments,
        department=department,
        start_date=start_date,
        end_date=end_date,
        status=status,
        total_tasks=len(tasks),
    )


@app.route("/reports/export")
@login_required
@admin_required
def export_report():
    department = request.args.get("department", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    status = request.args.get("status", "")

    tasks = filtered_tasks(department, start_date, end_date, status)
    report = build_report(tasks)

    wb = Workbook()

    navy = "1C3A5E"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor=navy)
    title_font = Font(bold=True, size=13, color=navy)
    bold = Font(bold=True)

    # ---- Özet sayfası ----
    ws = wb.active
    ws.title = "Özet"
    ws["A1"] = "AFAD Görev Takip — Şube Bazlı Özet Rapor"
    ws["A1"].font = title_font
    ws["A2"] = f"Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    filt_desc = []
    if department:
        filt_desc.append(f"Şube: {department}")
    if start_date:
        filt_desc.append(f"Başlangıç: {start_date}")
    if end_date:
        filt_desc.append(f"Bitiş: {end_date}")
    if status:
        filt_desc.append(f"Durum: {status}")
    ws["A3"] = "Filtre: " + (", ".join(filt_desc) if filt_desc else "Tümü")

    headers = ["Şube", "Toplam", "Bekliyor", "Devam Ediyor", "Tamamlandı", "İptal", "Gecikmiş", "Durağan", "Ort. Tamamlama (gün)"]
    row = 5
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center")

    row += 1
    for dept, data in sorted(report.items()):
        total = sum(data["counts"].values())
        ws.cell(row=row, column=1, value=dept)
        ws.cell(row=row, column=2, value=total)
        ws.cell(row=row, column=3, value=data["counts"]["Bekliyor"])
        ws.cell(row=row, column=4, value=data["counts"]["Devam Ediyor"])
        ws.cell(row=row, column=5, value=data["counts"]["Tamamlandı"])
        ws.cell(row=row, column=6, value=data["counts"]["İptal"])
        ws.cell(row=row, column=7, value=data["overdue"])
        ws.cell(row=row, column=8, value=data["stale"])
        ws.cell(row=row, column=9, value=data["avg_days"] if data["avg_days"] is not None else "-")
        if data["overdue"] > 0:
            ws.cell(row=row, column=7).font = Font(color="C8102E", bold=True)
        if data["stale"] > 0:
            ws.cell(row=row, column=8).font = Font(color="B5720B", bold=True)
        row += 1

    for i, w in enumerate([28, 10, 10, 14, 12, 8, 10, 10, 18], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ---- Detay sayfası ----
    ws2 = wb.create_sheet("İşlem Detayları")
    d_headers = ["Sıra No", "Şube", "İşlem", "Sorumlu", "Öncelik", "Durum", "İlerleme (%)", "Oluşturulma", "Termin", "Tamamlanma", "Gecikti mi"]
    for col, h in enumerate(d_headers, start=1):
        c = ws2.cell(row=1, column=col, value=h)
        c.font = header_font
        c.fill = header_fill

    row = 2
    for dept, data in sorted(report.items()):
        for t in data["tasks"]:
            ws2.cell(row=row, column=1, value=row - 1)
            ws2.cell(row=row, column=2, value=dept)
            ws2.cell(row=row, column=3, value=t["title"])
            ws2.cell(row=row, column=4, value=t["assigned_name"])
            ws2.cell(row=row, column=5, value=t["priority"])
            ws2.cell(row=row, column=6, value=t["status"])
            ws2.cell(row=row, column=7, value=t["progress"])
            ws2.cell(row=row, column=8, value=t["created_at"][:10] if t["created_at"] else "")
            ws2.cell(row=row, column=9, value=t["due_date"] or "")
            ws2.cell(row=row, column=10, value=t["completed_at"][:10] if t["completed_at"] else "")
            overdue_cell = ws2.cell(row=row, column=11, value="Evet" if is_overdue(t) else "Hayır")
            if is_overdue(t):
                overdue_cell.font = Font(color="C8102E", bold=True)
            row += 1

    for i, w in enumerate([9, 26, 34, 18, 10, 14, 12, 12, 12, 12, 10], start=1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    fname = f"gorev-raporu-{date.today().isoformat()}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/statistics")
@login_required
@admin_required
def statistics():
    db = get_db()
    all_tasks = db.execute("SELECT tasks.*, u.full_name AS assigned_name FROM tasks JOIN users u ON tasks.assigned_to = u.id").fetchall()

    # ---- Öncelik dağılımı ----
    priority_counts = {p: 0 for p in PRIORITIES}
    for t in all_tasks:
        priority_counts[t["priority"]] += 1
    priority_total = sum(priority_counts.values())

    # ---- Şube karşılaştırması ----
    dept_report = build_report(all_tasks)
    dept_compare = []
    for dept, data in sorted(dept_report.items()):
        total = sum(data["counts"].values())
        dept_compare.append({
            "name": dept,
            "total": total,
            "completed": data["counts"]["Tamamlandı"],
            "overdue": data["overdue"],
        })
    dept_max = max((d["total"] for d in dept_compare), default=0) or 1

    # ---- Haftalık eğilim (son 8 hafta) ----
    weeks = []
    today = date.today()
    for i in range(7, -1, -1):
        monday = today - timedelta(days=today.weekday(), weeks=i)
        iso_year, iso_week, _ = monday.isocalendar()
        weeks.append({"key": (iso_year, iso_week), "label": monday.strftime("%d.%m"), "created": 0, "completed": 0})
    week_index = {w["key"]: w for w in weeks}

    for t in all_tasks:
        if t["created_at"]:
            try:
                d = datetime.fromisoformat(t["created_at"]).date()
                w = week_index.get(d.isocalendar()[:2])
                if w:
                    w["created"] += 1
            except ValueError:
                pass
        if t["completed_at"]:
            try:
                d = datetime.fromisoformat(t["completed_at"]).date()
                w = week_index.get(d.isocalendar()[:2])
                if w:
                    w["completed"] += 1
            except ValueError:
                pass
    week_max = max((max(w["created"], w["completed"]) for w in weeks), default=0) or 1

    # ---- Sorumlu bazında performans ----
    manager_perf = {}
    for t in all_tasks:
        name = t["assigned_name"]
        manager_perf.setdefault(name, {s: 0 for s in STATUSES})
        manager_perf[name][t["status"]] += 1
    manager_overdue = {name: 0 for name in manager_perf}
    for t in all_tasks:
        if is_overdue(t):
            manager_overdue[t["assigned_name"]] += 1

    return render_template(
        "statistics.html",
        user=current_user(),
        PRIORITIES=PRIORITIES,
        STATUSES=STATUSES,
        priority_counts=priority_counts,
        priority_total=priority_total,
        dept_compare=dept_compare,
        dept_max=dept_max,
        weeks=weeks,
        week_max=week_max,
        manager_perf=manager_perf,
        manager_overdue=manager_overdue,
    )


@app.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    db = get_db()
    user = current_user()

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user["password_hash"], current_password):
            flash("Mevcut şifreniz hatalı.", "error")
        elif len(new_password) < 4:
            flash("Yeni şifre en az 4 karakter olmalı.", "error")
        elif new_password != confirm_password:
            flash("Yeni şifreler birbiriyle uyuşmuyor.", "error")
        else:
            db.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (generate_password_hash(new_password, method="pbkdf2:sha256"), user["id"]),
            )
            db.commit()
            flash("Şifreniz güncellendi.", "success")
            return redirect(url_for("dashboard"))

    return render_template("change_password.html")


@app.route("/admins", methods=["GET", "POST"])
@login_required
@admin_required
def admins():
    db = get_db()
    if request.method == "POST":
        username = request.form["username"].strip()
        full_name = request.form["full_name"].strip()
        password = request.form["password"]

        existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            flash("Bu kullanıcı adı zaten kayıtlı.", "error")
        else:
            db.execute(
                "INSERT INTO users (username, password_hash, full_name, role, department) VALUES (?,?,?,?,?)",
                (username, generate_password_hash(password, method="pbkdf2:sha256"), full_name, "admin", None),
            )
            db.commit()
            flash(f"{full_name} yönetici olarak eklendi.", "success")
        return redirect(url_for("admins"))

    admin_list = db.execute("SELECT * FROM users WHERE role='admin' ORDER BY full_name").fetchall()
    return render_template("admins.html", admin_list=admin_list, current_user_id=session["user_id"])


@app.route("/admins/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_admin(user_id):
    db = get_db()
    admin_user = db.execute("SELECT * FROM users WHERE id=? AND role='admin'", (user_id,)).fetchone()
    if not admin_user:
        flash("Yönetici bulunamadı.", "error")
        return redirect(url_for("admins"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        username = request.form["username"].strip()
        new_password = request.form.get("password", "").strip()

        existing = db.execute(
            "SELECT id FROM users WHERE username=? AND id!=?", (username, user_id)
        ).fetchone()
        if existing:
            flash("Bu kullanıcı adı başka bir kullanıcıda kayıtlı.", "error")
            return redirect(url_for("edit_admin", user_id=user_id))

        if new_password:
            db.execute(
                "UPDATE users SET full_name=?, username=?, password_hash=? WHERE id=?",
                (full_name, username, generate_password_hash(new_password, method="pbkdf2:sha256"), user_id),
            )
        else:
            db.execute(
                "UPDATE users SET full_name=?, username=? WHERE id=?",
                (full_name, username, user_id),
            )
        db.commit()
        flash(f"{full_name} güncellendi.", "success")
        return redirect(url_for("admins"))

    return render_template("edit_admin.html", admin_user=admin_user)


@app.route("/admins/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id):
    db = get_db()
    active_admin_count = db.execute(
        "SELECT COUNT(*) as c FROM users WHERE role='admin' AND is_active=1"
    ).fetchone()["c"]
    target = db.execute("SELECT * FROM users WHERE id=? AND role='admin'", (user_id,)).fetchone()

    if target and target["is_active"] and active_admin_count <= 1:
        flash("Son aktif yönetici pasifleştirilemez. Önce başka bir yönetici ekleyin.", "error")
        return redirect(url_for("admins"))

    db.execute("UPDATE users SET is_active = 1 - is_active WHERE id=?", (user_id,))
    db.commit()
    return redirect(url_for("admins"))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("İşlem bulunamadı.", "error")
        return redirect(url_for("dashboard"))

    attachments = db.execute("SELECT * FROM attachments WHERE task_id=?", (task_id,)).fetchall()
    task_folder = os.path.join(UPLOAD_DIR, str(task_id))
    for a in attachments:
        try:
            os.remove(os.path.join(task_folder, a["stored_name"]))
        except OSError:
            pass
    if os.path.isdir(task_folder):
        try:
            os.rmdir(task_folder)
        except OSError:
            pass

    db.execute("DELETE FROM attachments WHERE task_id=?", (task_id,))
    db.execute("DELETE FROM task_notes WHERE task_id=?", (task_id,))
    db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    db.commit()
    flash(f"\"{task['title']}\" işlemi silindi.", "success")
    return redirect(url_for("dashboard"))


@app.route("/tasks/<int:task_id>/notes/<int:note_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_note(task_id, note_id):
    db = get_db()
    db.execute("DELETE FROM task_notes WHERE id=? AND task_id=?", (note_id, task_id))
    db.commit()
    flash("Not silindi.", "success")
    return redirect(url_for("task_detail", task_id=task_id))


# ---------- Kullanıcı (Şube Müdürü) Yönetimi ----------

@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    db = get_db()
    if request.method == "POST":
        username = request.form["username"].strip()
        full_name = request.form["full_name"].strip()
        department = request.form["department"].strip()
        password = request.form["password"]
        email = request.form.get("email", "").strip()

        existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            flash("Bu kullanıcı adı zaten kayıtlı.", "error")
        else:
            db.execute(
                "INSERT INTO users (username, password_hash, full_name, role, department, email) VALUES (?,?,?,?,?,?)",
                (username, generate_password_hash(password, method="pbkdf2:sha256"), full_name, "manager", department, email or None),
            )
            db.commit()
            flash(f"{full_name} eklendi.", "success")
        return redirect(url_for("users"))

    manager_list = db.execute(
        "SELECT * FROM users WHERE role='manager' ORDER BY department, full_name"
    ).fetchall()
    return render_template("users.html", managers=manager_list)


@app.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    db = get_db()
    db.execute("UPDATE users SET is_active = 1 - is_active WHERE id=?", (user_id,))
    db.commit()
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    db = get_db()
    manager = db.execute("SELECT * FROM users WHERE id=? AND role='manager'", (user_id,)).fetchone()
    if not manager:
        flash("Şube müdürü bulunamadı.", "error")
        return redirect(url_for("users"))

    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        department = request.form["department"].strip()
        username = request.form["username"].strip()
        new_password = request.form.get("password", "").strip()
        email = request.form.get("email", "").strip()

        existing = db.execute(
            "SELECT id FROM users WHERE username=? AND id!=?", (username, user_id)
        ).fetchone()
        if existing:
            flash("Bu kullanıcı adı başka bir kullanıcıda kayıtlı.", "error")
            return redirect(url_for("edit_user", user_id=user_id))

        old_department = manager["department"]

        if new_password:
            db.execute(
                "UPDATE users SET full_name=?, department=?, username=?, password_hash=?, email=? WHERE id=?",
                (full_name, department, username, generate_password_hash(new_password, method="pbkdf2:sha256"), email or None, user_id),
            )
        else:
            db.execute(
                "UPDATE users SET full_name=?, department=?, username=?, email=? WHERE id=?",
                (full_name, department, username, email or None, user_id),
            )

        # Birim adı değiştiyse, bu kullanıcıya atanmış mevcut işlemlerin şube alanını da güncelle
        if old_department != department:
            db.execute("UPDATE tasks SET department=? WHERE assigned_to=?", (department, user_id))

        db.commit()
        flash(f"{full_name} güncellendi.", "success")
        return redirect(url_for("users"))

    return render_template("edit_user.html", manager=manager)


# ---------- Personel (Şube Müdürü kendi ekibi) ----------

@app.route("/personnel", methods=["GET", "POST"])
@login_required
@manager_required
def personnel():
    db = get_db()
    user = current_user()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if full_name:
            db.execute(
                "INSERT INTO personnel (manager_id, full_name, created_at) VALUES (?,?,?)",
                (user["id"], full_name, datetime.now().isoformat(timespec="seconds")),
            )
            db.commit()
            flash(f"{full_name} eklendi.", "success")
        return redirect(url_for("personnel"))

    personnel_list = db.execute(
        "SELECT * FROM personnel WHERE manager_id=? ORDER BY full_name", (user["id"],)
    ).fetchall()
    return render_template("personnel.html", personnel_list=personnel_list, user=user)


@app.route("/personnel/<int:personnel_id>/toggle", methods=["POST"])
@login_required
@manager_required
def toggle_personnel(personnel_id):
    db = get_db()
    user = current_user()
    db.execute(
        "UPDATE personnel SET is_active = 1 - is_active WHERE id=? AND manager_id=?",
        (personnel_id, user["id"]),
    )
    db.commit()
    return redirect(url_for("personnel"))


# ---------- Aylık faaliyet raporu ----------

def monthly_owner_id(db, user, requested_id=None):
    if user["role"] == "manager":
        return user["id"]
    if requested_id in (None, ""):
        return None
    try:
        owner_id = int(requested_id)
    except (TypeError, ValueError):
        return None
    owner = db.execute(
        "SELECT id FROM users WHERE id=? AND role='manager'", (owner_id,)
    ).fetchone()
    return owner_id if owner else None


def valid_month(value):
    if not isinstance(value, str) or len(value) != 7:
        return False
    try:
        date.fromisoformat(value + "-01")
        return True
    except ValueError:
        return False


def clean_monthly_activity(payload):
    if not isinstance(payload, dict):
        return None
    client_id = str(payload.get("client_id", "")).strip()[:100]
    unit = str(payload.get("unit", "")).strip()
    activity_type = str(payload.get("type", payload.get("activity_type", ""))).strip()
    activity_date = str(payload.get("date", payload.get("activity_date", ""))).strip()
    status = str(payload.get("status", "")).strip()
    if (
        not client_id
        or unit not in MONTHLY_ACTIVITY_TYPES
        or activity_type not in MONTHLY_ACTIVITY_TYPES[unit]
        or status not in MONTHLY_ACTIVITY_STATUSES
    ):
        return None
    try:
        date.fromisoformat(activity_date)
        sessions = int(payload.get("sessions", payload.get("sess", 0)) or 0)
        participants = int(payload.get("participants", payload.get("ppl", 0)) or 0)
    except (TypeError, ValueError):
        return None
    if sessions < 0 or participants < 0 or sessions > 1_000_000 or participants > 1_000_000:
        return None
    return {
        "client_id": client_id,
        "unit": unit,
        "activity_type": activity_type,
        "description": str(payload.get("description", payload.get("desc", ""))).strip()[:10_000],
        "activity_date": activity_date,
        "status": status,
        "sessions": sessions,
        "participants": participants,
        "institution": str(payload.get("institution", payload.get("kur", ""))).strip()[:500],
        "participant_group": str(payload.get("participant_group", payload.get("grp", ""))).strip()[:100],
    }


def monthly_target_owner(db, user, payload):
    requested_id = payload.get("owner_id") if isinstance(payload, dict) else None
    if user["role"] == "manager":
        return user["id"]
    return monthly_owner_id(db, user, requested_id)


def monthly_owner_rows(db, user, owner_id=None):
    if user["role"] == "manager":
        return db.execute(
            "SELECT id, full_name, department FROM users WHERE id=? AND role='manager'",
            (user["id"],),
        ).fetchall()
    if owner_id:
        return db.execute(
            "SELECT id, full_name, department FROM users WHERE id=? AND role='manager'",
            (owner_id,),
        ).fetchall()
    return db.execute(
        "SELECT id, full_name, department FROM users WHERE role='manager' ORDER BY department, full_name"
    ).fetchall()


@app.route("/monthly-activities")
@login_required
def monthly_activities():
    return redirect(url_for("monthly_activity_entry"))


def render_monthly_activities(view):
    db = get_db()
    user = current_user()
    requested_id = request.args.get("owner_id", "")
    selected_owner = monthly_owner_id(db, user, requested_id)
    if user["role"] == "admin" and requested_id and selected_owner is None:
        flash("Seçilen şube müdürü bulunamadı.", "error")
        return redirect(url_for("monthly_activity_entry"))
    owners = monthly_owner_rows(db, user, None if user["role"] == "admin" else selected_owner)
    return render_template(
        "monthly_activities.html",
        user=user,
        owners=owners,
        selected_owner=selected_owner,
        activity_types=MONTHLY_ACTIVITY_TYPES,
        view=view,
    )


@app.route("/monthly-activities/entry")
@login_required
def monthly_activity_entry():
    return render_monthly_activities("entry")


@app.route("/monthly-activities/report")
@login_required
def monthly_activity_report():
    return render_monthly_activities("report")


@app.route("/monthly-activities/data")
@login_required
def monthly_activities_data():
    db = get_db()
    user = current_user()
    requested_id = request.args.get("owner_id", "")
    owner_id = monthly_owner_id(db, user, requested_id)
    if user["role"] == "admin" and requested_id and owner_id is None:
        return jsonify(error="Seçilen şube müdürü bulunamadı."), 404

    owners = monthly_owner_rows(db, user, owner_id)
    owner_ids = [row["id"] for row in owners]
    if owner_ids:
        placeholders = ",".join("?" for _ in owner_ids)
        activities = db.execute(
            f"""SELECT a.*, u.full_name AS owner_name, u.department
                FROM monthly_activities a JOIN users u ON a.owner_id=u.id
                WHERE a.owner_id IN ({placeholders})
                ORDER BY a.activity_date DESC, a.id DESC""",
            owner_ids,
        ).fetchall()
        sections = db.execute(
            f"SELECT * FROM monthly_report_sections WHERE owner_id IN ({placeholders})",
            owner_ids,
        ).fetchall()
        periods = db.execute(
            f"SELECT * FROM monthly_report_periods WHERE owner_id IN ({placeholders})",
            owner_ids,
        ).fetchall()
        preferences = db.execute(
            f"SELECT * FROM monthly_report_preferences WHERE owner_id IN ({placeholders})",
            owner_ids,
        ).fetchall()
    else:
        activities, sections, periods, preferences = [], [], [], []

    return jsonify(
        owners=[dict(row) for row in owners],
        activities=[dict(row) for row in activities],
        sections=[dict(row) for row in sections],
        periods=[dict(row) for row in periods],
        preferences=[dict(row) for row in preferences],
        activity_types=MONTHLY_ACTIVITY_TYPES,
        statuses=MONTHLY_ACTIVITY_STATUSES,
    )


@app.route("/monthly-activities/activities", methods=["POST"])
@login_required
def create_monthly_activity():
    db = get_db()
    user = current_user()
    payload = request.get_json()
    owner_id = monthly_target_owner(db, user, payload)
    activity = clean_monthly_activity(payload)
    if not owner_id:
        return jsonify(error="Kayıt için geçerli bir şube müdürü seçin."), 400
    if not activity:
        return jsonify(error="Faaliyet bilgileri eksik veya geçersiz."), 400
    month = activity["activity_date"][:7]
    period = db.execute(
        "SELECT approved_at FROM monthly_report_periods WHERE owner_id=? AND month=?",
        (owner_id, month),
    ).fetchone()
    if period and period["approved_at"]:
        return jsonify(error="Onaylanıp kilitlenmiş aya yeni kayıt eklenemez."), 409
    now = datetime.now().isoformat(timespec="seconds")
    try:
        db.execute(
            """INSERT INTO monthly_activities
               (owner_id, client_id, unit, activity_type, description, activity_date, status,
                sessions, participants, institution, participant_group, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                owner_id, activity["client_id"], activity["unit"], activity["activity_type"],
                activity["description"], activity["activity_date"], activity["status"],
                activity["sessions"], activity["participants"], activity["institution"],
                activity["participant_group"], now, now,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="Bu faaliyet kimliği daha önce kaydedilmiş."), 409
    return jsonify(ok=True), 201


@app.route("/monthly-activities/activities/<int:activity_id>", methods=["PUT", "DELETE"])
@login_required
def update_monthly_activity(activity_id):
    db = get_db()
    user = current_user()
    activity_row = db.execute(
        "SELECT * FROM monthly_activities WHERE id=?", (activity_id,)
    ).fetchone()
    if not activity_row:
        return jsonify(error="Faaliyet bulunamadı."), 404
    if user["role"] == "manager" and activity_row["owner_id"] != user["id"]:
        return jsonify(error="Bu faaliyeti değiştirme yetkiniz yok."), 403
    if request.method == "DELETE":
        period = db.execute(
            "SELECT approved_at FROM monthly_report_periods WHERE owner_id=? AND month=?",
            (activity_row["owner_id"], activity_row["activity_date"][:7]),
        ).fetchone()
        if period and period["approved_at"]:
            return jsonify(error="Onaylanıp kilitlenmiş aydaki faaliyet silinemez."), 409
        db.execute("DELETE FROM monthly_activities WHERE id=?", (activity_id,))
        db.commit()
        return jsonify(ok=True)

    payload = request.get_json()
    activity = clean_monthly_activity(payload)
    if not activity:
        return jsonify(error="Faaliyet bilgileri eksik veya geçersiz."), 400
    for month in {activity_row["activity_date"][:7], activity["activity_date"][:7]}:
        period = db.execute(
            "SELECT approved_at FROM monthly_report_periods WHERE owner_id=? AND month=?",
            (activity_row["owner_id"], month),
        ).fetchone()
        if period and period["approved_at"]:
            return jsonify(error="Onaylanıp kilitlenmiş aya ait faaliyet düzenlenemez."), 409
    try:
        db.execute(
            """UPDATE monthly_activities SET unit=?, activity_type=?, description=?, activity_date=?,
               status=?, sessions=?, participants=?, institution=?, participant_group=?, updated_at=?
               WHERE id=?""",
            (
                activity["unit"], activity["activity_type"], activity["description"],
                activity["activity_date"], activity["status"], activity["sessions"],
                activity["participants"], activity["institution"], activity["participant_group"],
                datetime.now().isoformat(timespec="seconds"), activity_id,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="Faaliyet güncellenemedi."), 409
    return jsonify(ok=True)


@app.route("/monthly-activities/import", methods=["POST"])
@login_required
def import_monthly_activities():
    db = get_db()
    user = current_user()
    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify(error="İçe aktarım verisi geçersiz."), 400
    owner_id = monthly_target_owner(db, user, payload)
    records = payload.get("records", [])
    if not owner_id:
        return jsonify(error="İçe aktarım için bir şube müdürü seçin."), 400
    if not isinstance(records, list) or len(records) > 2000:
        return jsonify(error="En fazla 2000 faaliyet tek seferde aktarılabilir."), 400

    now = datetime.now().isoformat(timespec="seconds")
    imported = duplicates = skipped = 0
    for record in records:
        activity = clean_monthly_activity(record)
        if not activity:
            skipped += 1
            continue
        period = db.execute(
            "SELECT approved_at FROM monthly_report_periods WHERE owner_id=? AND month=?",
            (owner_id, activity["activity_date"][:7]),
        ).fetchone()
        if period and period["approved_at"]:
            skipped += 1
            continue
        cursor = db.execute(
            """INSERT OR IGNORE INTO monthly_activities
               (owner_id, client_id, unit, activity_type, description, activity_date, status,
                sessions, participants, institution, participant_group, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                owner_id, activity["client_id"], activity["unit"], activity["activity_type"],
                activity["description"], activity["activity_date"], activity["status"],
                activity["sessions"], activity["participants"], activity["institution"],
                activity["participant_group"], now, now,
            ),
        )
        if cursor.rowcount:
            imported += 1
        else:
            duplicates += 1

    locks = payload.get("locks", {})
    if isinstance(locks, dict):
        for month, approved_at in locks.items():
            if not valid_month(month) or not approved_at:
                continue
            db.execute(
                """INSERT OR IGNORE INTO monthly_report_periods (owner_id, month, approved_at)
                   VALUES (?,?,?)""",
                (owner_id, month, str(approved_at)[:40]),
            )

    logos = payload.get("logos", {})
    if isinstance(logos, dict):
        left_logo = logos.get("l", "")
        right_logo = logos.get("r", "")
        if (
            isinstance(left_logo, str) and isinstance(right_logo, str)
            and len(left_logo) <= 400_000 and len(right_logo) <= 400_000
            and all(not logo or logo.startswith("data:image/png;base64,") for logo in (left_logo, right_logo))
        ):
            db.execute(
                """INSERT INTO monthly_report_preferences (owner_id, left_logo, right_logo)
                   VALUES (?,?,?) ON CONFLICT(owner_id) DO UPDATE SET
                   left_logo=CASE WHEN monthly_report_preferences.left_logo=''
                                  THEN excluded.left_logo ELSE monthly_report_preferences.left_logo END,
                   right_logo=CASE WHEN monthly_report_preferences.right_logo=''
                                   THEN excluded.right_logo ELSE monthly_report_preferences.right_logo END""",
                (owner_id, left_logo, right_logo),
            )

    db.commit()
    return jsonify(imported=imported, duplicates=duplicates, skipped=skipped)


@app.route("/monthly-activities/sections", methods=["PUT"])
@login_required
def save_monthly_sections():
    db = get_db()
    user = current_user()
    payload = request.get_json()
    if not isinstance(payload, dict) or not valid_month(payload.get("month")):
        return jsonify(error="Rapor ayı geçersiz."), 400
    owner_id = monthly_target_owner(db, user, payload)
    if not owner_id:
        return jsonify(error="Şube müdürü seçilmedi."), 400
    month = payload["month"]
    period = db.execute(
        "SELECT approved_at FROM monthly_report_periods WHERE owner_id=? AND month=?",
        (owner_id, month),
    ).fetchone()
    if period and period["approved_at"]:
        return jsonify(error="Onaylanmış raporun metinleri değiştirilemez."), 409
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        return jsonify(error="Rapor metinleri geçersiz."), 400
    for unit in MONTHLY_ACTIVITY_TYPES:
        section = sections.get(unit, {})
        if not isinstance(section, dict):
            return jsonify(error="Rapor metinleri geçersiz."), 400
        db.execute(
            """INSERT INTO monthly_report_sections (owner_id, month, unit, ongoing, issues)
               VALUES (?,?,?,?,?)
               ON CONFLICT(owner_id, month, unit) DO UPDATE SET
               ongoing=excluded.ongoing, issues=excluded.issues""",
            (
                owner_id, month, unit,
                str(section.get("ongoing", ""))[:10_000],
                str(section.get("issues", ""))[:10_000],
            ),
        )
    db.commit()
    return jsonify(ok=True)


@app.route("/monthly-activities/period", methods=["POST"])
@login_required
def toggle_monthly_period():
    db = get_db()
    user = current_user()
    payload = request.get_json()
    if not isinstance(payload, dict) or not valid_month(payload.get("month")):
        return jsonify(error="Rapor ayı geçersiz."), 400
    owner_id = monthly_target_owner(db, user, payload)
    if not owner_id:
        return jsonify(error="Şube müdürü seçilmedi."), 400
    current = db.execute(
        "SELECT approved_at FROM monthly_report_periods WHERE owner_id=? AND month=?",
        (owner_id, payload["month"]),
    ).fetchone()
    if current and current["approved_at"]:
        db.execute(
            "UPDATE monthly_report_periods SET approved_at=NULL WHERE owner_id=? AND month=?",
            (owner_id, payload["month"]),
        )
        approved = False
    else:
        db.execute(
            """INSERT INTO monthly_report_periods (owner_id, month, approved_at)
               VALUES (?,?,?) ON CONFLICT(owner_id, month) DO UPDATE SET
               approved_at=excluded.approved_at""",
            (owner_id, payload["month"], datetime.now().strftime("%d.%m.%Y")),
        )
        approved = True
    db.commit()
    return jsonify(approved=approved)


@app.route("/monthly-activities/preferences", methods=["PUT"])
@login_required
def save_monthly_preferences():
    db = get_db()
    user = current_user()
    payload = request.get_json()
    owner_id = monthly_target_owner(db, user, payload)
    if not owner_id or not isinstance(payload, dict):
        return jsonify(error="Şube müdürü seçilmedi."), 400
    left_logo = payload.get("left_logo", "")
    right_logo = payload.get("right_logo", "")
    if (
        not isinstance(left_logo, str) or not isinstance(right_logo, str)
        or len(left_logo) > 400_000 or len(right_logo) > 400_000
        or any(logo and not logo.startswith("data:image/png;base64,") for logo in (left_logo, right_logo))
    ):
        return jsonify(error="Logo dosyası geçersiz veya 300 KB sınırını aşıyor."), 400
    db.execute(
        """INSERT INTO monthly_report_preferences (owner_id, left_logo, right_logo)
           VALUES (?,?,?) ON CONFLICT(owner_id) DO UPDATE SET
           left_logo=excluded.left_logo, right_logo=excluded.right_logo""",
        (owner_id, left_logo, right_logo),
    )
    db.commit()
    return jsonify(ok=True)


init_db()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

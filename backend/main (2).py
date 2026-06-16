# backend/main.py
import os, re, sqlite3, io, csv
from datetime import datetime, date
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "classpulse.db")

app = Flask(__name__)
CORS(app)

def norm(s: str) -> str:
    if not s: return ""
    return re.sub(r'[^A-Za-z0-9]', '', s).upper()

def get_conn():
    need_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if need_init:
        init_db(conn)
    return conn

def init_db(conn):
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS students (
      student_id TEXT PRIMARY KEY,
      name TEXT,
      roll_no TEXT,
      branch TEXT,
      year INTEGER,
      barcode_value TEXT
    );
    CREATE TABLE IF NOT EXISTS student_barcodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT,
      barcode TEXT UNIQUE,
      FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS attendance (
      attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT,
      class_id INTEGER,
      timestamp TEXT,
      method TEXT,
      FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    """)
    conn.commit()

conn = get_conn()

# --- Admin registers student by scanning a card (or manual)
# POST /api/student/register_scan
# body JSON: { student_id, name, roll_no (opt), branch (opt), year (opt), barcode (raw-scanned) }
@app.route("/api/student/register_scan", methods=["POST"])
def register_scan():
    data = request.get_json(force=True)
    sid = data.get("student_id")
    name = data.get("name")
    barcode_raw = data.get("barcode") or data.get("barcode_value")
    if not sid or not name or not barcode_raw:
        return jsonify({"status":"error","message":"student_id, name and barcode are required"}), 400

    barcode = norm(barcode_raw)
    cur = conn.cursor()
    # insert or update student (store barcode_value for reference)
    cur.execute("""INSERT INTO students(student_id,name,roll_no,branch,year,barcode_value)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(student_id) DO UPDATE SET
                     name=excluded.name, roll_no=excluded.roll_no, branch=excluded.branch, year=excluded.year, barcode_value=excluded.barcode_value
                """, (sid, name, data.get("roll_no"), data.get("branch"), data.get("year"), barcode_raw))
    # add normalized barcode alias
    cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?, ?)", (sid, barcode))
    conn.commit()
    return jsonify({"status":"ok","message":"Student registered with scanned barcode","student_id":sid,"barcode":barcode})

# --- Simple manual student create (optional)
# POST /api/student   JSON: { student_id, name, barcode_value, ... }
@app.route("/api/student", methods=["POST"])
def create_student():
    data = request.get_json(force=True)
    sid = data.get("student_id"); name = data.get("name")
    if not sid or not name:
        return jsonify({"status":"error","message":"student_id and name required"}), 400
    barcode_raw = data.get("barcode_value")
    cur = conn.cursor()
    cur.execute("""INSERT INTO students(student_id,name,roll_no,branch,year,barcode_value)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(student_id) DO UPDATE SET
                     name=excluded.name, roll_no=excluded.roll_no, branch=excluded.branch, year=excluded.year, barcode_value=excluded.barcode_value
                """, (sid, name, data.get("roll_no"), data.get("branch"), data.get("year"), barcode_raw))
    if barcode_raw:
        cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?, ?)", (sid, norm(barcode_raw)))
    conn.commit()
    return jsonify({"status":"ok","message":"Student created/updated","student_id":sid})

# --- Scan to mark attendance
# POST /api/attendance/scan   JSON: { barcode, class_id }
@app.route("/api/attendance/scan", methods=["POST"])
def attendance_scan():
    data = request.get_json(force=True)
    raw = data.get("barcode")
    class_id = int(data.get("class_id", 1))
    if not raw:
        return jsonify({"status":"error","message":"barcode required"}), 400
    barcode = norm(raw)
    cur = conn.cursor()
    cur.execute("SELECT student_id FROM student_barcodes WHERE barcode = ?", (barcode,))
    r = cur.fetchone()
    if not r:
        return jsonify({"status":"not_found","message":"No student with this barcode","scanned":raw,"normalized":barcode}), 404
    sid = r["student_id"]
    today = date.today().isoformat()
    cur.execute("SELECT 1 FROM attendance WHERE student_id=? AND class_id=? AND date(timestamp)=?", (sid, class_id, today))
    if cur.fetchone():
        return jsonify({"status":"ok","message":"Already marked for today","student_id":sid})
    now = datetime.now().isoformat(timespec='seconds')
    cur.execute("INSERT INTO attendance(student_id,class_id,timestamp,method) VALUES (?,?,?,?)", (sid, class_id, now, "camera-scan"))
    conn.commit()
    return jsonify({"status":"ok","message":"Attendance recorded","student_id":sid,"timestamp":now})

# --- list students
@app.route("/api/students", methods=["GET"])
def list_students():
    cur = conn.cursor()
    cur.execute("SELECT student_id,name,roll_no,branch,year,barcode_value FROM students ORDER BY student_id LIMIT 1000")
    rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"status":"ok","count":len(rows),"students":rows})

# --- list today's attendance for class
@app.route("/api/class/<int:class_id>/attendance", methods=["GET"])
def class_attendance(class_id):
    d = request.args.get("date") or date.today().isoformat()
    cur = conn.cursor()
    cur.execute("""SELECT a.attendance_id, a.timestamp, a.student_id, s.name
                   FROM attendance a JOIN students s ON a.student_id=s.student_id
                   WHERE a.class_id=? AND date(a.timestamp)=?
                   ORDER BY a.timestamp DESC""", (class_id, d))
    rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"status":"ok","class_id":class_id,"date":d,"records":rows})

# --- simple export CSV
@app.route("/api/export/class/<int:class_id>", methods=["GET"])
def export_class(class_id):
    d = request.args.get("date") or date.today().isoformat()
    cur = conn.cursor()
    cur.execute("""SELECT a.attendance_id, a.student_id, s.name, a.timestamp, a.method
                   FROM attendance a JOIN students s ON a.student_id=s.student_id
                   WHERE a.class_id=? AND date(a.timestamp)=?
                   ORDER BY a.timestamp""", (class_id, d))
    rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["attendance_id","student_id","name","timestamp","method"])
    for r in rows:
        writer.writerow([r["attendance_id"], r["student_id"], r["name"], r["timestamp"], r["method"]])
    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=f"class_{class_id}_{d}.csv")

# --- health
@app.route("/", methods=["GET"])
def root():
    return jsonify({"status":"ok","message":"ClassPulse running (fresh simple)"})


if __name__ == "__main__":
    print("Starting backend at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

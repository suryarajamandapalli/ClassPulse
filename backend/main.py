# backend/main.py
import os
import re
import sqlite3
import io
import csv
import base64
import json
import numpy as np
import cv2
from datetime import datetime, date
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "classpulse.db")
ROOT_DIR = os.path.dirname(BASE_DIR) # Root folder of ClassPulse

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
      barcode_value TEXT UNIQUE,
      section TEXT,
      photo TEXT,
      email TEXT,
      phone TEXT,
      address TEXT,
      total_classes INTEGER DEFAULT 40
    );
    CREATE TABLE IF NOT EXISTS student_barcodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      student_id TEXT,
      barcode TEXT UNIQUE,
      FOREIGN KEY(student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS classes (
      class_id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_code TEXT,
      class_name TEXT,
      teacher TEXT,
      scheduled_date TEXT,
      scheduled_start TEXT,
      scheduled_end TEXT
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

# --- Preprocess face for template matching comparison
def preprocess_face(face_img):
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    # Equalize contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)
    # Apply blur to minimize high-frequency noise/expression differences
    blurred = cv2.GaussianBlur(equalized, (5, 5), 0)
    return blurred

# --- Get Face Config State
# GET /api/face/config
@app.route("/api/face/config", methods=["GET"])
def get_face_config():
    config_path = os.path.join(BASE_DIR, "face_config.json")
    photo_path = os.path.join(BASE_DIR, "face_registered.jpg")
    
    if os.path.exists(config_path) and os.path.exists(photo_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            return jsonify({"registered": True, "student": config})
        except Exception as e:
            return jsonify({"registered": False, "error": str(e)})
    return jsonify({"registered": False})

# --- Serve Face Photo
# GET /api/face/photo
@app.route("/api/face/photo")
def serve_face_photo():
    photo_path = os.path.join(BASE_DIR, "face_registered.jpg")
    if os.path.exists(photo_path):
        return send_file(photo_path, mimetype="image/jpeg")
    return "Not Found", 404

# --- Face ID Registration (Onboarding)
# POST /api/face/register
@app.route("/api/face/register", methods=["POST"])
def register_face():
    data = request.get_json(force=True)
    name = data.get("name")
    roll_no = data.get("roll_no")
    branch = data.get("branch") or "CSE"
    phone = data.get("phone")
    img_b64 = data.get("image_base64")
    
    if not name or not roll_no or not img_b64:
        return jsonify({"status": "error", "message": "name, roll_no, and image_base64 are required"}), 400

    try:
        # Decode base64 image
        if "," in img_b64:
            img_b64 = img_b64.split(",")[1]
        img_bytes = base64.b64decode(img_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"status": "error", "message": "Invalid image data received"}), 400
            
        # Detect Face using OpenCV Haar Cascades
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            return jsonify({"status": "error", "message": "No face detected in the frame. Please look directly at the camera with clear lighting."}), 400
            
        # Take largest detected face
        largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
        x, y, w, h = largest_face
        
        # Crop face with a slight margin
        h_margin = int(h * 0.1)
        w_margin = int(w * 0.1)
        y1 = max(0, y - h_margin)
        y2 = min(img.shape[0], y + h + h_margin)
        x1 = max(0, x - w_margin)
        x2 = min(img.shape[1], x + w + w_margin)
        
        face_crop = img[y1:y2, x1:x2]
        face_resized = cv2.resize(face_crop, (128, 128))
        
        # Save registered face image
        reg_img_path = os.path.join(BASE_DIR, "face_registered.jpg")
        cv2.imwrite(reg_img_path, face_resized)
        
        # Save details config
        config_path = os.path.join(BASE_DIR, "face_config.json")
        student_details = {
            "student_id": roll_no,
            "name": name,
            "roll_no": roll_no,
            "branch": branch,
            "phone": phone or "",
            "email": f"{name.lower().replace(' ', '.')}@giet.edu",
            "address": "Registered via Face ID Onboarding",
            "section": "B",
            "photo": "/api/face/photo"
        }
        with open(config_path, "w") as f:
            json.dump(student_details, f)
            
        # Register student in the database
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO students (student_id, name, roll_no, branch, year, barcode_value, section, photo, email, phone, address, total_classes)
            VALUES (?, ?, ?, ?, 2, ?, ?, ?, ?, ?, ?, 40)
        """, (
            student_details["student_id"],
            student_details["name"],
            student_details["roll_no"],
            student_details["branch"],
            student_details["roll_no"], # Barcode value matches roll_no
            student_details["section"],
            student_details["photo"],
            student_details["email"],
            student_details["phone"],
            student_details["address"]
        ))
        
        # Create barcode aliases
        barcode = norm(roll_no)
        if barcode:
            cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (roll_no, barcode))
            if len(barcode) >= 6:
                cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (roll_no, barcode[-6:]))
            if len(barcode) >= 8:
                cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (roll_no, barcode[-8:]))
        
        conn.commit()
        return jsonify({"status": "ok", "message": "Face ID registered successfully", "student": student_details})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Server processing error: {str(e)}"}), 500

# --- Face ID Login Verification
# POST /api/face/verify
@app.route("/api/face/verify", methods=["POST"])
def verify_face():
    config_path = os.path.join(BASE_DIR, "face_config.json")
    reg_img_path = os.path.join(BASE_DIR, "face_registered.jpg")
    
    if not os.path.exists(config_path) or not os.path.exists(reg_img_path):
        return jsonify({"status": "error", "message": "No face registered on system"}), 400
        
    data = request.get_json(force=True)
    img_b64 = data.get("image_base64")
    
    if not img_b64:
        return jsonify({"status": "error", "message": "image_base64 is required"}), 400

    try:
        # Load registered details
        with open(config_path, "r") as f:
            student_details = json.load(f)
            
        # Decode base64 image
        if "," in img_b64:
            img_b64 = img_b64.split(",")[1]
        img_bytes = base64.b64decode(img_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"status": "error", "message": "Invalid image data"}), 400
            
        # Detect Face
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            return jsonify({"status": "no_face", "message": "No face detected"}), 200
            
        # Crop face
        largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
        x, y, w, h = largest_face
        
        h_margin = int(h * 0.1)
        w_margin = int(w * 0.1)
        y1 = max(0, y - h_margin)
        y2 = min(img.shape[0], y + h + h_margin)
        x1 = max(0, x - w_margin)
        x2 = min(img.shape[1], x + w + w_margin)
        
        face_crop = img[y1:y2, x1:x2]
        face_resized = cv2.resize(face_crop, (128, 128))
        
        # Load registered template image
        reg_face = cv2.imread(reg_img_path)
        if reg_face is None:
            return jsonify({"status": "error", "message": "Could not read registered face template"}), 500
            
        # Process faces for matching
        test_processed = preprocess_face(face_resized)
        reg_processed = preprocess_face(reg_face)
        
        # Compare using Normalized Cross-Correlation
        res = cv2.matchTemplate(test_processed, reg_processed, cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0])
        
        # Set a matching threshold. Preprocessed aligned templates show score > 0.42.
        threshold = 0.42
        is_match = score >= threshold
        print(f"Face verification attempt: score={score:.4f}, threshold={threshold}, match={is_match}")
        
        if is_match:
            return jsonify({
                "status": "ok", 
                "match": True, 
                "score": score, 
                "name": student_details["name"],
                "student": student_details
            })
        else:
            return jsonify({"status": "ok", "match": False, "score": score})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Admin registers student by scanning a card (or manual)
# POST /api/student/register_scan
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
    cur.execute("""INSERT INTO students(student_id,name,roll_no,branch,year,barcode_value)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(student_id) DO UPDATE SET
                     name=excluded.name, roll_no=excluded.roll_no, branch=excluded.branch, year=excluded.year, barcode_value=excluded.barcode_value
                """, (sid, name, data.get("roll_no"), data.get("branch"), data.get("year"), barcode_raw))
    cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?, ?)", (sid, barcode))
    conn.commit()
    return jsonify({"status":"ok","message":"Student registered with scanned barcode","student_id":sid,"barcode":barcode})

# --- Simple manual student create (optional)
# POST /api/student
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
# POST /api/attendance/scan
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
    
    cur.execute("SELECT name FROM students WHERE student_id=?", (sid,))
    srow = cur.fetchone()
    name = srow["name"] if srow else "Unknown Student"
    
    today = date.today().isoformat()
    cur.execute("SELECT 1 FROM attendance WHERE student_id=? AND class_id=? AND date(timestamp)=?", (sid, class_id, today))
    if cur.fetchone():
        return jsonify({"status":"ok","message":"Already marked for today","student_id":sid,"name":name})
    
    now = datetime.now().isoformat(timespec='seconds')
    cur.execute("INSERT INTO attendance(student_id,class_id,timestamp,method) VALUES (?,?,?,?)", (sid, class_id, now, "camera-scan"))
    conn.commit()
    return jsonify({"status":"ok","message":"Attendance recorded","student_id":sid,"name":name,"timestamp":now})

# --- Toggle attendance (mark present / absent)
# POST /api/attendance/toggle
@app.route("/api/attendance/toggle", methods=["POST"])
def attendance_toggle():
    data = request.get_json(force=True)
    sid = data.get("student_id")
    class_id = int(data.get("class_id", 1))
    if not sid:
        return jsonify({"status":"error","message":"student_id is required"}), 400
        
    cur = conn.cursor()
    today = date.today().isoformat()
    
    # Check if marked for today
    cur.execute("SELECT attendance_id FROM attendance WHERE student_id=? AND class_id=? AND date(timestamp)=?", (sid, class_id, today))
    row = cur.fetchone()
    
    if row:
        # Delete it (mark absent)
        cur.execute("DELETE FROM attendance WHERE attendance_id=?", (row["attendance_id"],))
        conn.commit()
        action = "absent"
    else:
        # Insert it (mark present)
        now = datetime.now().isoformat(timespec='seconds')
        cur.execute("INSERT INTO attendance(student_id,class_id,timestamp,method) VALUES (?,?,?,?)", (sid, class_id, now, "manual-entry"))
        conn.commit()
        action = "present"
        
    # Get updated attendance count
    cur.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?", (sid,))
    classes_attended = cur.fetchone()[0]
    
    return jsonify({
        "status": "ok",
        "action": action,
        "classes_attended": classes_attended,
        "presentToday": (action == "present")
    })

# --- list students with stats
@app.route("/api/students", methods=["GET"])
def list_students():
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute("""
        SELECT s.*, 
               (SELECT COUNT(*) FROM attendance a WHERE a.student_id = s.student_id) as classes_attended,
               (SELECT COUNT(*) FROM attendance a WHERE a.student_id = s.student_id AND date(a.timestamp) = ?) as present_today
        FROM students s
        ORDER BY s.name ASC
        LIMIT 1000
    """, (today,))
    rows = [dict(r) for r in cur.fetchall()]
    
    for r in rows:
        r["presentToday"] = r["present_today"] > 0
        del r["present_today"]
        
    return jsonify({"status":"ok","count":len(rows),"students":rows})

# --- list today's attendance for class
@app.route("/api/class/<int:class_id>/attendance", methods=["GET"])
def class_attendance(class_id):
    d = request.args.get("date") or date.today().isoformat()
    cur = conn.cursor()
    cur.execute("""SELECT a.attendance_id, a.timestamp, a.student_id, s.name, a.method
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

# --- Serve Static Frontend Files from Root Directory ---
@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(ROOT_DIR, "js"), filename)

@app.route("/frontend/<path:filename>")
def serve_frontend(filename):
    return send_from_directory(os.path.join(ROOT_DIR, "frontend"), filename)

@app.route("/dashboard.html")
def serve_dashboard():
    return send_from_directory(ROOT_DIR, "dashboard.html")

@app.route("/index.html")
def serve_index_html():
    return send_from_directory(ROOT_DIR, "index.html")

@app.route("/")
def serve_index():
    return send_from_directory(ROOT_DIR, "index.html")

@app.route("/<path:filename>")
def serve_root_files(filename):
    return send_from_directory(ROOT_DIR, filename)

if __name__ == "__main__":
    print("Starting backend at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

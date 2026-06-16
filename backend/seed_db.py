# backend/seed_db.py
import os
import sqlite3
import csv
import re
from datetime import datetime, timedelta
import random

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "classpulse.db")
CSV_PATH = os.path.join(BASE_DIR, "seed_students.csv")

def norm(s: str) -> str:
    if not s: return ""
    return re.sub(r'[^A-Za-z0-9]', '', s).upper()

def main():
    print("Connecting to database at:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Ensure Schema
    print("Ensuring tables exist...")
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

    # Just in case columns don't exist in existing DB, we add them individually
    # This prevents sqlite3 error if table already existed without these columns
    columns_to_add = [
        ("section", "TEXT"),
        ("photo", "TEXT"),
        ("email", "TEXT"),
        ("phone", "TEXT"),
        ("address", "TEXT"),
        ("total_classes", "INTEGER DEFAULT 40")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to students table.")
        except sqlite3.OperationalError:
            # Column already exists
            pass
    conn.commit()

    # 2. Seed GIET Students
    print("Seeding GIET Students...")
    giet_students = [
        {
            "student_id": "24T91A05B6", "name": "Surya Raja Mandapalli", "roll_no": "24T91A05B6",
            "branch": "CSE", "section": "B", "year": 2, "barcode_value": "STUDENT_566",
            "photo": "https://media.campx.in/giet/student-photos/13219.jpg",
            "email": "suryarajamandapalli@college.edu", "phone": "+91 98765 43210", "address": "123 Tech Street, Hyderabad"
        },
        {
            "student_id": "24T91A0576", "name": "Charan kandivalasa", "roll_no": "24T91A0576",
            "branch": "CSE", "section": "B", "year": 2, "barcode_value": "STUDENT_567",
            "photo": "https://media.campx.in/giet/student-photos/13164.jpg",
            "email": "charan.kandivalasa@college.edu", "phone": "+91 98765 43211", "address": "456 Innovation Ave, Mumbai"
        },
        {
            "student_id": "24T91A0580", "name": "Sameera Karri", "roll_no": "24T91A0580",
            "branch": "ECE", "section": "B", "year": 2, "barcode_value": "STUDENT_568",
            "photo": "https://media.campx.in/giet/student-photos/13177.jpg",
            "email": "sameera.karri@college.edu", "phone": "+91 98765 43212", "address": "789 Circuit Lane, Delhi"
        },
        {
            "student_id": "24T91A0582", "name": "Poojitha kasireddy", "roll_no": "24T91A0582",
            "branch": "ECE", "section": "B", "year": 2, "barcode_value": "STUDENT_569",
            "photo": "https://media.campx.in/giet/student-photos/13233.jpg",
            "email": "poojitha.kasireddy@college.edu", "phone": "+91 98765 43213", "address": "321 Code Boulevard, Bangalore"
        },
        {
            "student_id": "24T91A05B9", "name": "Bhagavan Mediboyina", "roll_no": "24T91A05B9",
            "branch": "MECH", "section": "B", "year": 2, "barcode_value": "STUDENT_570",
            "photo": "https://media.campx.in/giet/student-photos/13201.jpg",
            "email": "bhagavan.mediboyina@college.edu", "phone": "+91 98765 43214", "address": "654 Power Street, Chennai"
        },
        {
            "student_id": "24T91A05H2", "name": "Sunkara Sai Bhaskar", "roll_no": "24T91A05H2",
            "branch": "CSE", "section": "B", "year": 2, "barcode_value": "STUDENT_571",
            "photo": "https://media.campx.in/giet/student-photos/13172.jpg",
            "email": "sunkara.saibhaskar@college.edu", "phone": "+91 98765 43215", "address": "987 Algorithm Way, Pune"
        }
    ]

    for s in giet_students:
        cur.execute("""
            INSERT OR REPLACE INTO students (student_id, name, roll_no, branch, year, barcode_value, section, photo, email, phone, address, total_classes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 40)
        """, (s["student_id"], s["name"], s["roll_no"], s["branch"], s["year"], s["barcode_value"], s["section"], s["photo"], s["email"], s["phone"], s["address"]))
    conn.commit()

    # 3. Seed Students from seed_students.csv (if exists)
    indian_cities = ["Hyderabad", "Visakhapatnam", "Kakinada", "Rajahmundry", "Vijayawada", "Guntur", "Tirupati", "Nellore", "Anantapur"]
    if os.path.exists(CSV_PATH):
        print("Seeding students from CSV:", CSV_PATH)
        with open(CSV_PATH, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row['student_id']
                # Skip if already exists (like if GIET students happen to clash, though they won't)
                cur.execute("SELECT 1 FROM students WHERE student_id=?", (sid,))
                if cur.fetchone():
                    continue

                name = row['name']
                roll_no = row.get('roll_no') or sid
                branch = row.get('branch') or 'CSE'
                year = int(row.get('year')) if row.get('year') else 3
                barcode_value = row['barcode_value']
                section = random.choice(['A', 'B', 'C'])
                photo = f"https://picsum.photos/seed/{sid}/200/200"

                # Generate clean email
                clean_name = re.sub(r'[^a-zA-Z\s]', '', name).strip().lower()
                email_parts = clean_name.split()
                if len(email_parts) >= 2:
                    email = f"{email_parts[0]}.{email_parts[1]}@giet.edu"
                else:
                    email = f"{email_parts[0]}@giet.edu"

                phone = f"+91 9{random.randint(100000000, 999999999)}"
                address = f"{random.randint(10, 200)} Main Road, {random.choice(indian_cities)}"

                cur.execute("""
                    INSERT OR REPLACE INTO students (student_id, name, roll_no, branch, year, barcode_value, section, photo, email, phone, address, total_classes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 40)
                """, (sid, name, roll_no, branch, year, barcode_value, section, photo, email, phone, address))
        conn.commit()
    else:
        print("No seed_students.csv found in backend. Skipping CSV seed.")

    # 4. Generate student barcodes aliases
    print("Generating barcode aliases (normalized & suffixes)...")
    cur.execute("SELECT student_id, barcode_value FROM students")
    students_list = cur.fetchall()
    barcode_count = 0
    for row in students_list:
        sid = row["student_id"]
        bc_val = row["barcode_value"]
        if not bc_val:
            continue
        
        # Add exact normalized
        bcn = norm(bc_val)
        if bcn:
            try:
                cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn))
                barcode_count += 1
            except Exception as e:
                print(f"Error inserting barcode {bcn} for {sid}: {e}")
            
            # Add suffix aliases (last 6 and 8 chars)
            if len(bcn) >= 6:
                cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn[-6:]))
            if len(bcn) >= 8:
                cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn[-8:]))
    conn.commit()
    print(f"Registered {barcode_count} primary barcodes and their suffix aliases.")

    # 5. Seed historical attendance
    print("Seeding historical attendance for last 10 days...")
    # Clear old attendance so we re-seed fresh, realistic values
    cur.execute("DELETE FROM attendance")
    conn.commit()

    # Get last 10 school days (excl Sat/Sun)
    school_days = []
    curr_date = datetime.now() - timedelta(days=1) # start from yesterday
    while len(school_days) < 10:
        if curr_date.weekday() < 5: # Monday to Friday
            school_days.append(curr_date.date())
        curr_date -= timedelta(days=1)
    
    # Sort chronological
    school_days.reverse()
    print("Historical attendance days:", [d.isoformat() for d in school_days])

    # Ensure class 1 exists in classes table
    cur.execute("INSERT OR REPLACE INTO classes(class_id, course_code, class_name, teacher, scheduled_date, scheduled_start, scheduled_end) VALUES (1, 'CS201', 'Core Course', 'Admin Teacher', ?, '09:00', '10:00')", (datetime.now().date().isoformat(),))
    conn.commit()

    attendance_records = 0
    # For each student, assign a target attendance percentage (e.g. between 60% and 95%)
    # Then for each day, mark present based on that probability
    for s_row in students_list:
        sid = s_row["student_id"]
        target_prob = random.uniform(0.60, 0.95)
        
        # If it is Surya Raja (you), let's give him a high attendance percentage (e.g. 88%)
        if sid == "24T91A05B6":
            target_prob = 0.88 # 88%

        for idx, day in enumerate(school_days):
            if random.random() < target_prob:
                # Decide method
                method = "camera-scan" if random.random() < 0.8 else "manual-entry"
                # Timestamp around 09:00 - 09:15
                hour = 9
                minute = random.randint(0, 15)
                second = random.randint(0, 59)
                ts = datetime(day.year, day.month, day.day, hour, minute, second).isoformat(timespec='seconds')
                
                cur.execute("INSERT INTO attendance(student_id, class_id, timestamp, method) VALUES (?, ?, ?, ?)", (sid, 1, ts, method))
                attendance_records += 1
                
    conn.commit()
    print(f"Inserted {attendance_records} historical attendance records.")
    
    # Verify counts
    cur.execute("SELECT COUNT(*) FROM students")
    print("Total students in DB:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM student_barcodes")
    print("Total barcode aliases in DB:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM attendance")
    print("Total attendance records in DB:", cur.fetchone()[0])

    conn.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    main()

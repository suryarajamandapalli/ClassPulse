# backend/migrate_add_tables.py
import os, sqlite3

DB = os.path.join(os.path.dirname(__file__), "classpulse.db")
print("Using DB:", DB)

conn = sqlite3.connect(DB)
cur = conn.cursor()

print("Creating missing tables if they do not exist...")

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
print("Done. Tables ensured. Now you can optionally populate aliases (see next step).")
conn.close()

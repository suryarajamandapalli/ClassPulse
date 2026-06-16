# backend/load_students.py
import sqlite3, os, csv

DB_PATH = os.path.join(os.path.dirname(__file__), "classpulse.db")
CSV = "seed_students.csv"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ensure schema exists
cur.executescript("""
CREATE TABLE IF NOT EXISTS students (
  student_id TEXT PRIMARY KEY,
  name TEXT,
  roll_no TEXT,
  branch TEXT,
  year INTEGER,
  barcode_value TEXT UNIQUE
);
""")
conn.commit()

count = 0
with open(CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute("""INSERT INTO students(student_id,name,roll_no,branch,year,barcode_value)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(student_id) DO UPDATE SET name=excluded.name, roll_no=excluded.roll_no, branch=excluded.branch, year=excluded.year, barcode_value=excluded.barcode_value
                    """, (row['student_id'], row['name'], row.get('roll_no'), row.get('branch'), int(row.get('year')) if row.get('year') else None, row['barcode_value']))
        count += 1
conn.commit()
print(f"Imported {count} students into {DB_PATH}")
conn.close()

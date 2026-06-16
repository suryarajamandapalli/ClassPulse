# backend/create_suffix_aliases.py
import sqlite3, os, re
DB = os.path.join(os.path.dirname(__file__), "classpulse.db")

def norm(s): return ''.join(ch for ch in (s or "") if ch.isalnum()).upper()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT student_id, barcode_value FROM students WHERE barcode_value IS NOT NULL")
rows = cur.fetchall()
count = 0
for r in rows:
    sid = r[0]; bc = r[1]
    bcn = norm(bc)
    if not bcn: continue
    cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn))
    if len(bcn) >= 6:
        cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn[-6:]))
    if len(bcn) >= 8:
        cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn[-8:]))
    count += 1
conn.commit()
print("Processed", count, "students")
conn.close()

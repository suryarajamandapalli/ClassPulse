# backend/populate_aliases_from_students.py
import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), "classpulse.db")
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT student_id, barcode_value FROM students WHERE barcode_value IS NOT NULL")
for sid, bc in cur.fetchall():
    if not bc: continue
    bcn = ''.join(ch for ch in bc if ch.isalnum()).upper()
    cur.execute("INSERT OR IGNORE INTO student_barcodes(student_id, barcode) VALUES (?,?)", (sid, bcn))
conn.commit()
print("Populated aliases for students")
conn.close()

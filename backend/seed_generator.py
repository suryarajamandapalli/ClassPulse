# backend/seed_generator.py
from faker import Faker
import csv

fake = Faker()
NUM = 200
OUT = "seed_students.csv"

with open(OUT, "w", newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["student_id","name","roll_no","branch","year","barcode_value"])
    for i in range(1, NUM+1):
        sid = f"S{1000 + i}"
        name = fake.name()
        roll = f"21CSE{str(i).zfill(3)}"
        branch = "CSE"
        year = 2 + (i % 4)
        barcode = f"CSE2025_{str(i).zfill(4)}"
        writer.writerow([sid, name, roll, branch, year, barcode])

print(f"Generated {OUT}")

CREATE DATABASE IF NOT EXISTS classpulse;
USE classpulse;


CREATE TABLE IF NOT EXISTS students (
student_id VARCHAR(64) PRIMARY KEY,
name VARCHAR(200),
roll_no VARCHAR(50),
branch VARCHAR(100),
year INT,
barcode_value VARCHAR(128) UNIQUE
);


CREATE TABLE IF NOT EXISTS classes (
class_id INT AUTO_INCREMENT PRIMARY KEY,
course_code VARCHAR(50),
class_name VARCHAR(200),
teacher VARCHAR(200),
scheduled_date DATE,
scheduled_start TIME,
scheduled_end TIME
);


CREATE TABLE IF NOT EXISTS attendance (
attendance_id BIGINT AUTO_INCREMENT PRIMARY KEY,
student_id VARCHAR(64),
class_id INT,
timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
method VARCHAR(50),
UNIQUE KEY uniq_student_class_day (student_id, class_id, DATE(timestamp)),
FOREIGN KEY (student_id) REFERENCES students(student_id),
FOREIGN KEY (class_id) REFERENCES classes(class_id)
);


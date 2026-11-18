CREATE USER IF NOT EXISTS 'attendance_app'@'localhost'
  IDENTIFIED BY 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON university_system.* TO 'attendance_app'@'localhost';
FLUSH PRIVILEGES;

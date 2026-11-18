SET @user_password_hash_exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='users' AND column_name='password_hash');
SET @user_password_hash_ddl = IF(@user_password_hash_exists=0, 'ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL', 'SELECT 1');
PREPARE user_password_hash_stmt FROM @user_password_hash_ddl;
EXECUTE user_password_hash_stmt;
DEALLOCATE PREPARE user_password_hash_stmt;
SET @user_created_at_exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='users' AND column_name='created_at');
SET @user_created_at_ddl = IF(@user_created_at_exists=0, 'ALTER TABLE users ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP', 'SELECT 1');
PREPARE user_created_at_stmt FROM @user_created_at_ddl;
EXECUTE user_created_at_stmt;
DEALLOCATE PREPARE user_created_at_stmt;
SET @user_updated_at_exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='users' AND column_name='updated_at');
SET @user_updated_at_ddl = IF(@user_updated_at_exists=0, 'ALTER TABLE users ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP', 'SELECT 1');
PREPARE user_updated_at_stmt FROM @user_updated_at_ddl;
EXECUTE user_updated_at_stmt;
DEALLOCATE PREPARE user_updated_at_stmt;
SET @user_deleted_at_exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='users' AND column_name='deleted_at');
SET @user_deleted_at_ddl = IF(@user_deleted_at_exists=0, 'ALTER TABLE users ADD COLUMN deleted_at DATETIME NULL', 'SELECT 1');
PREPARE user_deleted_at_stmt FROM @user_deleted_at_ddl;
EXECUTE user_deleted_at_stmt;
DEALLOCATE PREPARE user_deleted_at_stmt;
SET @access_log_source_exists = (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='access_logs' AND column_name='source');
SET @access_log_source_ddl = IF(@access_log_source_exists=0, "ALTER TABLE access_logs ADD COLUMN source VARCHAR(24) NOT NULL DEFAULT 'nfc'", 'SELECT 1');
PREPARE access_log_source_stmt FROM @access_log_source_ddl;
EXECUTE access_log_source_stmt;
DEALLOCATE PREPARE access_log_source_stmt;
CREATE TABLE IF NOT EXISTS courses (
 id INT AUTO_INCREMENT PRIMARY KEY,
 code VARCHAR(32) NOT NULL UNIQUE,
 name VARCHAR(160) NOT NULL,
 description TEXT NULL,
 teacher_id INT NULL,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_courses_active(active),INDEX idx_courses_teacher(teacher_id,active)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS enrollments (
 user_id INT NOT NULL,
 course_id INT NOT NULL,
 enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 enrollment_status ENUM('active','withdrawn') NOT NULL DEFAULT 'active',
 PRIMARY KEY(user_id,course_id),
 INDEX idx_enrollments_course_status(course_id,enrollment_status)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS course_sessions (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 course_id INT NOT NULL,
 title VARCHAR(160) NULL,
 starts_at DATETIME NOT NULL,
 ends_at DATETIME NOT NULL,
 room VARCHAR(80) NULL,
 status ENUM('planned','open','closed','cancelled') NOT NULL DEFAULT 'planned',
 late_after_minutes SMALLINT UNSIGNED NOT NULL DEFAULT 10,
 created_by INT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_sessions_course_starts(course_id,starts_at),
 INDEX idx_sessions_status_starts(status,starts_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS attendance_records (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 session_id BIGINT UNSIGNED NOT NULL,
 user_id INT NOT NULL,
 status ENUM('absent','present','late','excused') NOT NULL DEFAULT 'absent',
 marked_at DATETIME NULL,
 marked_by INT NULL,
 access_log_id INT NULL,
 method ENUM('nfc','manual','import') NOT NULL DEFAULT 'manual',
 note VARCHAR(500) NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_attendance_session_user(session_id,user_id),
 INDEX idx_attendance_session_status(session_id,status),
 INDEX idx_attendance_user_status(user_id,status)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS audit_events (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 actor_id INT NULL,event_type VARCHAR(48) NOT NULL,entity_type VARCHAR(48) NOT NULL,
 entity_id VARCHAR(64) NULL,summary VARCHAR(500) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_audit_created(created_at),INDEX idx_audit_entity(entity_type,entity_id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS import_batches (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 actor_id INT NULL,file_name VARCHAR(255) NOT NULL,file_sha256 CHAR(64) NOT NULL,
 total_rows INT UNSIGNED NOT NULL DEFAULT 0,inserted_rows INT UNSIGNED NOT NULL DEFAULT 0,
 skipped_rows INT UNSIGNED NOT NULL DEFAULT 0,created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_import_created(created_at),INDEX idx_import_hash(file_sha256)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS api_tokens (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,user_id INT NOT NULL,
 token_hash CHAR(64) NOT NULL UNIQUE,expires_at DATETIME NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,INDEX idx_api_token_expiry(expires_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS attendance_history (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 session_id BIGINT UNSIGNED NOT NULL,user_id INT NOT NULL,actor_id INT NULL,
 previous_status VARCHAR(16) NULL,new_status VARCHAR(16) NOT NULL,
 source ENUM('manual','nfc','import','system') NOT NULL DEFAULT 'manual',
 reason VARCHAR(500) NULL,changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_history_session_user(session_id,user_id,changed_at),
 INDEX idx_history_actor(actor_id,changed_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS card_assignment_history (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,actor_id INT NULL,old_card_id VARCHAR(64) NULL,
 new_card_id VARCHAR(64) NULL,action ENUM('assigned','unassigned') NOT NULL,
 changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_card_hist_user(user_id,changed_at)
) ENGINE=InnoDB;

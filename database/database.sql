CREATE DATABASE IF NOT EXISTS university_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE university_system;

CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    email VARCHAR(254) NULL UNIQUE,
    neptun VARCHAR(6) NULL UNIQUE,
    card_id VARCHAR(64) NULL UNIQUE,
    role ENUM('student','teacher','admin') NOT NULL DEFAULT 'student',
    password_hash VARCHAR(255) NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    is_inside BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen DATETIME NULL,
    deleted_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_name(name),
    INDEX idx_users_active_inside(active,is_inside),
    INDEX idx_users_role_active(role,active)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS courses (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL,
    description TEXT NULL,
    teacher_id INT UNSIGNED NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_courses_teacher FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_courses_active(active),
    INDEX idx_courses_teacher(teacher_id,active)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS enrollments (
    user_id INT UNSIGNED NOT NULL,
    course_id INT UNSIGNED NOT NULL,
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    enrollment_status ENUM('active','withdrawn') NOT NULL DEFAULT 'active',
    PRIMARY KEY(user_id,course_id),
    CONSTRAINT fk_enrollments_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_course FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
    INDEX idx_enrollments_course_status(course_id,enrollment_status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS course_sessions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_id INT UNSIGNED NOT NULL,
    title VARCHAR(160) NULL,
    starts_at DATETIME NOT NULL,
    ends_at DATETIME NOT NULL,
    room VARCHAR(80) NULL,
    status ENUM('planned','open','closed','cancelled') NOT NULL DEFAULT 'planned',
    late_after_minutes SMALLINT UNSIGNED NOT NULL DEFAULT 10,
    created_by INT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sessions_course FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
    CONSTRAINT fk_sessions_creator FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_sessions_course_starts(course_id,starts_at),
    INDEX idx_sessions_status_starts(status,starts_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS access_logs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    card_id VARCHAR(64) NOT NULL,
    action ENUM('ENTRY','EXIT') NOT NULL,
    source VARCHAR(24) NOT NULL DEFAULT 'nfc',
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_access_logs_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_access_timestamp(timestamp),
    INDEX idx_access_user_timestamp(user_id,timestamp),
    INDEX idx_access_action_timestamp(action,timestamp)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attendance_records (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id BIGINT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    status ENUM('absent','present','late','excused') NOT NULL DEFAULT 'absent',
    marked_at DATETIME NULL,
    marked_by INT UNSIGNED NULL,
    access_log_id BIGINT UNSIGNED NULL,
    method ENUM('nfc','manual','import') NOT NULL DEFAULT 'manual',
    note VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_attendance_session_user(session_id,user_id),
    CONSTRAINT fk_attendance_session FOREIGN KEY(session_id) REFERENCES course_sessions(id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_marker FOREIGN KEY(marked_by) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_attendance_accesslog FOREIGN KEY(access_log_id) REFERENCES access_logs(id) ON DELETE SET NULL,
    INDEX idx_attendance_user_status(user_id,status),
    INDEX idx_attendance_session_status(session_id,status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    actor_id INT UNSIGNED NULL,
    event_type VARCHAR(48) NOT NULL,
    entity_type VARCHAR(48) NOT NULL,
    entity_id VARCHAR(64) NULL,
    summary VARCHAR(500) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_actor FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_audit_created(created_at),
    INDEX idx_audit_entity(entity_type,entity_id),
    INDEX idx_audit_actor(actor_id,created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS import_batches (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    actor_id INT UNSIGNED NULL,
    file_name VARCHAR(255) NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    total_rows INT UNSIGNED NOT NULL DEFAULT 0,
    inserted_rows INT UNSIGNED NOT NULL DEFAULT 0,
    skipped_rows INT UNSIGNED NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_import_actor FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_import_created(created_at),
    INDEX idx_import_hash(file_sha256)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS api_tokens (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_api_token_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_api_token_expiry(expires_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS attendance_history (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 session_id BIGINT UNSIGNED NOT NULL,user_id INT UNSIGNED NOT NULL,actor_id INT UNSIGNED NULL,
 previous_status VARCHAR(16) NULL,new_status VARCHAR(16) NOT NULL,
 source ENUM('manual','nfc','import','system') NOT NULL DEFAULT 'manual',
 reason VARCHAR(500) NULL,changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_history_session FOREIGN KEY(session_id) REFERENCES course_sessions(id) ON DELETE CASCADE,
 CONSTRAINT fk_history_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_history_actor FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE SET NULL,
 INDEX idx_history_session_user(session_id,user_id,changed_at),
 INDEX idx_history_actor(actor_id,changed_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS card_assignment_history (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 user_id INT UNSIGNED NOT NULL,actor_id INT UNSIGNED NULL,
 old_card_id VARCHAR(64) NULL,new_card_id VARCHAR(64) NULL,
 action ENUM('assigned','unassigned') NOT NULL,
 changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_card_hist_user FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
 CONSTRAINT fk_card_hist_actor FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE SET NULL,
 INDEX idx_card_hist_user(user_id,changed_at)
) ENGINE=InnoDB;

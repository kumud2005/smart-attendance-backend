-- ============================================================
-- Public-registration review workflow
-- Smart Anti-Proxy Attendance System
-- ============================================================
-- Run on LOCAL MySQL first, before starting the updated backend.
-- This migration does NOT modify attendance history or face data.
-- ============================================================

CREATE TABLE IF NOT EXISTS student_section_registration_requests (
    request_id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    section_id INT NOT NULL,

    request_status ENUM('PENDING', 'APPROVED', 'REJECTED')
        NOT NULL DEFAULT 'PENDING',

    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME NULL,
    reviewed_by_user_id INT NULL,
    review_note VARCHAR(255) NULL,

    PRIMARY KEY (request_id),
    UNIQUE KEY uq_ssrr_student (student_id),
    KEY idx_ssrr_status (request_status),
    KEY idx_ssrr_section (section_id),
    KEY idx_ssrr_reviewer (reviewed_by_user_id),

    CONSTRAINT fk_ssrr_student
        FOREIGN KEY (student_id)
        REFERENCES student_profiles (student_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_ssrr_section
        FOREIGN KEY (section_id)
        REFERENCES sections (section_id),

    CONSTRAINT fk_ssrr_reviewer
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS faculty_assignment_requests (
    request_id INT NOT NULL AUTO_INCREMENT,
    faculty_id INT NOT NULL,
    semester_id INT NOT NULL,
    section_id INT NOT NULL,
    subject_id INT NOT NULL,

    request_status ENUM('PENDING', 'APPROVED', 'REJECTED')
        NOT NULL DEFAULT 'PENDING',

    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME NULL,
    reviewed_by_user_id INT NULL,
    review_note VARCHAR(255) NULL,

    PRIMARY KEY (request_id),
    KEY idx_far_faculty_status (faculty_id, request_status),
    KEY idx_far_semester (semester_id),
    KEY idx_far_section (section_id),
    KEY idx_far_subject (subject_id),
    KEY idx_far_reviewer (reviewed_by_user_id),

    CONSTRAINT fk_far_faculty
        FOREIGN KEY (faculty_id)
        REFERENCES faculty_profiles (faculty_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_far_semester
        FOREIGN KEY (semester_id)
        REFERENCES semesters (semester_id),

    CONSTRAINT fk_far_section
        FOREIGN KEY (section_id)
        REFERENCES sections (section_id),

    CONSTRAINT fk_far_subject
        FOREIGN KEY (subject_id)
        REFERENCES subjects (subject_id),

    CONSTRAINT fk_far_reviewer
        FOREIGN KEY (reviewed_by_user_id)
        REFERENCES users (user_id)
        ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

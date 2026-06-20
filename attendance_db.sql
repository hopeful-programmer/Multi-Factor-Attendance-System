-- ============================================================
-- Multi-Factor Biometric Attendance System — Database Schema
-- ============================================================

DROP DATABASE IF EXISTS `attendance_db`;
CREATE DATABASE IF NOT EXISTS `attendance_db`
  DEFAULT CHARACTER SET utf8mb4;
USE `attendance_db`;


-- --------------------------------------------------------
-- Table: user_tbl
-- --------------------------------------------------------
DROP TABLE IF EXISTS `user_tbl`;
CREATE TABLE IF NOT EXISTS `user_tbl` (
  `user_id`       INT          NOT NULL AUTO_INCREMENT,
  `name`          VARCHAR(50)  NOT NULL,
  `password`      VARCHAR(60)  NOT NULL COMMENT 'bcrypt hash',
  `face_features` LONGTEXT     NOT NULL COMMENT '128-dim dlib face encoding stored as comma-separated floats',
  `audio_profile` LONGBLOB     NOT NULL COMMENT 'Picovoice Eagle binary voice profile',
  `isActive`      ENUM('True','False') NOT NULL DEFAULT 'True',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_name` (`name`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;


-- --------------------------------------------------------
-- Table: attendance_tbl
-- --------------------------------------------------------
DROP TABLE IF EXISTS `attendance_tbl`;
CREATE TABLE IF NOT EXISTS `attendance_tbl` (
  `record_id` INT      NOT NULL AUTO_INCREMENT,
  `user_id`   INT      DEFAULT NULL,
  `set_at`    DATETIME DEFAULT NULL,
  PRIMARY KEY (`record_id`),
  KEY `fk_user_id` (`user_id`),
  CONSTRAINT `fk_user_id` FOREIGN KEY (`user_id`) REFERENCES `user_tbl` (`user_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;


-- --------------------------------------------------------
-- Trigger: enforce 24-hour attendance cooldown per user
--
-- Prevents duplicate check-ins at the database level —
-- no application logic needed to guard against this.
-- --------------------------------------------------------
DROP TRIGGER IF EXISTS `attendance_tbl_before_insert`;

DELIMITER //
CREATE TRIGGER `attendance_tbl_before_insert`
BEFORE INSERT ON `attendance_tbl`
FOR EACH ROW
BEGIN
    DECLARE last_set DATETIME;

    SELECT MAX(set_at) INTO last_set
    FROM attendance_tbl
    WHERE user_id = NEW.user_id;

    IF last_set IS NOT NULL AND TIMESTAMPDIFF(HOUR, last_set, NOW()) < 24 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Attendance already recorded: user must wait 24 hours before checking in again.';
    END IF;

    SET NEW.set_at = NOW();
END//
DELIMITER ;


-- --------------------------------------------------------
-- Table: security_log — failed authentication events
-- --------------------------------------------------------
DROP TABLE IF EXISTS `security_log`;
CREATE TABLE IF NOT EXISTS `security_log` (
  `log_id`         INT          NOT NULL AUTO_INCREMENT,
  `attempted_name` VARCHAR(50)  DEFAULT NULL,
  `event`          VARCHAR(100) NOT NULL,
  `set_at`         DATETIME     DEFAULT NOW(),
  PRIMARY KEY (`log_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;


-- --------------------------------------------------------
-- View: attendance_view — readable attendance report
-- --------------------------------------------------------
DROP VIEW IF EXISTS `attendance_view`;
CREATE VIEW `attendance_view` AS
    SELECT
        a.record_id,
        a.set_at,
        u.name
    FROM attendance_tbl  a
    JOIN user_tbl        u ON a.user_id = u.user_id;

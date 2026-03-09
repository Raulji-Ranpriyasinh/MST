-- Migration 004: Add firm_id column to student_details table
-- Run this against your local MySQL database: mysql -u root -p exam < migrations/004_add_firm_id_to_student_details.sql

-- Add firm_id column only if it does not already exist
SET @col_exists = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'student_details'
    AND COLUMN_NAME = 'firm_id'
);

SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `student_details` ADD COLUMN `firm_id` INT DEFAULT NULL',
  'SELECT "Column firm_id already exists on student_details"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add foreign key only if it does not already exist
SET @fk_exists = (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'student_details'
    AND CONSTRAINT_NAME = 'fk_student_details_firm'
);

SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `student_details` ADD CONSTRAINT `fk_student_details_firm` FOREIGN KEY (`firm_id`) REFERENCES `consultancy_firms` (`id`) ON DELETE SET NULL',
  'SELECT "Foreign key fk_student_details_firm already exists"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

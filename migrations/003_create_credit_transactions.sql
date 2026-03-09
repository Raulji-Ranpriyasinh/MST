-- Migration 003: Create credit_transactions table
-- Run this against your local MySQL database: mysql -u root -p exam < migrations/003_create_credit_transactions.sql

CREATE TABLE IF NOT EXISTS `credit_transactions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `firm_id` INT NOT NULL,
  `student_id` INT DEFAULT NULL,
  `credits_used` INT NOT NULL DEFAULT 0,
  `transaction_type` ENUM('purchase', 'usage', 'refund', 'adjustment') NOT NULL,
  `description` TEXT DEFAULT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_credit_transactions_firm_id` (`firm_id`),
  KEY `idx_credit_transactions_student_id` (`student_id`),
  CONSTRAINT `fk_credit_transactions_firm` FOREIGN KEY (`firm_id`) REFERENCES `consultancy_firms` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_credit_transactions_student` FOREIGN KEY (`student_id`) REFERENCES `student_details` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

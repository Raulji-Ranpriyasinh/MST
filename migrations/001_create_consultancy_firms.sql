-- Migration 001: Create consultancy_firms table
-- Run this against your local MySQL database: mysql -u root -p exam < migrations/001_create_consultancy_firms.sql

CREATE TABLE IF NOT EXISTS `consultancy_firms` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `firm_name` VARCHAR(255) NOT NULL,
  `contact_email` VARCHAR(255) NOT NULL,
  `contact_phone` VARCHAR(20) DEFAULT NULL,
  `credit_balance` INT NOT NULL DEFAULT 0,
  `price_per_assessment` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_firm_name` (`firm_name`),
  UNIQUE KEY `uq_contact_email` (`contact_email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Migration 002: Create firm_admins table
-- Run this against your local MySQL database: mysql -u root -p exam < migrations/002_create_firm_admins.sql

CREATE TABLE IF NOT EXISTS `firm_admins` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `firm_id` INT NOT NULL,
  `username` VARCHAR(100) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_firm_admin_username` (`username`),
  UNIQUE KEY `uq_firm_admin_email` (`email`),
  KEY `idx_firm_admins_firm_id` (`firm_id`),
  CONSTRAINT `fk_firm_admins_firm` FOREIGN KEY (`firm_id`) REFERENCES `consultancy_firms` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Synthetic Data API — MySQL Schema
-- Run: mysql -u <user> -p <database> < schema.sql

CREATE TABLE IF NOT EXISTS users (
    id INTEGER NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_email (email)
);

CREATE TABLE IF NOT EXISTS synthetic_requests (
    id INTEGER NOT NULL AUTO_INCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    prompt TEXT,
    columns JSON NOT NULL,
    num_rows INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    error TEXT,
    duration_ms INTEGER,
    PRIMARY KEY (id),
    INDEX idx_user_id (user_id),
    INDEX idx_task_type (task_type),
    INDEX idx_created (created)
);

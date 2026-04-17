-- Synthetic Data platform schema
-- All tables use IF NOT EXISTS so this script is safe to re-run.

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER      NOT NULL AUTO_INCREMENT,
    email       VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_users_email (email)
);

CREATE TABLE IF NOT EXISTS synthetic_requests (
    id          INTEGER      NOT NULL AUTO_INCREMENT,
    user_id     INTEGER,
    task_type   VARCHAR(50)  NOT NULL,
    prompt      TEXT,
    columns     JSON         NOT NULL,
    num_rows    INTEGER      NOT NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'completed',
    error       TEXT,
    duration_ms INTEGER,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_requests_user    (user_id),
    INDEX idx_requests_type    (task_type),
    INDEX idx_requests_created (created_at),
    CONSTRAINT fk_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

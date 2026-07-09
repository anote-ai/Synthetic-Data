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

CREATE TABLE IF NOT EXISTS generation_versions (
    version_id        VARCHAR(36)  NOT NULL,
    user_email         VARCHAR(255) NOT NULL,
    name               VARCHAR(255),
    parent_version_id  VARCHAR(36),
    task_type          VARCHAR(50)  NOT NULL,
    prompt             TEXT,
    columns            JSON         NOT NULL,
    examples           JSON,
    params             JSON,
    result_data        JSON,
    num_rows           INTEGER      NOT NULL,
    row_count          INTEGER      NOT NULL,
    quality_score      JSON,
    status             VARCHAR(20)  NOT NULL DEFAULT 'completed',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version_id),
    INDEX idx_versions_user    (user_email),
    INDEX idx_versions_name    (user_email, name),
    INDEX idx_versions_parent  (parent_version_id),
    INDEX idx_versions_created (created_at),
    CONSTRAINT fk_versions_parent FOREIGN KEY (parent_version_id) REFERENCES generation_versions(version_id) ON DELETE SET NULL
);

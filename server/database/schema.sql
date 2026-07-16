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

-- RSI feedback loop (issue #92): generator prompt templates and their measured lift.
CREATE TABLE IF NOT EXISTS rsi_templates (
    template_id     VARCHAR(64)  NOT NULL,
    task_type       VARCHAR(50)  NOT NULL,
    label           VARCHAR(100) NOT NULL,
    prompt_template TEXT         NOT NULL,
    use_count       INTEGER      NOT NULL DEFAULT 0,
    avg_lift        FLOAT,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (template_id),
    INDEX idx_rsi_templates_task (task_type)
);

CREATE TABLE IF NOT EXISTS rsi_batches (
    batch_id       VARCHAR(36)  NOT NULL,
    user_email     VARCHAR(255) NOT NULL,
    task_type      VARCHAR(50)  NOT NULL,
    template_id    VARCHAR(64),
    weak_spot      VARCHAR(255),
    target_model   VARCHAR(255),
    iteration      INTEGER,
    prompt         TEXT,
    row_count      INTEGER,
    baseline_score FLOAT,
    new_score      FLOAT,
    lift_score     FLOAT,
    status         VARCHAR(20)  NOT NULL DEFAULT 'unscored',
    error          TEXT,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (batch_id),
    INDEX idx_rsi_batches_template (template_id),
    INDEX idx_rsi_batches_user     (user_email),
    CONSTRAINT fk_rsi_batches_template FOREIGN KEY (template_id) REFERENCES rsi_templates(template_id) ON DELETE SET NULL
);

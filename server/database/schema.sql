CREATE TABLE IF NOT EXISTS synthetic_requests (
    id INTEGER NOT NULL AUTO_INCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    prompt TEXT,
    columns JSON NOT NULL,
    num_rows INTEGER NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS generation_versions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  version_id VARCHAR(36) NOT NULL UNIQUE,
  user_email VARCHAR(255),
  task_type VARCHAR(50),
  prompt TEXT,
  columns JSON,
  num_rows INT,
  params JSON,
  seed INT,
  result_data LONGTEXT,
  row_count INT,
  status VARCHAR(20) DEFAULT 'completed',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_email (user_email),
  INDEX idx_task_type (task_type),
  INDEX idx_created (created_at)
);

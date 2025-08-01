# TODO: update the schema

-- CREATE TABLE synthetic_requests (
--     id INTEGER NOT NULL AUTO_INCREMENT,
--     created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     user_id INTEGER NOT NULL,
--     task_type TEXT NOT NULL,
--     prompt TEXT,
--     columns JSON NOT NULL,
--     num_rows INTEGER NOT NULL,
--     PRIMARY KEY (id)
-- );

-- CREATE TABLE IF NOT EXISTS synthetic_requests (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     user_id INTEGER NOT NULL,
--     task_type TEXT NOT NULL,
--     prompt TEXT,
--     columns TEXT NOT NULL,  -- store JSON as text
--     num_rows INTEGER NOT NULL
-- );

-- CREATE TABLE IF NOT EXISTS datasets (
--     id TEXT PRIMARY KEY,
--     type TEXT,
--     path TEXT,
--     created_at TEXT
-- );



CREATE TABLE IF NOT EXISTS synthetic_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    prompt TEXT,
    columns TEXT NOT NULL,
    num_rows INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    type TEXT,
    path TEXT,
    created_at TEXT
);


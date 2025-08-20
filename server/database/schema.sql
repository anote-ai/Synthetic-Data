# Database schema for Anote Synthetic Data API

CREATE TABLE synthetic_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    task_type TEXT NOT NULL,
    prompt TEXT,
    columns JSON NOT NULL,
    num_rows INTEGER NOT NULL
);

CREATE TABLE generated_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data JSON NOT NULL,
    FOREIGN KEY (request_id) REFERENCES synthetic_requests(id)
);

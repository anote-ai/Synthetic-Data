# TODO: update the schema

CREATE TABLE synthetic_requests (
    id INTEGER NOT NULL AUTO_INCREMENT,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    prompt TEXT,
    columns JSON NOT NULL,
    num_rows INTEGER NOT NULL,
    PRIMARY KEY (id)
);

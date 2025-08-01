# # TODO: add imports
# # schema of where we store API calls



import sqlite3
from datetime import datetime

DB_PATH = "synthetic_data.db"

def insert_dataset(dataset_id, dataset_type, path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO datasets (id, type, path, created_at) VALUES (?, ?, ?, ?)",
        (dataset_id, dataset_type, path, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def get_all_datasets():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, type, path, created_at FROM datasets")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "type": r[1], "path": r[2], "created_at": r[3]} for r in rows]

def get_dataset_path(dataset_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT path FROM datasets WHERE id = ?", (dataset_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


# def store_generate_request(user_email, task_type, columns, prompt, num_rows):
#     conn, cursor = get_db_connection()
#     user_id = user_id_for_email(user_email)
#     cursor.execute(
#         'INSERT INTO synthetic_requests (user_id, task_type, prompt, columns, num_rows) VALUES (%s, %s, %s, %s, %s)',
#         [user_id, task_type, prompt, json.dumps(columns), num_rows]
#     )
#     conn.commit()
#     conn.close()

# import sqlite3
# from datetime import datetime

# DB_PATH = "synthetic_data.db"

# def insert_dataset(dataset_id, dataset_type, path):
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "INSERT INTO datasets (id, type, path, created_at) VALUES (?, ?, ?, ?)",
#         (dataset_id, dataset_type, path, datetime.utcnow().isoformat())
#     )
#     conn.commit()
#     conn.close()

# def get_all_datasets():
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute("SELECT id, type, path, created_at FROM datasets")
#     rows = cur.fetchall()
#     conn.close()
#     return [{"id": r[0], "type": r[1], "path": r[2], "created_at": r[3]} for r in rows]

# def get_dataset_path(dataset_id):
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute("SELECT path FROM datasets WHERE id = ?", (dataset_id,))
#     row = cur.fetchone()
#     conn.close()
#     return row[0] if row else None



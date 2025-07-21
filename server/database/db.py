# TODO: add imports
# schema of where we store API calls

def store_generate_request(user_email, task_type, columns, prompt, num_rows):
    conn, cursor = get_db_connection()
    user_id = user_id_for_email(user_email)
    cursor.execute(
        'INSERT INTO synthetic_requests (user_id, task_type, prompt, columns, num_rows) VALUES (%s, %s, %s, %s, %s)',
        [user_id, task_type, prompt, json.dumps(columns), num_rows]
    )
    conn.commit()
    conn.close()

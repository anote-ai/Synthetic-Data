import sqlite3
import json
import os

# TODO: add imports
# schema of where we store API calls

def init_database():
    """Initialize the database with schema"""
    conn, cursor = get_db_connection()
    
    # Read and execute schema
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        schema = f.read()
    
    # Execute each statement, skipping comments
    for statement in schema.split(';'):
        statement = statement.strip()
        if statement and not statement.startswith('#'):
            cursor.execute(statement)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    db_path = os.path.join(os.path.dirname(__file__), 'synthetic_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()

def user_id_for_email(user_email):
    """Get or create user ID for email"""
    conn, cursor = get_db_connection()
    
    # Check if user exists
    cursor.execute('SELECT id FROM users WHERE email = ?', (user_email,))
    result = cursor.fetchone()
    
    if result:
        user_id = result['id']
    else:
        # Create new user
        cursor.execute('INSERT INTO users (email) VALUES (?)', (user_email,))
        user_id = cursor.lastrowid
        conn.commit()
    
    conn.close()
    return user_id

def store_generate_request(user_email, task_type, columns, prompt, num_rows):
    conn, cursor = get_db_connection()
    user_id = user_id_for_email(user_email)
    cursor.execute(
        'INSERT INTO synthetic_requests (user_id, task_type, prompt, columns, num_rows) VALUES (?, ?, ?, ?, ?)',
        [user_id, task_type, prompt, json.dumps(columns), num_rows]
    )
    conn.commit()
    conn.close()

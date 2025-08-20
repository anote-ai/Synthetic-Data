import json
import sqlite3
import os

def init_database():
    """Initialize database and create tables if they don't exist"""
    db_path = os.path.join(os.path.dirname(__file__), 'anote_synthetic_data.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS synthetic_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            task_type TEXT NOT NULL,
            prompt TEXT,
            columns JSON NOT NULL,
            num_rows INTEGER NOT NULL,
            user_id TEXT DEFAULT "test@example.com"
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generated_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            data JSON NOT NULL,
            FOREIGN KEY (request_id) REFERENCES synthetic_requests(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    db_path = os.path.join(os.path.dirname(__file__), 'anote_synthetic_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()

def store_generate_request(task_type, columns, prompt, num_rows, user_email="test@example.com"):
    """Store generation request in database and return the request ID"""
    try:
        conn, cursor = get_db_connection()
        
        # Check if user_id column exists, if not add it
        cursor.execute("PRAGMA table_info(synthetic_requests)")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        if 'user_id' not in column_names:
            # Add user_id column if it doesn't exist
            cursor.execute('ALTER TABLE synthetic_requests ADD COLUMN user_id TEXT DEFAULT "test@example.com"')
            print("Added user_id column to synthetic_requests table")
        
        # Insert the request
        cursor.execute(
            'INSERT INTO synthetic_requests (task_type, prompt, columns, num_rows, user_id) VALUES (?, ?, ?, ?, ?)',
            [task_type, prompt, json.dumps(columns), num_rows, user_email]
        )
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return request_id
    except Exception as e:
        print(f"Database error: {e}")
        return None

def store_generated_data(request_id, data):
    """Store generated data in database"""
    try:
        conn, cursor = get_db_connection()
        cursor.execute(
            'INSERT INTO generated_data (request_id, data) VALUES (?, ?)',
            [request_id, json.dumps(data)]
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database error storing generated data: {e}")
        return False

def get_generated_data(request_id):
    """Retrieve generated data by request ID"""
    try:
        conn, cursor = get_db_connection()
        cursor.execute(
            'SELECT data FROM generated_data WHERE request_id = ?',
            [request_id]
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return json.loads(result['data'])
        return None
    except Exception as e:
        print(f"Database error retrieving data: {e}")
        return None
